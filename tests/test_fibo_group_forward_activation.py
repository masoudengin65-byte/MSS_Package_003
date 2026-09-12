import hashlib

import pytest

from mss.analysis.fibo_group_forward_activation import (
    REQUIRED_EXECUTION_PATHS,
    activation_window,
    build_manifest,
    canonical_bytes,
    verify_manifest,
)
from mss.analysis.fibo_group_paired_forward_runtime import (
    _FIBO_VERIFIED_ACTIVATION_MARKER,
)

FREEZE = {
    "number": 46,
    "url": "https://github.com/example/repo/pull/46",
    "state": "MERGED",
    "merge_commit_sha": "a" * 40,
    "merged_at_utc": "2026-09-11T17:00:00Z",
}
VERSIONS = {"python_version": "3.12.2", "numpy_version": "2.3.3"}
IDENTITY = [
    {"path": path, "git_blob_sha256": hashlib.sha256(path.encode()).hexdigest()}
    for path in sorted(REQUIRED_EXECUTION_PATHS)
]


def test_activation_window_is_two_hours_then_ceil_m15_and_45_days():
    assert activation_window("2026-09-11T17:01:01Z") == (
        "2026-09-11T19:15:00Z",
        "2026-10-26T19:15:00Z",
    )


def test_manifest_verification_issues_only_marked_context():
    manifest = build_manifest(
        freeze_metadata=FREEZE,
        manifest_created_at_utc="2026-09-11T17:05:00Z",
        runtime_versions=VERSIONS,
        execution_identity=IDENTITY,
    )
    raw = canonical_bytes(manifest)
    activation = verify_manifest(
        manifest=manifest,
        manifest_bytes=raw,
        freeze_metadata=FREEZE,
        publication_metadata={
            "state": "MERGED",
            "base_branch": "main",
            "merged_at_utc": "2026-09-11T17:10:00Z",
            "manifest_blob_sha256": hashlib.sha256(raw).hexdigest(),
        },
        runtime_versions=VERSIONS,
        observed_execution_identity=IDENTITY,
        no_forward_outcome_access_verified=True,
    )
    assert activation._verification_marker is _FIBO_VERIFIED_ACTIVATION_MARKER


def test_manifest_tamper_and_late_publication_fail_closed():
    manifest = build_manifest(
        freeze_metadata=FREEZE,
        manifest_created_at_utc="2026-09-11T17:05:00Z",
        runtime_versions=VERSIONS,
        execution_identity=IDENTITY,
    )
    raw = canonical_bytes(manifest)
    with pytest.raises(RuntimeError, match="before activation"):
        verify_manifest(
            manifest=manifest,
            manifest_bytes=raw,
            freeze_metadata=FREEZE,
            publication_metadata={
                "state": "MERGED",
                "base_branch": "main",
                "merged_at_utc": "2026-09-11T19:00:00Z",
                "manifest_blob_sha256": hashlib.sha256(raw).hexdigest(),
            },
            runtime_versions=VERSIONS,
            observed_execution_identity=IDENTITY,
            no_forward_outcome_access_verified=True,
        )
    tampered = dict(manifest)
    tampered["provider"] = "Alpari"
    tampered_raw = canonical_bytes(tampered)
    with pytest.raises(RuntimeError, match="broker contract"):
        verify_manifest(
            manifest=tampered,
            manifest_bytes=tampered_raw,
            freeze_metadata=FREEZE,
            publication_metadata={
                "state": "MERGED",
                "base_branch": "main",
                "merged_at_utc": "2026-09-11T17:10:00Z",
                "manifest_blob_sha256": hashlib.sha256(tampered_raw).hexdigest(),
            },
            runtime_versions=VERSIONS,
            observed_execution_identity=IDENTITY,
            no_forward_outcome_access_verified=True,
        )
