param(
    [string]$ProjectRoot = 'C:\MSS_Package_003',
    [string]$PythonExe = 'C:\MSS_Runtime\venv\Scripts\python.exe',
    [string]$TerminalExe = 'C:\Program Files\Alpari MT5\terminal64.exe'
)

$ErrorActionPreference = 'Stop'
$version = 'V16'
$repoRaw = 'https://raw.githubusercontent.com/masoudengin65-byte/MSS_Package_003'
$manifestRel = "reports/MSS_Sprint93_3F_FIBO_Group_Forward_Activation_Manifest_Refreeze_$version.json"
$freezeRel = "reports/MSS_Sprint93_3F_FIBO_Group_Forward_Refreeze_${version}_Freeze_PR.json"
$publicationRel = "reports/MSS_Sprint93_3F_FIBO_Group_Forward_Refreeze_${version}_Publication_PR.json"
$runnerRel = 'integration_tests/run_sprint93_3f_fibo_group_forward_supervisor.py'
$stageName = 'mss-fibo-v16-' + [guid]::NewGuid().ToString('N')
$stage = Join-Path ([IO.Path]::GetTempPath()) $stageName

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project directory is missing: $ProjectRoot"
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python runtime is missing: $PythonExe"
}
if (-not (Test-Path -LiteralPath $TerminalExe -PathType Leaf)) {
    throw "MT5 terminal is missing: $TerminalExe"
}

function Get-StagedFile([string]$Revision, [string]$Relative) {
    $target = Join-Path $stage ($Relative.Replace('/', '\'))
    $parent = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri "$repoRaw/$Revision/$Relative" -OutFile $target
    return $target
}

function Test-Sha256([string]$Path, [string]$Expected) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    if ($actual -ne $Expected.ToLowerInvariant()) {
        throw "SHA256 mismatch: $Path"
    }
}

New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $manifestStage = Get-StagedFile 'main' $manifestRel
    $freezeStage = Get-StagedFile 'main' $freezeRel
    $publicationStage = Get-StagedFile 'main' $publicationRel
    $manifest = Get-Content -LiteralPath $manifestStage -Raw | ConvertFrom-Json
    $publication = Get-Content -LiteralPath $publicationStage -Raw | ConvertFrom-Json
    $freeze = Get-Content -LiteralPath $freezeStage -Raw | ConvertFrom-Json
    Test-Sha256 $manifestStage $publication.manifest_blob_sha256
    if ($freeze.merge_commit_sha -ne $manifest.runtime_freeze_pr.merge_commit_sha) {
        throw 'Freeze receipt does not match manifest'
    }
    $sourceRevision = [string]$manifest.runtime_freeze_pr.merge_commit_sha
    if ($sourceRevision -notmatch '^[0-9a-f]{40}$') {
        throw 'Invalid frozen source revision'
    }
    $runnerStage = Get-StagedFile $sourceRevision $runnerRel
    foreach ($row in $manifest.complete_execution_identity) {
        $relative = [string]$row.path
        if ($relative -notmatch '^(src|integration_tests)/[A-Za-z0-9_./-]+\.py$' -or $relative.Contains('..')) {
            throw "Invalid frozen source path: $relative"
        }
        $file = Get-StagedFile $sourceRevision $relative
        Test-Sha256 $file ([string]$row.git_blob_sha256)
    }
    $allFiles = @($manifestRel, $freezeRel, $publicationRel, $runnerRel) + @(
        $manifest.complete_execution_identity | ForEach-Object { [string]$_.path }
    )
    foreach ($relative in ($allFiles | Select-Object -Unique)) {
        $source = Join-Path $stage ($relative.Replace('/', '\'))
        $destination = Join-Path $ProjectRoot ($relative.Replace('/', '\'))
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
    foreach ($row in $manifest.complete_execution_identity) {
        $destination = Join-Path $ProjectRoot (([string]$row.path).Replace('/', '\'))
        Test-Sha256 $destination ([string]$row.git_blob_sha256)
    }
    Test-Sha256 (Join-Path $ProjectRoot ($manifestRel.Replace('/', '\'))) $publication.manifest_blob_sha256
} finally {
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $stageFull = [IO.Path]::GetFullPath($stage)
    if ($stageFull.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and
        ([IO.Path]::GetFileName($stageFull) -eq $stageName)) {
        Remove-Item -LiteralPath $stageFull -Recurse -Force
    }
}

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$attempt = [guid]::NewGuid().ToString('N').Substring(0, 8)
$journal = Join-Path $ProjectRoot "shadow_data\live\sprint93_3f_fibo_forward_v16_live\paired_evidence_$stamp-$attempt.jsonl"
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
Set-Location -LiteralPath $ProjectRoot
Write-Host "FIBO_V16_VERIFIED: starting read-only shadow collection. Journal: $journal"
& $PythonExe $runnerRel --manifest $manifestRel --freeze-pr-json $freezeRel --publication-pr-json $publicationRel --terminal-path $TerminalExe --journal $journal
if ($LASTEXITCODE -ne 0) {
    throw "FIBO runner exited with code $LASTEXITCODE; preserve the journal and supervisor log"
}
