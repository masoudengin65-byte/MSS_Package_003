"""Sprint 93.2B paired forward-shadow activation and evidence collection.

The activation manifest is intentionally created only after this package's PR is
publicly merged.  Collection stays fail-closed until that write-once manifest is
committed, publicly pushed, and verified against the frozen Sprint 93.2A rules.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
from typing import Any, Mapping

from mss.analysis.confluence_gated_smart_money_pipeline import (
    ConfluenceGatedSmartMoneyPipeline,
)
from mss.analysis.frozen_shadow_strategy_adapter import (
    FrozenShadowSignal,
    FrozenShadowStrategyAdapter,
)
from mss.analysis.global_time_authority import GlobalTimeAuthority
from mss.analysis.live_completed_candle_signal_engine import (
    LiveCompletedCandleSignalEngine,
)
from mss.analysis.shadow_trade_journal import ShadowTradeJournal
from mss.analysis.shadow_position_recovery import ShadowPositionRecovery
from mss.analysis.shadow_trade_engine import ShadowTradeEngine
from mss.analysis.shadow_trade_valuation import ShadowTradeValuation
from mss.analysis.smart_money_pipeline import SmartMoneyPipeline
from mss.analysis.sprint93_confluence_gate_v2_preregistration import (
    Sprint93ConfluenceGateV2Preregistration as Preregistration,
)
from mss.analysis.virtual_position_engine import (
    VirtualPosition,
    VirtualPositionEngine,
)


VERSION = "MSS_SPRINT93_2B_PAIRED_FORWARD_ACTIVATION_V1"
TIMEFRAME = "M15"
TIMEFRAME_SECONDS = 15 * 60
DEFAULT_MANIFEST_RELATIVE_PATH = (
    "reports/MSS_Sprint93_2B_Paired_Forward_Activation_Manifest.json"
)
DEFAULT_EVIDENCE_RELATIVE_PATH = (
    "shadow_data/live/sprint93_2b_paired_forward/paired_evidence.jsonl"
)

PAIRED_EXECUTOR_PATH = "src/mss/analysis/sprint93_paired_forward_activation.py"
ACTIVATION_RUNNER_PATH = (
    "integration_tests/run_sprint93_2b_paired_forward_activation.py"
)
EVALUATION_PATH = (
    "src/mss/analysis/sprint93_confluence_gate_v2_preregistration.py"
)
JOURNAL_PATH = "src/mss/analysis/shadow_trade_journal.py"
RISK_PATH = "src/mss/analysis/shadow_risk_calculator.py"
VALUATION_PATH = "src/mss/analysis/shadow_trade_valuation.py"

EXECUTION_ROOT_PATHS = tuple(
    sorted(
        {
            ACTIVATION_RUNNER_PATH,
            EVALUATION_PATH,
            JOURNAL_PATH,
            PAIRED_EXECUTOR_PATH,
            RISK_PATH,
            VALUATION_PATH,
            "src/mss/analysis/confluence_gated_smart_money_pipeline.py",
            "src/mss/analysis/frozen_shadow_strategy_adapter.py",
            "src/mss/analysis/global_time_authority.py",
            "src/mss/analysis/live_completed_candle_signal_engine.py",
            "src/mss/analysis/shadow_trade_engine.py",
            "src/mss/analysis/smart_money_pipeline.py",
            "src/mss/analysis/virtual_position_engine.py",
        }
    )
)

SYMBOL_MAP = dict(Preregistration.SYMBOLS)
FULL_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
EVIDENCE_EVENT_TYPES = {
    "decision": "SPRINT93_2B_PAIRED_DECISION",
    "entry_input": "SPRINT93_2B_PAIRED_ENTRY_INPUT",
    "entry": "SPRINT93_2B_PAIRED_ENTRY_OUTCOME",
    "settlement": "SPRINT93_2B_PAIRED_SETTLEMENT",
    "terminal_baseline": "SPRINT93_2B_BASELINE_TERMINAL",
    "terminal_candidate": "SPRINT93_2B_CANDIDATE_TERMINAL",
    "terminal_input_baseline": "SPRINT93_2B_BASELINE_TERMINAL_INPUT",
    "terminal_input_candidate": "SPRINT93_2B_CANDIDATE_TERMINAL_INPUT",
}
_VERIFIED_ACTIVATION_MARKER = object()


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _normalise_lf(raw: bytes) -> bytes:
    if b"\r" in raw.replace(b"\r\n", b""):
        raise RuntimeError("bare carriage return is not a canonical representation")
    return raw.replace(b"\r\n", b"\n")


def _parse_utc_z(value: object, label: str) -> datetime:
    return Preregistration._parse_utc_z(value, label)


def _render_utc_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _epoch_from_utc_z(value: str, label: str) -> int:
    parsed = _parse_utc_z(value, label)
    if parsed.microsecond:
        raise RuntimeError(f"{label} must have whole-second precision")
    return int(parsed.timestamp())


def _require_full_git_sha(value: object, label: str) -> str:
    Preregistration._require_full_git_sha(value, label)
    return str(value)


def observed_runtime_versions() -> dict[str, str]:
    import numpy

    return {
        "python_version": platform.python_version(),
        "numpy_version": str(numpy.__version__),
    }


def _run_git(
    repository_root: Path,
    arguments: list[str],
    *,
    text: bool = False,
) -> bytes | str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    return completed.stdout


def _resolve_commit(repository_root: Path, revision: str) -> str:
    if revision != "HEAD" and FULL_GIT_SHA_RE.fullmatch(revision) is None:
        raise RuntimeError("revision must be HEAD or a full lowercase commit SHA")
    resolved = str(
        _run_git(
            repository_root,
            ["rev-parse", "--verify", f"{revision}^{{commit}}"],
            text=True,
        )
    ).strip()
    return _require_full_git_sha(resolved, "resolved commit")


def _git_blob(repository_root: Path, commit_sha: str, path: str) -> bytes:
    _require_full_git_sha(commit_sha, "Git blob commit")
    raw = _run_git(repository_root, ["cat-file", "blob", f"{commit_sha}:{path}"])
    if not isinstance(raw, bytes):
        raise RuntimeError("Git blob read unexpectedly returned text")
    return raw


def _git_path_exists(repository_root: Path, commit_sha: str, path: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}:{path}"],
        cwd=repository_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def _git_is_ancestor(
    repository_root: Path, ancestor_sha: str, descendant_sha: str
) -> bool:
    _require_full_git_sha(ancestor_sha, "ancestor commit")
    _require_full_git_sha(descendant_sha, "descendant commit")
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha],
        cwd=repository_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError("unable to verify activation commit ancestry")
    return completed.returncode == 0


def _execution_worktree_clean(
    repository_root: Path, paths: tuple[str, ...]
) -> bool:
    status = _run_git(
        repository_root,
        ["status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
        text=True,
    )
    return not str(status).strip()


def _internal_import_paths(source: bytes) -> tuple[str, ...]:
    tree = ast.parse(source.decode("utf-8-sig"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(
        sorted(
            {
                "src/" + module.replace(".", "/") + ".py"
                for module in modules
                if module.startswith("mss.")
            }
        )
    )


def execution_file_paths(
    *,
    repository_root: Path,
    commit_sha: str,
) -> tuple[str, ...]:
    """Resolve the complete repository-local Python closure at one commit."""

    repository_root = Path(repository_root).resolve()
    commit_sha = _resolve_commit(repository_root, commit_sha)
    pending = list(EXECUTION_ROOT_PATHS)
    found: set[str] = set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        if not _git_path_exists(repository_root, commit_sha, path):
            raise RuntimeError(f"activation execution file missing at merge commit: {path}")
        found.add(path)
        for imported_path in _internal_import_paths(
            _git_blob(repository_root, commit_sha, path)
        ):
            if imported_path not in found and _git_path_exists(
                repository_root, commit_sha, imported_path
            ):
                pending.append(imported_path)

    found.update(Preregistration.PACKAGE_INITIALIZER_FILES)
    frozen_strategy_paths = set(Preregistration.REQUIRED_STRATEGY_COMPONENT_FILES)
    if not frozen_strategy_paths.issubset(found):
        missing = tuple(sorted(frozen_strategy_paths - found))
        raise RuntimeError(f"activation closure omitted frozen strategy files: {missing}")
    return tuple(sorted(found))


def execution_identity(
    *,
    repository_root: Path,
    commit_sha: str,
) -> tuple[tuple[str, str], ...]:
    repository_root = Path(repository_root).resolve()
    commit_sha = _resolve_commit(repository_root, commit_sha)
    return tuple(
        (
            path,
            hashlib.sha256(_git_blob(repository_root, commit_sha, path)).hexdigest(),
        )
        for path in execution_file_paths(
            repository_root=repository_root,
            commit_sha=commit_sha,
        )
    )


def _identity_records(
    identity: tuple[tuple[str, str], ...],
) -> list[dict[str, str]]:
    return [
        {"path": path, "git_blob_sha256": digest} for path, digest in identity
    ]


def build_activation_manifest_after_merge(
    *,
    repository_root: Path,
    public_pr_metadata: Mapping[str, object],
    manifest_created_at_utc: str,
    no_forward_outcome_access_verified: bool,
) -> dict[str, object]:
    """Build, but do not write, the manifest after the activation PR is merged."""

    if no_forward_outcome_access_verified is not True:
        raise RuntimeError("external no-forward-outcome-access proof is required")
    required_public = {"url", "number", "state", "mergedAt", "merge_commit_sha"}
    if not required_public.issubset(public_pr_metadata):
        raise RuntimeError("complete public activation PR metadata is required")
    if public_pr_metadata["state"] != "MERGED":
        raise RuntimeError("activation PR must already be merged")

    merge_sha = _require_full_git_sha(
        public_pr_metadata["merge_commit_sha"], "activation merge commit"
    )
    merged_at = _parse_utc_z(public_pr_metadata["mergedAt"], "activation mergedAt")
    created_at = _parse_utc_z(manifest_created_at_utc, "manifest creation")
    start_utc, end_utc = Preregistration.activation_window(
        str(public_pr_metadata["mergedAt"])
    )
    start_at = _parse_utc_z(start_utc, "computed activation start")
    if not (merged_at < created_at < start_at):
        raise RuntimeError(
            "manifest must be created after merge and before the activation boundary"
        )

    identity = execution_identity(
        repository_root=Path(repository_root), commit_sha=merge_sha
    )
    identity_map = dict(identity)
    candidate_strategy_records = _identity_records(
        tuple(
            item
            for item in identity
            if item[0] in Preregistration.REQUIRED_STRATEGY_COMPONENT_FILES
        )
    )
    baseline_strategy_records = [
        item.copy()
        for item in candidate_strategy_records
        if item["path"]
        != "src/mss/analysis/confluence_gated_smart_money_pipeline.py"
    ]
    for required_path in (
        PAIRED_EXECUTOR_PATH,
        EVALUATION_PATH,
        JOURNAL_PATH,
        RISK_PATH,
        VALUATION_PATH,
    ):
        if required_path not in identity_map:
            raise RuntimeError(f"required activation identity missing: {required_path}")

    runtime = observed_runtime_versions()
    record = lambda path: {
        "path": path,
        "git_blob_sha256": identity_map[path],
    }
    manifest: dict[str, object] = {
        "activation_pr_url": public_pr_metadata["url"],
        "activation_pr_number": public_pr_metadata["number"],
        "activation_pr_public_merged_at_utc": public_pr_metadata["mergedAt"],
        "activation_merge_commit_sha": merge_sha,
        "manifest_created_at_utc": manifest_created_at_utc,
        "python_version": runtime["python_version"],
        "numpy_version": runtime["numpy_version"],
        "paired_executor_identity": record(PAIRED_EXECUTOR_PATH),
        "baseline_strategy_identity": {
            "strategy_identifier": "BASELINE_SMART_MONEY_PIPELINE",
            "path_git_blob_sha256": baseline_strategy_records,
        },
        "candidate_strategy_identity": {
            "strategy_identifier": "CANDIDATE_CONFLUENCE_GATED_SMART_MONEY_PIPELINE",
            "path_git_blob_sha256": [
                item.copy() for item in candidate_strategy_records
            ],
        },
        "journal_implementation_identity": record(JOURNAL_PATH),
        "journal_schema_identity": {
            "schema_identifier": ShadowTradeJournal.VERSION,
            "implementation_path": JOURNAL_PATH,
            "git_blob_sha256": identity_map[JOURNAL_PATH],
        },
        "risk_implementation_identity": record(RISK_PATH),
        "valuation_implementation_identity": record(VALUATION_PATH),
        "evaluation_implementation_identity": record(EVALUATION_PATH),
        "complete_transitive_execution_file_identity": _identity_records(identity),
        "transitive_execution_file_universe_complete": True,
        "computed_first_eligible_m15_open_utc": start_utc,
        "computed_exclusive_45_day_end_utc": end_utc,
        "no_forward_outcome_access_before_activation": True,
        "all_data_before_computed_start_permanently_ineligible": True,
        "write_once": True,
    }
    if set(manifest) != set(Preregistration.ACTIVATION_MANIFEST_REQUIRED_FIELDS):
        raise RuntimeError("internal activation manifest field mismatch")

    # Structural preflight.  Actual commit/push times are supplied only during
    # post-publication verification; using creation time here makes no claim
    # that publication has already occurred.
    Preregistration.validate_activation_manifest(
        manifest,
        public_pr_metadata=public_pr_metadata,
        publication_metadata={
            "manifest_committed_at_utc": manifest_created_at_utc,
            "manifest_publicly_pushed_at_utc": manifest_created_at_utc,
        },
        runtime_versions=runtime,
        observed_execution_identity=identity,
        no_forward_outcome_access_verified=True,
        existing_manifest=None,
    )
    return manifest


def activation_manifest_path(repository_root: Path) -> Path:
    return Path(repository_root).resolve() / DEFAULT_MANIFEST_RELATIVE_PATH


def create_activation_manifest_once(
    *, repository_root: Path, manifest: Mapping[str, object]
) -> str:
    """Exclusively create a canonical manifest; replacement is never allowed."""

    if set(manifest) != set(Preregistration.ACTIVATION_MANIFEST_REQUIRED_FIELDS):
        raise RuntimeError("activation manifest must contain exactly the frozen fields")
    path = activation_manifest_path(repository_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json_bytes(dict(manifest))
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return hashlib.sha256(payload).hexdigest()


def _load_canonical_manifest(path: Path) -> tuple[dict[str, object], bytes]:
    raw = Path(path).read_bytes()
    normalised = _normalise_lf(raw)
    try:
        manifest = json.loads(normalised.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("activation manifest is not canonical UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("activation manifest must be a JSON object")
    canonical = _canonical_json_bytes(manifest)
    if normalised != canonical:
        raise RuntimeError("activation manifest bytes are not canonical")
    if set(manifest) != set(Preregistration.ACTIVATION_MANIFEST_REQUIRED_FIELDS):
        raise RuntimeError("activation manifest fields differ from the frozen contract")
    return manifest, canonical


@dataclass(frozen=True)
class VerifiedActivation:
    manifest_sha256: str
    activation_merge_commit_sha: str
    first_eligible_m15_open_utc: str
    exclusive_45_day_end_utc: str
    python_version: str
    numpy_version: str
    execution_identity: tuple[tuple[str, str], ...]
    real_order_send_allowed: bool = False
    order_check_allowed: bool = False
    production_execution_enabled: bool = False
    _verification_marker: object = None

    def require_eligible_decision(self, decision_candle_open_utc: str) -> None:
        decision = _parse_utc_z(decision_candle_open_utc, "decision candle open")
        start = _parse_utc_z(
            self.first_eligible_m15_open_utc, "computed activation start"
        )
        end = _parse_utc_z(self.exclusive_45_day_end_utc, "exclusive end")
        if int(decision.timestamp()) % TIMEFRAME_SECONDS:
            raise RuntimeError("decision candle must be aligned to M15")
        if decision < start:
            raise RuntimeError("pre-activation candle is permanently ineligible")
        if decision >= end:
            raise RuntimeError("decision candle is outside the exclusive experiment end")


def verify_published_activation_manifest(
    *,
    manifest_path: Path,
    repository_root: Path,
    public_pr_metadata: Mapping[str, object],
    publication_metadata: Mapping[str, object],
    no_forward_outcome_access_verified: bool,
) -> VerifiedActivation:
    """Fully verify a committed/pushed manifest and the code running it."""

    manifest_path = Path(manifest_path).resolve()
    repository_root = Path(repository_root).resolve()
    if manifest_path != activation_manifest_path(repository_root):
        raise RuntimeError("activation manifest path differs from the frozen path")
    try:
        manifest_relative_path = manifest_path.relative_to(repository_root).as_posix()
    except ValueError as exc:
        raise RuntimeError("activation manifest must be inside the repository") from exc

    manifest, canonical = _load_canonical_manifest(manifest_path)
    merge_sha = _require_full_git_sha(
        manifest["activation_merge_commit_sha"], "activation merge commit"
    )
    expected_manifest = build_activation_manifest_after_merge(
        repository_root=repository_root,
        public_pr_metadata=public_pr_metadata,
        manifest_created_at_utc=str(manifest["manifest_created_at_utc"]),
        no_forward_outcome_access_verified=no_forward_outcome_access_verified,
    )
    if manifest != expected_manifest:
        raise RuntimeError("activation manifest differs from the executable frozen build")
    merge_identity = execution_identity(
        repository_root=repository_root, commit_sha=merge_sha
    )
    head_sha = _resolve_commit(repository_root, "HEAD")
    head_identity = execution_identity(
        repository_root=repository_root, commit_sha=head_sha
    )
    if head_identity != merge_identity:
        raise RuntimeError("running execution source differs from frozen activation identity")

    manifest_commit_sha = _require_full_git_sha(
        publication_metadata.get("manifest_commit_sha"), "manifest commit"
    )
    if not _git_is_ancestor(repository_root, merge_sha, manifest_commit_sha):
        raise RuntimeError("manifest commit does not descend from the activation merge")
    if not _git_is_ancestor(repository_root, manifest_commit_sha, head_sha):
        raise RuntimeError("running checkout does not contain the manifest commit")
    committed_manifest = _normalise_lf(
        _git_blob(repository_root, manifest_commit_sha, manifest_relative_path)
    )
    if committed_manifest != canonical:
        raise RuntimeError("working manifest differs from its committed Git blob")
    manifest_commit_identity = execution_identity(
        repository_root=repository_root, commit_sha=manifest_commit_sha
    )
    if manifest_commit_identity != merge_identity:
        raise RuntimeError("manifest commit changed the frozen execution identity")
    if not _execution_worktree_clean(
        repository_root, tuple(path for path, _digest in merge_identity)
    ):
        raise RuntimeError("running execution source has uncommitted changes")

    runtime = observed_runtime_versions()
    Preregistration.validate_activation_manifest(
        manifest,
        public_pr_metadata=public_pr_metadata,
        publication_metadata=publication_metadata,
        runtime_versions=runtime,
        observed_execution_identity=merge_identity,
        no_forward_outcome_access_verified=no_forward_outcome_access_verified,
        existing_manifest=None,
    )
    return VerifiedActivation(
        manifest_sha256=hashlib.sha256(canonical).hexdigest(),
        activation_merge_commit_sha=merge_sha,
        first_eligible_m15_open_utc=str(
            manifest["computed_first_eligible_m15_open_utc"]
        ),
        exclusive_45_day_end_utc=str(
            manifest["computed_exclusive_45_day_end_utc"]
        ),
        python_version=str(manifest["python_version"]),
        numpy_version=str(manifest["numpy_version"]),
        execution_identity=merge_identity,
        _verification_marker=_VERIFIED_ACTIVATION_MARKER,
    )


@dataclass(frozen=True)
class _FrozenRate:
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


@dataclass(frozen=True)
class EvidenceWriteResult:
    appended: bool
    event_id: str
    event_sequence: int
    event_sha256: str


@dataclass(frozen=True)
class PairedDecisionResult:
    write: EvidenceWriteResult
    pair_key: tuple[str, str]
    input_snapshot_sha256: str
    baseline_decision_identity: str
    candidate_decision_identity: str
    baseline_position_id: str
    candidate_position_id: str
    baseline_frozen_signal: object
    candidate_frozen_signal: object


@dataclass(frozen=True)
class PairedEntryResult:
    write: EvidenceWriteResult
    pair_key: tuple[str, str]
    baseline_position: VirtualPosition | None
    candidate_position: VirtualPosition | None


@dataclass(frozen=True)
class VirtualTradeUpdateResult:
    branch: str
    action: str
    position: VirtualPosition | None
    terminal_write: EvidenceWriteResult | None = None


@dataclass(frozen=True)
class BranchEntryOutcome:
    actual_trade_opened: bool
    reason: str
    position_id: str | None = None

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("entry outcome reason is required")
        if self.actual_trade_opened:
            if not self.position_id:
                raise ValueError("an actual virtual trade requires a position identity")
        elif self.position_id is not None:
            raise ValueError("a no-trade outcome cannot carry a position identity")


@dataclass(frozen=True)
class BranchSettlement:
    actual_trade: bool
    net_r: float | None
    settlement_utc: str | None
    timebox_mtm: bool = False
    valuation_snapshot_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.actual_trade:
            if (
                self.net_r is not None
                or self.settlement_utc is not None
                or self.timebox_mtm
                or self.valuation_snapshot_sha256 is not None
            ):
                raise ValueError("no-trade settlement fields must be null")
            return
        if isinstance(self.net_r, bool) or not isinstance(self.net_r, (int, float)):
            raise ValueError("actual trade requires numeric net R")
        if not math.isfinite(float(self.net_r)):
            raise ValueError("actual trade net R must be finite")
        if not self.settlement_utc:
            raise ValueError("actual trade requires settlement UTC")
        _parse_utc_z(self.settlement_utc, "terminal settlement")
        if self.timebox_mtm:
            Preregistration._require_sha256(
                self.valuation_snapshot_sha256, "timebox valuation snapshot"
            )
        elif self.valuation_snapshot_sha256 is not None:
            raise ValueError("only timebox MTM may carry a valuation snapshot")


@dataclass(frozen=True)
class EvidenceRecovery:
    decision_pair_keys: tuple[tuple[str, str], ...]
    pending_entry_pair_keys: tuple[tuple[str, str], ...]
    open_pair_keys: tuple[tuple[str, str], ...]
    settled_pair_keys: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TimeboxCloseResult:
    closed_position: VirtualPosition
    settlement: BranchSettlement
    terminal_write: EvidenceWriteResult | None = None


def _rate_value(rate: object, name: str) -> object:
    if isinstance(rate, Mapping):
        return rate[name]
    return getattr(rate, name)


def _freeze_rates(
    rates: object, *, current_bar_epoch: int
) -> tuple[_FrozenRate, ...]:
    if rates is None:
        raise RuntimeError("paired rates snapshot is required")
    frozen: list[_FrozenRate] = []
    for rate in rates:
        item = _FrozenRate(
            time=int(_rate_value(rate, "time")),
            open=float(_rate_value(rate, "open")),
            high=float(_rate_value(rate, "high")),
            low=float(_rate_value(rate, "low")),
            close=float(_rate_value(rate, "close")),
            tick_volume=int(_rate_value(rate, "tick_volume")),
            spread=int(_rate_value(rate, "spread")),
            real_volume=int(_rate_value(rate, "real_volume")),
        )
        if not all(
            math.isfinite(value)
            for value in (item.open, item.high, item.low, item.close)
        ):
            raise RuntimeError("paired rates snapshot contains non-finite price")
        frozen.append(item)
    if not frozen:
        raise RuntimeError("paired rates snapshot is empty")
    epochs = tuple(item.time for item in frozen)
    if epochs != tuple(sorted(epochs)) or len(epochs) != len(set(epochs)):
        raise RuntimeError("paired rates snapshot must be strictly ordered and unique")
    if epochs[-1] != int(current_bar_epoch):
        raise RuntimeError("paired rates snapshot must end at the current broker bar")
    if any(epoch > int(current_bar_epoch) for epoch in epochs):
        raise RuntimeError("paired rates snapshot contains a future broker bar")
    return tuple(frozen)


def _time_authority_offset(
    time_authority: Mapping[str, object],
    *,
    expected_current_bar_epoch: int | None = None,
    expected_tick_epoch: int | None = None,
    require_current: bool = True,
) -> int:
    try:
        authority = time_authority["time_authority"]
        observation = time_authority["observation"]
        fail_safe = time_authority["fail_safe"]
        confirmed = authority["confirmed"]
        status = authority["status"]
        offset = observation["detected_broker_offset_seconds"]
        current_bar_epoch = observation["mt5_raw_current_m15_bar_epoch"]
        tick_epoch = observation["mt5_raw_tick_epoch"]
        utc_before_tick = observation["utc_epoch_before_tick"]
        utc_after_tick = observation["utc_epoch_after_tick"]
        utc_midpoint = observation["utc_midpoint_epoch"]
        offset_plausible = observation["offset_plausible"]
        tick_fresh_enough = observation["tick_fresh_enough"]
        bar_matches = observation["bar_matches_broker_clock"]
        bar_aligned = observation["bar_m15_aligned"]
        trading_allowed = fail_safe["trading_allowed_by_time_authority"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("complete GlobalTimeAuthority evidence is required") from exc
    if time_authority.get("schema_version") != GlobalTimeAuthority.VERSION:
        raise RuntimeError("GlobalTimeAuthority schema identity mismatch")
    if (
        confirmed is not True
        or status != "BROKER_TIME_DOMAIN_CONFIRMED"
        or trading_allowed is not True
        or offset_plausible is not True
        or tick_fresh_enough is not True
        or bar_matches is not True
        or bar_aligned is not True
    ):
        raise RuntimeError("broker time authority must be confirmed")
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise RuntimeError("broker UTC offset must be an integer")
    if offset % GlobalTimeAuthority.OFFSET_GRID_SECONDS:
        raise RuntimeError("broker UTC offset is not on the frozen authority grid")
    if abs(offset) > GlobalTimeAuthority.MAX_ABS_OFFSET_SECONDS:
        raise RuntimeError("broker UTC offset is outside the plausible range")
    if isinstance(current_bar_epoch, bool) or not isinstance(current_bar_epoch, int):
        raise RuntimeError("time authority current bar epoch must be an integer")
    if isinstance(tick_epoch, bool) or not isinstance(tick_epoch, int):
        raise RuntimeError("time authority tick epoch must be an integer")
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (utc_before_tick, utc_after_tick, utc_midpoint)
    ):
        raise RuntimeError("time authority UTC observation must be numeric")
    if not (
        float(utc_before_tick)
        <= float(utc_midpoint)
        <= float(utc_after_tick)
    ):
        raise RuntimeError("time authority UTC observation order is invalid")
    if require_current and abs(_utc_now_epoch() - float(utc_midpoint)) > (
        GlobalTimeAuthority.MAX_TICK_RESIDUAL_SECONDS
    ):
        raise RuntimeError("time authority evidence is stale")
    if current_bar_epoch % TIMEFRAME_SECONDS:
        raise RuntimeError("time authority current bar is not M15 aligned")
    if current_bar_epoch != (tick_epoch // TIMEFRAME_SECONDS) * TIMEFRAME_SECONDS:
        raise RuntimeError("time authority current bar does not match its tick")
    if (
        expected_current_bar_epoch is not None
        and current_bar_epoch != int(expected_current_bar_epoch)
    ):
        raise RuntimeError("time authority is not bound to the supplied current bar")
    if expected_tick_epoch is not None and tick_epoch != int(expected_tick_epoch):
        raise RuntimeError("time authority is not bound to the supplied settlement tick")
    return offset


def _event_id(
    *,
    manifest_sha256: str,
    pair_key: tuple[str, str],
    phase: str,
) -> str:
    return _canonical_sha256(
        {
            "manifest_sha256": manifest_sha256,
            "pair_key": list(pair_key),
            "phase": phase,
        }
    )


def _write_result(event: Mapping[str, object], appended: bool) -> EvidenceWriteResult:
    payload = event["payload"]
    return EvidenceWriteResult(
        appended=appended,
        event_id=str(payload["sprint93_2b_event_id"]),
        event_sequence=int(event["event_sequence"]),
        event_sha256=str(event["event_sha256"]),
    )


def _append_evidence_once_unlocked(
    *,
    journal_path: Path,
    event_type: str,
    event_id: str,
    broker_epoch: int,
    payload: dict[str, object],
) -> EvidenceWriteResult:
    desired = {
        "event_type": event_type,
        "position_id": event_id,
        "broker_epoch": int(broker_epoch),
        "payload": payload,
    }
    verified = ShadowTradeJournal.verify(journal_path)
    if not verified["valid"]:
        raise RuntimeError(
            f"paired evidence journal integrity failure: {verified['reason']}"
        )
    matches = []
    for event in ShadowTradeJournal._read_events(Path(journal_path)):
        event_payload = event.get("payload")
        if (
            isinstance(event_payload, dict)
            and event_payload.get("sprint93_2b_event_id") == event_id
        ):
            matches.append(event)
    if len(matches) > 1:
        raise RuntimeError("duplicate evidence identity already exists in journal")
    if matches:
        existing = matches[0]
        existing_material = {
            "event_type": existing.get("event_type"),
            "position_id": existing.get("position_id"),
            "broker_epoch": existing.get("broker_epoch"),
            "payload": existing.get("payload"),
        }
        if _canonical_json_bytes(existing_material) != _canonical_json_bytes(desired):
            raise RuntimeError("conflicting duplicate paired evidence identity")
        return _write_result(existing, appended=False)
    event = ShadowTradeJournal._append_event_unlocked(
        path=journal_path,
        event_type=event_type,
        position_id=event_id,
        broker_epoch=int(broker_epoch),
        payload=payload,
    )
    return _write_result(event, appended=True)


def _append_evidence_once(
    *,
    journal_path: Path,
    event_type: str,
    event_id: str,
    broker_epoch: int,
    payload: dict[str, object],
) -> EvidenceWriteResult:
    with ShadowTradeJournal.exclusive_transaction(journal_path):
        return _append_evidence_once_unlocked(
            journal_path=journal_path,
            event_type=event_type,
            event_id=event_id,
            broker_epoch=broker_epoch,
            payload=payload,
        )


class PairedForwardEvidenceCollector:
    """Pair-only orchestrator; all trading remains virtual and external."""

    real_order_send_allowed = False
    order_check_allowed = False
    production_execution_enabled = False

    def __init__(
        self,
        *,
        activation: VerifiedActivation,
        journal_path: Path,
        baseline_engine: object | None = None,
        candidate_engine: object | None = None,
        real_order_send_allowed: bool = False,
        order_check_allowed: bool = False,
        production_execution_enabled: bool = False,
    ) -> None:
        if not isinstance(activation, VerifiedActivation):
            raise TypeError("a verified activation context is required")
        if activation._verification_marker is not _VERIFIED_ACTIVATION_MARKER:
            raise RuntimeError("activation context was not produced by manifest verification")
        if (
            real_order_send_allowed is not False
            or order_check_allowed is not False
            or production_execution_enabled is not False
        ):
            raise RuntimeError("paired forward collection is shadow-only")
        if (
            activation.real_order_send_allowed
            or activation.order_check_allowed
            or activation.production_execution_enabled
        ):
            raise RuntimeError("activation context permits prohibited execution")
        self.activation = activation
        self.journal_path = Path(journal_path)
        self.baseline_engine = baseline_engine or LiveCompletedCandleSignalEngine(
            pipeline=SmartMoneyPipeline()
        )
        self.candidate_engine = candidate_engine or LiveCompletedCandleSignalEngine(
            pipeline=ConfluenceGatedSmartMoneyPipeline()
        )
        self.recover()

    def _events(self) -> list[dict[str, Any]]:
        verified = ShadowTradeJournal.verify(self.journal_path)
        if not verified["valid"]:
            raise RuntimeError(
                f"paired evidence journal integrity failure: {verified['reason']}"
            )
        return ShadowTradeJournal._read_events(self.journal_path)

    def _phase_events(self) -> dict[tuple[tuple[str, str], str], dict[str, Any]]:
        indexed: dict[tuple[tuple[str, str], str], dict[str, Any]] = {}
        seen_ids: set[str] = set()
        for event in self._events():
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("activation_manifest_sha256") != self.activation.manifest_sha256:
                continue
            event_id = payload.get("sprint93_2b_event_id")
            phase = payload.get("phase")
            pair = payload.get("pair_key")
            if event_id is None:
                continue
            if not isinstance(event_id, str) or event_id in seen_ids:
                raise RuntimeError("duplicate or invalid recovered evidence identity")
            seen_ids.add(event_id)
            if phase not in EVIDENCE_EVENT_TYPES or not (
                isinstance(pair, list)
                and len(pair) == 2
                and all(isinstance(value, str) and value for value in pair)
            ):
                raise RuntimeError("malformed Sprint 93.2B evidence payload")
            pair_key = (pair[0], pair[1])
            expected_id = _event_id(
                manifest_sha256=self.activation.manifest_sha256,
                pair_key=pair_key,
                phase=phase,
            )
            if event_id != expected_id:
                raise RuntimeError("recovered evidence identity mismatch")
            key = (pair_key, phase)
            if key in indexed:
                raise RuntimeError("duplicate recovered pair phase")
            indexed[key] = event
        return indexed

    def recover(self) -> EvidenceRecovery:
        indexed = self._phase_events()
        decisions = {pair for pair, phase in indexed if phase == "decision"}
        entries = {pair for pair, phase in indexed if phase == "entry"}
        settlements = {pair for pair, phase in indexed if phase == "settlement"}
        if not entries.issubset(decisions) or not settlements.issubset(entries):
            raise RuntimeError("paired evidence lifecycle is not append-order consistent")
        open_pairs = set()
        for pair in entries - settlements:
            payload = indexed[(pair, "entry")]["payload"]
            branches = payload.get("branches", {})
            if any(
                bool(branches.get(name, {}).get("is_actual_trade"))
                and (pair, f"terminal_{name}") not in indexed
                for name in ("baseline", "candidate")
            ):
                open_pairs.add(pair)
        return EvidenceRecovery(
            decision_pair_keys=tuple(sorted(decisions)),
            pending_entry_pair_keys=tuple(sorted(decisions - entries)),
            open_pair_keys=tuple(sorted(open_pairs)),
            settled_pair_keys=tuple(sorted(settlements)),
        )

    def _event_for(self, pair_key: tuple[str, str], phase: str) -> dict[str, Any]:
        event = self._phase_events().get((pair_key, phase))
        if event is None:
            raise RuntimeError(f"paired {phase} evidence is required first")
        return event

    def virtual_position_id(self, pair_key: tuple[str, str], branch: str) -> str:
        if branch not in {"baseline", "candidate"}:
            raise ValueError("virtual position branch must be baseline or candidate")
        digest = _canonical_sha256(
            {
                "activation_manifest_sha256": self.activation.manifest_sha256,
                "pair_key": list(pair_key),
                "branch": branch,
                "identity": "VIRTUAL_POSITION",
            }
        )
        return f"s93b-{branch}-{digest[:32]}"

    def trade_journal_path(self, pair_key: tuple[str, str], branch: str) -> Path:
        position_id = self.virtual_position_id(pair_key, branch)
        return (
            self.journal_path.parent
            / "virtual_positions"
            / position_id
            / "shadow_position.jsonl"
        )

    def _trade_events(
        self, pair_key: tuple[str, str], branch: str
    ) -> list[dict[str, Any]]:
        path = self.trade_journal_path(pair_key, branch)
        verified = ShadowTradeJournal.verify(path)
        if not verified["valid"]:
            raise RuntimeError(
                f"{branch} virtual trade journal integrity failure: "
                f"{verified['reason']}"
            )
        expected_position_id = self.virtual_position_id(pair_key, branch)
        events = ShadowTradeJournal._read_events(path)
        for event in events:
            if event.get("position_id") != expected_position_id:
                raise RuntimeError(f"{branch} trade journal position identity mismatch")
            audit = event.get("audit", {})
            if not (
                audit.get("shadow_only") is True
                and audit.get("real_order_send_allowed") is False
                and audit.get("order_send_called") is False
                and audit.get("order_check_called") is False
            ):
                raise RuntimeError(f"{branch} trade journal safety audit failed")
        return events

    def _recover_position(
        self, pair_key: tuple[str, str], branch: str
    ) -> VirtualPosition | None:
        path = self.trade_journal_path(pair_key, branch)
        recovered = ShadowPositionRecovery.recover(path)
        if not recovered.valid:
            raise RuntimeError(f"{branch} virtual position recovery failed: {recovered.reason}")
        if recovered.position is not None and recovered.position.position_id != (
            self.virtual_position_id(pair_key, branch)
        ):
            raise RuntimeError(f"{branch} recovered position identity mismatch")
        return recovered.position

    def _closed_trade_event(
        self, pair_key: tuple[str, str], branch: str
    ) -> dict[str, Any] | None:
        closed = [
            event
            for event in self._trade_events(pair_key, branch)
            if event.get("event_type") == "POSITION_CLOSED"
        ]
        if len(closed) > 1:
            raise RuntimeError(f"{branch} position has multiple terminal events")
        return closed[0] if closed else None

    def _closed_position(
        self, pair_key: tuple[str, str], branch: str
    ) -> VirtualPosition | None:
        events = self._trade_events(pair_key, branch)
        opened = [event for event in events if event.get("event_type") == "POSITION_OPENED"]
        closed = [event for event in events if event.get("event_type") == "POSITION_CLOSED"]
        if not closed:
            return None
        if len(opened) != 1 or len(closed) != 1:
            raise RuntimeError(f"{branch} closed position lifecycle is ambiguous")
        open_payload = opened[0]["payload"]
        close_payload = closed[0]["payload"]
        return VirtualPosition(
            position_id=self.virtual_position_id(pair_key, branch),
            symbol=str(open_payload["symbol"]),
            direction=str(open_payload["direction"]),
            volume=float(open_payload["volume"]),
            entry_price=float(open_payload["entry_price"]),
            stop_loss=float(open_payload["stop_loss"]),
            take_profit=float(open_payload["take_profit"]),
            initial_risk_price=float(open_payload["initial_risk_price"]),
            open_broker_epoch=int(opened[0]["broker_epoch"]),
            close_broker_epoch=int(closed[0]["broker_epoch"]),
            status="CLOSED",
            exit_reason=str(close_payload["exit_reason"]),
            close_price=float(close_payload["close_price"]),
            pnl_account_currency=float(close_payload["pnl_account_currency"]),
            r_multiple=float(close_payload["r_multiple"]),
            valid=True,
            real_order_send_allowed=False,
        )

    def collect_decision(
        self,
        *,
        canonical_symbol: str,
        decision_candle_open_utc: str,
        current_bar_epoch: int,
        rates: object,
        time_authority: Mapping[str, object],
    ) -> PairedDecisionResult:
        if canonical_symbol not in SYMBOL_MAP:
            raise RuntimeError("canonical symbol is outside the frozen pair universe")
        self.activation.require_eligible_decision(decision_candle_open_utc)
        offset = _time_authority_offset(
            time_authority,
            expected_current_bar_epoch=int(current_bar_epoch),
        )
        decision_utc_epoch = _epoch_from_utc_z(
            decision_candle_open_utc, "decision candle open"
        )
        expected_signal_epoch = decision_utc_epoch + offset
        if int(current_bar_epoch) != expected_signal_epoch + TIMEFRAME_SECONDS:
            raise RuntimeError("current broker bar is not the next M15 entry bar")
        current_utc_epoch = int(current_bar_epoch) - offset
        exclusive_end_epoch = _epoch_from_utc_z(
            self.activation.exclusive_45_day_end_utc, "exclusive end"
        )
        if current_utc_epoch >= exclusive_end_epoch:
            raise RuntimeError("new entries are prohibited at or after the exclusive end")

        frozen_rates = _freeze_rates(
            rates, current_bar_epoch=int(current_bar_epoch)
        )
        snapshot_records = [asdict(rate) for rate in frozen_rates]
        snapshot_sha = _canonical_sha256(snapshot_records)
        broker_symbol = SYMBOL_MAP[canonical_symbol]

        # The exact same immutable tuple is supplied to both engines.
        baseline = self.baseline_engine.evaluate(
            symbol=broker_symbol,
            rates=frozen_rates,
            current_bar_epoch=int(current_bar_epoch),
        )
        candidate = self.candidate_engine.evaluate(
            symbol=broker_symbol,
            rates=frozen_rates,
            current_bar_epoch=int(current_bar_epoch),
        )
        for branch_name, decision in (("baseline", baseline), ("candidate", candidate)):
            if not getattr(decision, "valid", False):
                raise RuntimeError(
                    f"{branch_name} completed-candle decision blocked: "
                    f"{getattr(decision, 'reason', 'UNKNOWN')}"
                )
            if int(getattr(decision, "signal_bar_epoch", 0)) != expected_signal_epoch:
                raise RuntimeError(f"{branch_name} signal bar differs from the frozen pair key")

        baseline_trade = bool(
            getattr(getattr(baseline, "frozen_signal", None), "valid", False)
        )
        candidate_trade = bool(
            getattr(getattr(candidate, "frozen_signal", None), "valid", False)
        )
        candidate_result = getattr(candidate, "pipeline_result", None)
        candidate_rejected = bool(
            getattr(candidate_result, "confluence_gate_rejected", False)
        )
        if candidate_trade and not baseline_trade:
            raise RuntimeError("candidate cannot create a trade absent in the baseline")
        if candidate_rejected and candidate_trade:
            raise RuntimeError("rejected candidate cannot remain trade-eligible")

        baseline_identity = "BASELINE_TRADE" if baseline_trade else "BASELINE_NO_TRADE"
        if candidate_rejected:
            candidate_identity = "REJECTED_CANDIDATE"
        else:
            candidate_identity = (
                "CANDIDATE_TRADE" if candidate_trade else "CANDIDATE_NO_TRADE"
            )
        pair_key = (canonical_symbol, decision_candle_open_utc)
        baseline_position_id = self.virtual_position_id(pair_key, "baseline")
        candidate_position_id = self.virtual_position_id(pair_key, "candidate")
        event_id = _event_id(
            manifest_sha256=self.activation.manifest_sha256,
            pair_key=pair_key,
            phase="decision",
        )

        def branch_payload(
            decision: object, identity: str, position_id: str
        ) -> dict[str, object]:
            frozen_signal = getattr(decision, "frozen_signal", None)
            pipeline_result = getattr(decision, "pipeline_result", None)
            return {
                "decision_identity": identity,
                "prospective_virtual_position_id": position_id,
                "input_snapshot_sha256": snapshot_sha,
                "completed_candle_count": int(
                    getattr(decision, "completed_candle_count", 0)
                ),
                "pipeline_valid": bool(getattr(pipeline_result, "valid", False)),
                "bos_detected": bool(getattr(pipeline_result, "bos_detected", False)),
                "bos_direction": str(getattr(pipeline_result, "bos_direction", "")),
                "confluence_valid": bool(
                    getattr(pipeline_result, "confluence_valid", False)
                ),
                "confluence_signal": str(
                    getattr(pipeline_result, "confluence_signal", "")
                ),
                "confluence_gate_rejected": bool(
                    getattr(pipeline_result, "confluence_gate_rejected", False)
                ),
                "decision_reason": str(getattr(decision, "reason", "")),
                "frozen_signal": asdict(frozen_signal) if frozen_signal is not None else None,
            }

        payload: dict[str, object] = {
            "schema_version": VERSION,
            "phase": "decision",
            "sprint93_2b_event_id": event_id,
            "activation_manifest_sha256": self.activation.manifest_sha256,
            "activation_merge_commit_sha": self.activation.activation_merge_commit_sha,
            "pair_key": list(pair_key),
            "canonical_symbol": canonical_symbol,
            "broker_symbol": broker_symbol,
            "timeframe": TIMEFRAME,
            "broker_utc_offset_seconds": offset,
            "input_snapshot_sha256": snapshot_sha,
            "input_snapshot_record_count": len(frozen_rates),
            "input_snapshot_first_broker_epoch": frozen_rates[0].time,
            "input_snapshot_last_broker_epoch": frozen_rates[-1].time,
            "current_bar_broker_epoch": int(current_bar_epoch),
            "input_snapshot": snapshot_records,
            "global_time_authority": dict(time_authority),
            "collected_at_utc": _render_utc_z(
                datetime.fromtimestamp(
                    float(time_authority["observation"]["utc_midpoint_epoch"]),
                    timezone.utc,
                )
            ),
            "branches": {
                "baseline": branch_payload(
                    baseline, baseline_identity, baseline_position_id
                ),
                "candidate": branch_payload(
                    candidate, candidate_identity, candidate_position_id
                ),
            },
            "safety": {
                "shadow_only": True,
                "real_order_send_allowed": False,
                "order_check_allowed": False,
                "production_execution_enabled": False,
            },
        }
        write = _append_evidence_once(
            journal_path=self.journal_path,
            event_type=EVIDENCE_EVENT_TYPES["decision"],
            event_id=event_id,
            broker_epoch=expected_signal_epoch,
            payload=payload,
        )
        return PairedDecisionResult(
            write=write,
            pair_key=pair_key,
            input_snapshot_sha256=snapshot_sha,
            baseline_decision_identity=baseline_identity,
            candidate_decision_identity=candidate_identity,
            baseline_position_id=baseline_position_id,
            candidate_position_id=candidate_position_id,
            baseline_frozen_signal=getattr(baseline, "frozen_signal", None),
            candidate_frozen_signal=getattr(candidate, "frozen_signal", None),
        )

    def open_virtual_entries(
        self,
        *,
        pair_key: tuple[str, str],
        balance: float,
        point: float,
        time_authority: Mapping[str, object],
    ) -> PairedEntryResult:
        """Activate and risk-size both branches through the frozen shadow engine."""

        if not math.isfinite(float(balance)) or float(balance) <= 0:
            raise RuntimeError("positive finite balance is required")
        if not math.isfinite(float(point)) or float(point) <= 0:
            raise RuntimeError("positive finite point is required")

        with ShadowTradeJournal.exclusive_transaction(self.journal_path):
            existing_entry = self._phase_events().get((pair_key, "entry"))
            if existing_entry is not None:
                branches = existing_entry["payload"]["branches"]
                return PairedEntryResult(
                    write=_write_result(existing_entry, appended=False),
                    pair_key=pair_key,
                    baseline_position=(
                        self._recover_position(pair_key, "baseline")
                        if branches["baseline"]["is_actual_trade"]
                        else None
                    ),
                    candidate_position=(
                        self._recover_position(pair_key, "candidate")
                        if branches["candidate"]["is_actual_trade"]
                        else None
                    ),
                )

            decision_event = self._event_for(pair_key, "decision")
            decision_payload = decision_event["payload"]
            entry_broker_epoch = int(decision_payload["current_bar_broker_epoch"])
            current_rows = [
                row
                for row in decision_payload["input_snapshot"]
                if int(row["time"]) == entry_broker_epoch
            ]
            if len(current_rows) != 1:
                raise RuntimeError("decision evidence lacks one exact entry-bar snapshot")
            current_rate = current_rows[0]
            branches = decision_payload["branches"]

            entry_input_event = self._phase_events().get((pair_key, "entry_input"))
            if entry_input_event is not None:
                frozen_input = entry_input_event["payload"]
                balance = float(frozen_input["balance"])
                point = float(frozen_input["point"])
                time_authority = frozen_input["global_time_authority"]
                if int(entry_input_event["broker_epoch"]) != entry_broker_epoch:
                    raise RuntimeError("frozen entry input broker epoch mismatch")
                authority_current = True
                try:
                    _time_authority_offset(
                        time_authority,
                        expected_current_bar_epoch=entry_broker_epoch,
                    )
                except RuntimeError:
                    _time_authority_offset(
                        time_authority,
                        expected_current_bar_epoch=entry_broker_epoch,
                        require_current=False,
                    )
                    authority_current = False
            else:
                try:
                    _time_authority_offset(
                        time_authority,
                        expected_current_bar_epoch=entry_broker_epoch,
                    )
                    if _canonical_json_bytes(time_authority) != _canonical_json_bytes(
                        decision_payload["global_time_authority"]
                    ):
                        raise RuntimeError(
                            "entry must use the same frozen time-authority snapshot as decision"
                        )
                    authority_current = True
                except RuntimeError:
                    # The timely decision remains auditable, but no virtual entry may
                    # be reconstructed after its next-bar window has passed.
                    baseline_outcome = BranchEntryOutcome(
                        False, "RESTART_AFTER_ENTRY_WINDOW"
                    )
                    candidate_outcome = BranchEntryOutcome(
                        False, "RESTART_AFTER_ENTRY_WINDOW"
                    )
                    write = self.record_entry_outcome(
                        pair_key=pair_key,
                        baseline=baseline_outcome,
                        candidate=candidate_outcome,
                        entry_broker_epoch=entry_broker_epoch,
                        time_authority=decision_payload["global_time_authority"],
                        entry_evidence={
                            "entry_input_event_sha256": None,
                            "reason": "RESTART_AFTER_ENTRY_WINDOW",
                            "input_snapshot_sha256": decision_payload[
                                "input_snapshot_sha256"
                            ],
                        },
                        _require_current_authority=False,
                        _lock_held=True,
                    )
                    return PairedEntryResult(
                        write=write,
                        pair_key=pair_key,
                        baseline_position=None,
                        candidate_position=None,
                    )

            def activate_branch(branch: str) -> dict[str, object]:
                branch_payload = branches[branch]
                expected_trade = (
                    "BASELINE_TRADE" if branch == "baseline" else "CANDIDATE_TRADE"
                )
                if branch_payload["decision_identity"] != expected_trade:
                    return {
                        "valid": False,
                        "reason": str(branch_payload["decision_identity"]),
                    }
                signal_payload = branch_payload.get("frozen_signal")
                if not isinstance(signal_payload, dict):
                    raise RuntimeError(f"{branch} frozen signal evidence is missing")
                signal = FrozenShadowSignal(**signal_payload)
                return asdict(
                    FrozenShadowStrategyAdapter.activate_entry(
                        signal=signal,
                        entry_bar_epoch=entry_broker_epoch,
                        next_candle_sequence_confirmed=True,
                        next_candle_open=float(current_rate["open"]),
                        spread_points=float(current_rate["spread"]),
                        point=float(point),
                    )
                )

            activated_entries = {
                "baseline": activate_branch("baseline"),
                "candidate": activate_branch("candidate"),
            }
            if entry_input_event is None:
                phase = "entry_input"
                input_event_id = _event_id(
                    manifest_sha256=self.activation.manifest_sha256,
                    pair_key=pair_key,
                    phase=phase,
                )
                input_payload = {
                    "schema_version": VERSION,
                    "phase": phase,
                    "sprint93_2b_event_id": input_event_id,
                    "activation_manifest_sha256": self.activation.manifest_sha256,
                    "activation_merge_commit_sha": (
                        self.activation.activation_merge_commit_sha
                    ),
                    "pair_key": list(pair_key),
                    "balance": float(balance),
                    "point": float(point),
                    "entry_bar": dict(current_rate),
                    "input_snapshot_sha256": decision_payload[
                        "input_snapshot_sha256"
                    ],
                    "activated_entries": activated_entries,
                    "global_time_authority": dict(time_authority),
                    "safety": {
                        "shadow_only": True,
                        "real_order_send_allowed": False,
                        "order_check_allowed": False,
                        "production_execution_enabled": False,
                    },
                }
                _append_evidence_once_unlocked(
                    journal_path=self.journal_path,
                    event_type=EVIDENCE_EVENT_TYPES[phase],
                    event_id=input_event_id,
                    broker_epoch=entry_broker_epoch,
                    payload=input_payload,
                )
                entry_input_event = self._event_for(pair_key, phase)
            else:
                if _canonical_json_bytes(activated_entries) != _canonical_json_bytes(
                    entry_input_event["payload"]["activated_entries"]
                ):
                    raise RuntimeError("recomputed frozen entries differ from entry intent")

            def open_branch(
                branch: str,
                *,
                baseline_opened: bool,
            ) -> tuple[BranchEntryOutcome, VirtualPosition | None, dict[str, object]]:
                branch_payload = branches[branch]
                decision_identity = branch_payload["decision_identity"]
                trade_identity = (
                    "BASELINE_TRADE" if branch == "baseline" else "CANDIDATE_TRADE"
                )
                if decision_identity != trade_identity:
                    return (
                        BranchEntryOutcome(False, str(decision_identity)),
                        None,
                        {"entry_valid": False, "entry_reason": str(decision_identity)},
                    )
                if branch == "candidate" and not baseline_opened:
                    return (
                        BranchEntryOutcome(False, "BASELINE_ENTRY_NOT_OPENED"),
                        None,
                        {
                            "entry_valid": False,
                            "entry_reason": "BASELINE_ENTRY_NOT_OPENED",
                        },
                    )
                entry_identity = activated_entries[branch]
                if not entry_identity["valid"]:
                    return (
                        BranchEntryOutcome(False, str(entry_identity["reason"])),
                        None,
                        entry_identity,
                    )

                position_id = self.virtual_position_id(pair_key, branch)
                existing_events = self._trade_events(pair_key, branch)
                opened_events = [
                    event
                    for event in existing_events
                    if event.get("event_type") == "POSITION_OPENED"
                ]
                if len(opened_events) > 1:
                    raise RuntimeError(f"{branch} position has multiple open events")
                if opened_events:
                    position = self._recover_position(pair_key, branch)
                    open_payload = opened_events[0]["payload"]
                    expected_geometry = {
                        "symbol": entry_identity["symbol"],
                        "direction": entry_identity["direction"],
                        "entry_price": entry_identity["entry_price"],
                        "stop_loss": entry_identity["stop_loss"],
                        "take_profit": entry_identity["take_profit"],
                    }
                    observed_geometry = {
                        key: open_payload[key] for key in expected_geometry
                    }
                    if observed_geometry != expected_geometry or int(
                        opened_events[0]["broker_epoch"]
                    ) != entry_broker_epoch:
                        raise RuntimeError(
                            f"{branch} recovered position differs from frozen entry intent"
                        )
                    return (
                        BranchEntryOutcome(True, "RECOVERED_POSITION_OPEN_EVENT", position_id),
                        position,
                        entry_identity,
                    )
                if not authority_current:
                    return (
                        BranchEntryOutcome(False, "RESTART_AFTER_ENTRY_WINDOW"),
                        None,
                        {
                            **entry_identity,
                            "valid": False,
                            "reason": "RESTART_AFTER_ENTRY_WINDOW",
                        },
                    )

                opened = ShadowTradeEngine.open_trade(
                    journal_path=self.trade_journal_path(pair_key, branch),
                    position_id=position_id,
                    symbol=str(entry_identity["symbol"]),
                    direction=str(entry_identity["direction"]),
                    balance=float(balance),
                    risk_percent=float(entry_identity["risk_percent"]),
                    entry_price=float(entry_identity["entry_price"]),
                    stop_loss=float(entry_identity["stop_loss"]),
                    take_profit=float(entry_identity["take_profit"]),
                    broker_epoch=entry_broker_epoch,
                    broker_position_ticket=0,
                    broker_position_identifier=0,
                )
                if (
                    opened.real_order_send_allowed
                    or opened.order_send_called
                    or opened.order_check_called
                ):
                    raise RuntimeError(f"{branch} shadow engine violated execution safety")
                if not opened.valid or opened.position is None:
                    return (
                        BranchEntryOutcome(False, opened.reason),
                        None,
                        entry_identity,
                    )
                if opened.position.position_id != position_id:
                    raise RuntimeError(f"{branch} shadow engine position identity mismatch")
                return (
                    BranchEntryOutcome(True, opened.reason, position_id),
                    opened.position,
                    entry_identity,
                )

            baseline_outcome, baseline_position, baseline_entry = open_branch(
                "baseline", baseline_opened=True
            )
            candidate_outcome, candidate_position, candidate_entry = open_branch(
                "candidate",
                baseline_opened=baseline_outcome.actual_trade_opened,
            )
            write = self.record_entry_outcome(
                pair_key=pair_key,
                baseline=baseline_outcome,
                candidate=candidate_outcome,
                entry_broker_epoch=entry_broker_epoch,
                time_authority=time_authority,
                entry_evidence={
                    "balance": float(balance),
                    "point": float(point),
                    "next_candle_open": float(current_rate["open"]),
                    "spread_points": float(current_rate["spread"]),
                    "input_snapshot_sha256": decision_payload[
                        "input_snapshot_sha256"
                    ],
                    "entry_input_event_sha256": entry_input_event[
                        "event_sha256"
                    ],
                    "baseline_frozen_entry": baseline_entry,
                    "candidate_frozen_entry": candidate_entry,
                },
                _require_current_authority=authority_current,
                _lock_held=True,
            )
            return PairedEntryResult(
                write=write,
                pair_key=pair_key,
                baseline_position=baseline_position,
                candidate_position=candidate_position,
            )

    def record_entry_outcome(
        self,
        *,
        pair_key: tuple[str, str],
        baseline: BranchEntryOutcome,
        candidate: BranchEntryOutcome,
        entry_broker_epoch: int,
        time_authority: Mapping[str, object],
        entry_evidence: Mapping[str, object] | None = None,
        _require_current_authority: bool = True,
        _lock_held: bool = False,
    ) -> EvidenceWriteResult:
        decision_event = self._event_for(pair_key, "decision")
        offset = _time_authority_offset(
            time_authority,
            expected_current_bar_epoch=int(entry_broker_epoch),
            require_current=_require_current_authority,
        )
        expected_entry_epoch = (
            _epoch_from_utc_z(pair_key[1], "decision candle open")
            + offset
            + TIMEFRAME_SECONDS
        )
        if int(entry_broker_epoch) != expected_entry_epoch:
            raise RuntimeError("entry outcome must bind the next M15 broker bar")
        entry_utc_epoch = int(entry_broker_epoch) - offset
        end_epoch = _epoch_from_utc_z(
            self.activation.exclusive_45_day_end_utc, "exclusive end"
        )
        if entry_utc_epoch >= end_epoch:
            raise RuntimeError("new entries are prohibited at or after the exclusive end")
        decision_branches = decision_event["payload"]["branches"]
        for name, outcome in (("baseline", baseline), ("candidate", candidate)):
            decision_identity = decision_branches[name]["decision_identity"]
            if outcome.actual_trade_opened and decision_identity in {
                "BASELINE_NO_TRADE",
                "CANDIDATE_NO_TRADE",
                "REJECTED_CANDIDATE",
            }:
                raise RuntimeError(f"{name} no-trade decision cannot open a position")
            if outcome.actual_trade_opened and outcome.position_id != (
                self.virtual_position_id(pair_key, name)
            ):
                raise RuntimeError(f"{name} virtual position identity mismatch")
        if candidate.actual_trade_opened and not baseline.actual_trade_opened:
            raise RuntimeError("candidate actual trade requires a baseline actual trade")

        event_id = _event_id(
            manifest_sha256=self.activation.manifest_sha256,
            pair_key=pair_key,
            phase="entry",
        )

        def entry_payload(name: str, outcome: BranchEntryOutcome) -> dict[str, object]:
            prefix = name.upper()
            return {
                "entry_identity": (
                    f"{prefix}_ACTUAL_TRADE"
                    if outcome.actual_trade_opened
                    else f"{prefix}_NO_TRADE"
                ),
                "is_actual_trade": outcome.actual_trade_opened,
                "position_id": outcome.position_id,
                "reason": outcome.reason,
            }

        payload = {
            "schema_version": VERSION,
            "phase": "entry",
            "sprint93_2b_event_id": event_id,
            "activation_manifest_sha256": self.activation.manifest_sha256,
            "activation_merge_commit_sha": self.activation.activation_merge_commit_sha,
            "pair_key": list(pair_key),
            "decision_event_sha256": decision_event["event_sha256"],
            "branches": {
                "baseline": entry_payload("baseline", baseline),
                "candidate": entry_payload("candidate", candidate),
            },
            "entry_evidence": dict(entry_evidence or {}),
            "global_time_authority": dict(time_authority),
            "safety": {
                "shadow_only": True,
                "real_order_send_allowed": False,
                "order_check_allowed": False,
                "production_execution_enabled": False,
            },
        }
        append = (
            _append_evidence_once_unlocked if _lock_held else _append_evidence_once
        )
        return append(
            journal_path=self.journal_path,
            event_type=EVIDENCE_EVENT_TYPES["entry"],
            event_id=event_id,
            broker_epoch=int(entry_broker_epoch),
            payload=payload,
        )

    def _append_terminal_input_unlocked(
        self,
        *,
        pair_key: tuple[str, str],
        branch: str,
        broker_epoch: int,
        payload_fields: Mapping[str, object],
    ) -> dict[str, Any]:
        phase = f"terminal_input_{branch}"
        event_id = _event_id(
            manifest_sha256=self.activation.manifest_sha256,
            pair_key=pair_key,
            phase=phase,
        )
        payload = {
            "schema_version": VERSION,
            "phase": phase,
            "sprint93_2b_event_id": event_id,
            "activation_manifest_sha256": self.activation.manifest_sha256,
            "activation_merge_commit_sha": self.activation.activation_merge_commit_sha,
            "pair_key": list(pair_key),
            "branch": branch,
            **dict(payload_fields),
            "safety": {
                "shadow_only": True,
                "real_order_send_allowed": False,
                "order_check_allowed": False,
                "production_execution_enabled": False,
            },
        }
        write = _append_evidence_once_unlocked(
            journal_path=self.journal_path,
            event_type=EVIDENCE_EVENT_TYPES[phase],
            event_id=event_id,
            broker_epoch=int(broker_epoch),
            payload=payload,
        )
        return self._event_for(pair_key, phase) if not write.appended else (
            self._phase_events()[(pair_key, phase)]
        )

    def _append_terminal_unlocked(
        self,
        *,
        pair_key: tuple[str, str],
        branch: str,
        close_event: Mapping[str, object],
        terminal_input_event: Mapping[str, object],
    ) -> EvidenceWriteResult:
        phase = f"terminal_{branch}"
        close_payload = close_event.get("payload")
        if not isinstance(close_payload, Mapping):
            raise RuntimeError(f"{branch} close event payload is invalid")
        broker_epoch = int(close_event["broker_epoch"])
        terminal_input = terminal_input_event["payload"]
        authority = terminal_input["global_time_authority"]
        offset = _time_authority_offset(
            authority,
            expected_tick_epoch=broker_epoch,
            require_current=False,
        )
        settlement_utc = _render_utc_z(
            datetime.fromtimestamp(broker_epoch - offset, timezone.utc)
        )
        net_r = float(close_payload["r_multiple"])
        if not math.isfinite(net_r):
            raise RuntimeError(f"{branch} terminal net R is non-finite")
        if net_r == 0.0:
            net_r = 0.0
        timebox = close_payload.get("exit_reason") == "TIMEBOX_MTM_CLOSE"
        valuation_snapshot_sha256 = terminal_input.get(
            "valuation_snapshot_sha256"
        )
        if timebox:
            Preregistration._require_sha256(
                valuation_snapshot_sha256, "timebox valuation snapshot"
            )
        elif valuation_snapshot_sha256 is not None:
            raise RuntimeError("non-timebox terminal cannot carry MTM snapshot identity")
        event_id = _event_id(
            manifest_sha256=self.activation.manifest_sha256,
            pair_key=pair_key,
            phase=phase,
        )
        payload = {
            "schema_version": VERSION,
            "phase": phase,
            "sprint93_2b_event_id": event_id,
            "activation_manifest_sha256": self.activation.manifest_sha256,
            "activation_merge_commit_sha": self.activation.activation_merge_commit_sha,
            "pair_key": list(pair_key),
            "branch": branch,
            "position_id": self.virtual_position_id(pair_key, branch),
            "terminal_identity": (
                "TIMEBOX_MTM_CLOSE"
                if timebox
                else f"{branch.upper()}_ACTUAL_TRADE"
            ),
            "actual_trade_net_r": net_r,
            "actual_zero_r": net_r == 0.0,
            "terminal_settlement_utc": settlement_utc,
            "timebox_mtm": timebox,
            "valuation_snapshot_sha256": valuation_snapshot_sha256,
            "trade_journal_event_sha256": close_event["event_sha256"],
            "terminal_input_event_sha256": terminal_input_event["event_sha256"],
            "global_time_authority": authority,
            "safety": {
                "shadow_only": True,
                "real_order_send_allowed": False,
                "order_check_allowed": False,
                "production_execution_enabled": False,
            },
        }
        return _append_evidence_once_unlocked(
            journal_path=self.journal_path,
            event_type=EVIDENCE_EVENT_TYPES[phase],
            event_id=event_id,
            broker_epoch=broker_epoch,
            payload=payload,
        )

    def update_virtual_trade(
        self,
        *,
        pair_key: tuple[str, str],
        branch: str,
        bid: float,
        ask: float,
        broker_epoch: int,
        time_authority: Mapping[str, object],
    ) -> VirtualTradeUpdateResult:
        """Update one existing branch through ShadowTradeEngine, restart-safely."""

        if branch not in {"baseline", "candidate"}:
            raise ValueError("virtual trade branch must be baseline or candidate")
        if not all(math.isfinite(float(value)) and float(value) > 0 for value in (bid, ask)):
            raise RuntimeError("positive finite bid and ask are required")

        with ShadowTradeJournal.exclusive_transaction(self.journal_path):
            entry_event = self._event_for(pair_key, "entry")
            if not entry_event["payload"]["branches"][branch]["is_actual_trade"]:
                raise RuntimeError(f"{branch} has no actual virtual trade to update")
            existing_terminal = self._phase_events().get(
                (pair_key, f"terminal_{branch}")
            )
            if existing_terminal is not None:
                return VirtualTradeUpdateResult(
                    branch=branch,
                    action="ALREADY_TERMINAL",
                    position=None,
                    terminal_write=_write_result(existing_terminal, appended=False),
                )

            closed_event = self._closed_trade_event(pair_key, branch)
            terminal_input = self._phase_events().get(
                (pair_key, f"terminal_input_{branch}")
            )
            if terminal_input is not None:
                frozen = terminal_input["payload"]
                broker_epoch = int(terminal_input["broker_epoch"])
                bid = float(frozen["bid"])
                ask = float(frozen["ask"])
                time_authority = frozen["global_time_authority"]
                _time_authority_offset(
                    time_authority,
                    expected_tick_epoch=broker_epoch,
                    require_current=False,
                )
            else:
                _time_authority_offset(
                    time_authority,
                    expected_tick_epoch=int(broker_epoch),
                )
            position = self._recover_position(pair_key, branch)
            if closed_event is not None:
                if terminal_input is None:
                    raise RuntimeError(
                        f"{branch} closed without frozen terminal-input evidence"
                    )
                terminal_write = self._append_terminal_unlocked(
                    pair_key=pair_key,
                    branch=branch,
                    close_event=closed_event,
                    terminal_input_event=terminal_input,
                )
                return VirtualTradeUpdateResult(
                    branch=branch,
                    action="TERMINAL_RECOVERED",
                    position=None,
                    terminal_write=terminal_write,
                )
            if position is None:
                raise RuntimeError(f"{branch} open virtual position is missing")
            trigger = VirtualPositionEngine.exit_trigger(
                position=position,
                bid=float(bid),
                ask=float(ask),
            )
            if trigger is None:
                if terminal_input is not None:
                    raise RuntimeError(
                        f"{branch} frozen terminal input no longer produces its trigger"
                    )
                return VirtualTradeUpdateResult(
                    branch=branch,
                    action="POSITION_HELD",
                    position=position,
                )

            if terminal_input is None:
                terminal_input = self._append_terminal_input_unlocked(
                    pair_key=pair_key,
                    branch=branch,
                    broker_epoch=int(broker_epoch),
                    payload_fields={
                        "trigger": trigger,
                        "bid": float(bid),
                        "ask": float(ask),
                        "global_time_authority": dict(time_authority),
                        "observed_at_utc": _render_utc_z(
                            datetime.fromtimestamp(
                                float(
                                    time_authority["observation"][
                                        "utc_midpoint_epoch"
                                    ]
                                ),
                                timezone.utc,
                            )
                        ),
                    },
                )

            updated = ShadowTradeEngine.update_trade(
                journal_path=self.trade_journal_path(pair_key, branch),
                position=position,
                bid=float(bid),
                ask=float(ask),
                broker_epoch=int(broker_epoch),
            )
            if (
                updated.real_order_send_allowed
                or updated.order_send_called
                or updated.order_check_called
            ):
                raise RuntimeError(f"{branch} shadow engine violated execution safety")
            if not updated.valid or updated.position is None:
                raise RuntimeError(f"{branch} virtual update blocked: {updated.reason}")
            if updated.position.status != "CLOSED":
                raise RuntimeError(f"{branch} frozen terminal trigger did not close")
            close_event = self._closed_trade_event(pair_key, branch)
            if close_event is None:
                raise RuntimeError(f"{branch} terminal journal event is missing")
            terminal_write = self._append_terminal_unlocked(
                pair_key=pair_key,
                branch=branch,
                close_event=close_event,
                terminal_input_event=terminal_input,
            )
            return VirtualTradeUpdateResult(
                branch=branch,
                action="POSITION_CLOSED",
                position=updated.position,
                terminal_write=terminal_write,
            )

    @staticmethod
    def _evaluation_member(
        branch: str, settlement: BranchSettlement
    ) -> dict[str, object]:
        if not settlement.actual_trade:
            return {
                "record_type": f"{branch.upper()}_NO_TRADE",
                "actual_trade_net_r": None,
                "terminal_settlement_utc": None,
            }
        net_r = float(settlement.net_r)
        if net_r == 0.0:
            net_r = 0.0
        return {
            "record_type": (
                "TIMEBOX_MTM_CLOSE"
                if settlement.timebox_mtm
                else f"{branch.upper()}_ACTUAL_TRADE"
            ),
            "actual_trade_net_r": net_r,
            "terminal_settlement_utc": settlement.settlement_utc,
        }

    def _record_settlement(
        self,
        *,
        pair_key: tuple[str, str],
        baseline: BranchSettlement,
        candidate: BranchSettlement,
        settlement_broker_epoch: int,
        terminal_event_sha256: Mapping[str, str],
        _lock_held: bool,
    ) -> EvidenceWriteResult:
        entry_event = self._event_for(pair_key, "entry")
        decision_event = self._event_for(pair_key, "decision")
        entry_branches = entry_event["payload"]["branches"]
        for name, settlement in (("baseline", baseline), ("candidate", candidate)):
            opened = bool(entry_branches[name]["is_actual_trade"])
            if opened != settlement.actual_trade:
                raise RuntimeError(f"{name} settlement differs from its entry identity")

        baseline_member = self._evaluation_member("baseline", baseline)
        candidate_member = self._evaluation_member("candidate", candidate)
        pair_record = {
            "pair_key": pair_key,
            "baseline_member": baseline_member,
            "candidate_member": candidate_member,
        }
        projection = Preregistration.validate_pair_record(pair_record)
        settlement_times = [
            settlement.settlement_utc
            for settlement in (baseline, candidate)
            if settlement.actual_trade
        ]
        settlement_epochs = [
            _epoch_from_utc_z(value, "terminal settlement") for value in settlement_times
        ]
        end_epoch = _epoch_from_utc_z(
            self.activation.exclusive_45_day_end_utc, "exclusive end"
        )
        if any(epoch > end_epoch for epoch in settlement_epochs):
            raise RuntimeError("trade settlement cannot occur after the exclusive end")
        offset = int(decision_event["payload"]["broker_utc_offset_seconds"])
        entry_utc_epoch = int(entry_event["broker_epoch"]) - offset
        if any(epoch < entry_utc_epoch for epoch in settlement_epochs):
            raise RuntimeError("trade settlement cannot precede its virtual entry")
        for settlement in (baseline, candidate):
            if settlement.timebox_mtm and settlement.settlement_utc != (
                self.activation.exclusive_45_day_end_utc
            ):
                raise RuntimeError("timebox MTM must settle at the exclusive end")

        event_id = _event_id(
            manifest_sha256=self.activation.manifest_sha256,
            pair_key=pair_key,
            phase="settlement",
        )
        payload = {
            "schema_version": VERSION,
            "phase": "settlement",
            "sprint93_2b_event_id": event_id,
            "activation_manifest_sha256": self.activation.manifest_sha256,
            "activation_merge_commit_sha": self.activation.activation_merge_commit_sha,
            "pair_key": list(pair_key),
            "entry_event_sha256": entry_event["event_sha256"],
            "baseline_member": baseline_member,
            "candidate_member": candidate_member,
            "projection": projection,
            "actual_zero_r": {
                "baseline": baseline.actual_trade and float(baseline.net_r) == 0.0,
                "candidate": candidate.actual_trade and float(candidate.net_r) == 0.0,
            },
            "valuation_snapshot_sha256": {
                "baseline": baseline.valuation_snapshot_sha256,
                "candidate": candidate.valuation_snapshot_sha256,
            },
            "terminal_event_sha256": dict(terminal_event_sha256),
            "safety": {
                "shadow_only": True,
                "real_order_send_allowed": False,
                "order_check_allowed": False,
                "production_execution_enabled": False,
            },
        }
        append = (
            _append_evidence_once_unlocked if _lock_held else _append_evidence_once
        )
        return append(
            journal_path=self.journal_path,
            event_type=EVIDENCE_EVENT_TYPES["settlement"],
            event_id=event_id,
            broker_epoch=int(settlement_broker_epoch),
            payload=payload,
        )

    def finalize_settlement(
        self, *, pair_key: tuple[str, str]
    ) -> EvidenceWriteResult:
        """Derive the frozen evaluator pair only from journaled terminal evidence."""

        with ShadowTradeJournal.exclusive_transaction(self.journal_path):
            existing = self._phase_events().get((pair_key, "settlement"))
            if existing is not None:
                return _write_result(existing, appended=False)
            entry_event = self._event_for(pair_key, "entry")
            settlements: dict[str, BranchSettlement] = {}
            terminal_hashes: dict[str, str] = {}
            terminal_broker_epochs: list[int] = []
            for branch in ("baseline", "candidate"):
                entry_branch = entry_event["payload"]["branches"][branch]
                if not entry_branch["is_actual_trade"]:
                    settlements[branch] = BranchSettlement(False, None, None)
                    terminal_hashes[branch] = entry_event["event_sha256"]
                    continue
                terminal = self._phase_events().get(
                    (pair_key, f"terminal_{branch}")
                )
                if terminal is None:
                    raise RuntimeError(f"{branch} actual trade is not terminal")
                terminal_payload = terminal["payload"]
                settlements[branch] = BranchSettlement(
                    actual_trade=True,
                    net_r=float(terminal_payload["actual_trade_net_r"]),
                    settlement_utc=str(
                        terminal_payload["terminal_settlement_utc"]
                    ),
                    timebox_mtm=bool(terminal_payload["timebox_mtm"]),
                    valuation_snapshot_sha256=(
                        str(terminal_payload["valuation_snapshot_sha256"])
                        if terminal_payload["valuation_snapshot_sha256"] is not None
                        else None
                    ),
                )
                terminal_hashes[branch] = terminal["event_sha256"]
                terminal_broker_epochs.append(int(terminal["broker_epoch"]))
            if not terminal_broker_epochs:
                raise RuntimeError(
                    "both-no-trade observations are excluded from evaluation pairs"
                )
            return self._record_settlement(
                pair_key=pair_key,
                baseline=settlements["baseline"],
                candidate=settlements["candidate"],
                settlement_broker_epoch=max(terminal_broker_epochs),
                terminal_event_sha256=terminal_hashes,
                _lock_held=True,
            )

    def timebox_close_virtual_trade(
        self,
        *,
        pair_key: tuple[str, str],
        branch: str,
        final_completed_candle: Mapping[str, object],
        point: float,
        time_authority: Mapping[str, object],
    ) -> TimeboxCloseResult:
        """Close one still-open branch from the frozen final completed M15 candle."""

        if branch not in {"baseline", "candidate"}:
            raise ValueError("virtual trade branch must be baseline or candidate")
        if not math.isfinite(float(point)) or float(point) <= 0:
            raise RuntimeError("positive finite point is required")
        end = _parse_utc_z(self.activation.exclusive_45_day_end_utc, "exclusive end")

        with ShadowTradeJournal.exclusive_transaction(self.journal_path):
            existing_terminal = self._phase_events().get(
                (pair_key, f"terminal_{branch}")
            )
            if existing_terminal is not None:
                closed = self._closed_position(pair_key, branch)
                if closed is None:
                    raise RuntimeError(f"{branch} terminal evidence lacks closed position")
                terminal_payload = existing_terminal["payload"]
                if terminal_payload.get("timebox_mtm") is not True:
                    raise RuntimeError(f"{branch} already closed before the timebox")
                return TimeboxCloseResult(
                    closed_position=closed,
                    settlement=BranchSettlement(
                        actual_trade=True,
                        net_r=float(terminal_payload["actual_trade_net_r"]),
                        settlement_utc=str(
                            terminal_payload["terminal_settlement_utc"]
                        ),
                        timebox_mtm=True,
                        valuation_snapshot_sha256=str(
                            terminal_payload["valuation_snapshot_sha256"]
                        ),
                    ),
                    terminal_write=_write_result(existing_terminal, appended=False),
                )

            entry_event = self._event_for(pair_key, "entry")
            if not entry_event["payload"]["branches"][branch]["is_actual_trade"]:
                raise RuntimeError(f"{branch} has no actual virtual trade to timebox")
            terminal_input = self._phase_events().get(
                (pair_key, f"terminal_input_{branch}")
            )
            close_event = self._closed_trade_event(pair_key, branch)
            if close_event is not None:
                if terminal_input is None:
                    raise RuntimeError(
                        f"{branch} timebox close lacks frozen terminal-input evidence"
                    )
                terminal_write = self._append_terminal_unlocked(
                    pair_key=pair_key,
                    branch=branch,
                    close_event=close_event,
                    terminal_input_event=terminal_input,
                )
                closed = self._closed_position(pair_key, branch)
                terminal_payload = self._event_for(
                    pair_key, f"terminal_{branch}"
                )["payload"]
                return TimeboxCloseResult(
                    closed_position=closed,
                    settlement=BranchSettlement(
                        actual_trade=True,
                        net_r=float(terminal_payload["actual_trade_net_r"]),
                        settlement_utc=str(
                            terminal_payload["terminal_settlement_utc"]
                        ),
                        timebox_mtm=True,
                        valuation_snapshot_sha256=str(
                            terminal_payload["valuation_snapshot_sha256"]
                        ),
                    ),
                    terminal_write=terminal_write,
                )

            position = self._recover_position(pair_key, branch)
            if position is None:
                raise RuntimeError(f"{branch} open virtual position is missing")
            if terminal_input is not None:
                frozen_input = terminal_input["payload"]
                if frozen_input.get("trigger") != "TIMEBOX_MTM_CLOSE":
                    raise RuntimeError(f"{branch} has a non-timebox terminal input")
                close_broker_epoch = int(terminal_input["broker_epoch"])
                time_authority = frozen_input["global_time_authority"]
                _time_authority_offset(
                    time_authority,
                    expected_current_bar_epoch=close_broker_epoch,
                    expected_tick_epoch=close_broker_epoch,
                    require_current=False,
                )
                final_snapshot = dict(frozen_input["final_completed_candle"])
                snapshot_sha = str(frozen_input["valuation_snapshot_sha256"])
                Preregistration._require_sha256(
                    snapshot_sha, "timebox valuation snapshot"
                )
                if _canonical_sha256(final_snapshot) != snapshot_sha:
                    raise RuntimeError("timebox valuation snapshot hash mismatch")
                bid = float(frozen_input["bid"])
                ask = float(frozen_input["ask"])
                point = float(frozen_input["point"])
            else:
                offset = _time_authority_offset(time_authority)
                close_broker_epoch = int(end.timestamp()) + offset
                _time_authority_offset(
                    time_authority,
                    expected_current_bar_epoch=close_broker_epoch,
                    expected_tick_epoch=close_broker_epoch,
                )
                expected_final_broker_epoch = (
                    close_broker_epoch - TIMEFRAME_SECONDS
                )
                frozen_final = _freeze_rates(
                    [final_completed_candle],
                    current_bar_epoch=expected_final_broker_epoch,
                )[0]
                if frozen_final.time != expected_final_broker_epoch:
                    raise RuntimeError(
                        "timebox valuation must use the final eligible completed M15 candle"
                    )
                if frozen_final.spread < 0:
                    raise RuntimeError("timebox valuation spread cannot be negative")
                final_snapshot = asdict(frozen_final)
                snapshot_sha = _canonical_sha256(final_snapshot)
                bid = frozen_final.close
                ask = frozen_final.close + frozen_final.spread * float(point)
            close_price = VirtualPositionEngine.market_close_price(
                direction=position.direction,
                bid=bid,
                ask=ask,
            )
            if close_price <= 0:
                raise RuntimeError("timebox MTM close price is invalid")
            if terminal_input is None:
                terminal_input = self._append_terminal_input_unlocked(
                    pair_key=pair_key,
                    branch=branch,
                    broker_epoch=close_broker_epoch,
                    payload_fields={
                        "trigger": "TIMEBOX_MTM_CLOSE",
                        "bid": bid,
                        "ask": ask,
                        "point": float(point),
                        "final_completed_candle": final_snapshot,
                        "valuation_snapshot_sha256": snapshot_sha,
                        "global_time_authority": dict(time_authority),
                        "observed_at_utc": self.activation.exclusive_45_day_end_utc,
                    },
                )
            valuation = ShadowTradeValuation.calculate(
                symbol=position.symbol,
                direction=position.direction,
                volume=position.volume,
                entry_price=position.entry_price,
                close_price=close_price,
            )
            if not valuation.valid:
                raise RuntimeError(f"timebox MTM valuation blocked: {valuation.reason}")
            if (
                valuation.real_order_send_allowed
                or valuation.order_send_called
                or valuation.order_check_called
            ):
                raise RuntimeError("timebox valuation violated execution safety")
            closed = VirtualPositionEngine.close_position(
                position=position,
                close_price=close_price,
                broker_epoch=close_broker_epoch,
                reason="TIMEBOX_MTM_CLOSE",
                pnl_account_currency=valuation.pnl_account_currency,
            )
            if closed.status != "CLOSED":
                raise RuntimeError("timebox MTM virtual close failed")
            close_payload = {
                "symbol": closed.symbol,
                "direction": closed.direction,
                "volume": closed.volume,
                "entry_price": closed.entry_price,
                "close_price": closed.close_price,
                "stop_loss": closed.stop_loss,
                "take_profit": closed.take_profit,
                "exit_reason": "TIMEBOX_MTM_CLOSE",
                "pnl_account_currency": closed.pnl_account_currency,
                "r_multiple": closed.r_multiple,
                "valuation_method": "MT5_ORDER_CALC_PROFIT",
                "valuation_snapshot_sha256": snapshot_sha,
            }
            ShadowTradeJournal.append_event(
                path=self.trade_journal_path(pair_key, branch),
                event_type="POSITION_CLOSED",
                position_id=self.virtual_position_id(pair_key, branch),
                broker_epoch=close_broker_epoch,
                payload=close_payload,
            )
            close_event = self._closed_trade_event(pair_key, branch)
            if close_event is None:
                raise RuntimeError("timebox terminal journal event is missing")
            terminal_write = self._append_terminal_unlocked(
                pair_key=pair_key,
                branch=branch,
                close_event=close_event,
                terminal_input_event=terminal_input,
            )
            return TimeboxCloseResult(
                closed_position=closed,
                settlement=BranchSettlement(
                    actual_trade=True,
                    net_r=closed.r_multiple,
                    settlement_utc=self.activation.exclusive_45_day_end_utc,
                    timebox_mtm=True,
                    valuation_snapshot_sha256=snapshot_sha,
                ),
                terminal_write=terminal_write,
            )


def verify_package_safety(module_path: Path) -> bool:
    """Static guard: this paired package cannot call real-order APIs."""

    tree = ast.parse(Path(module_path).read_text(encoding="utf-8-sig"))
    prohibited = {"order_send", "order_check"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Attribute):
                name = node.func.attr
            elif isinstance(node.func, ast.Name):
                name = node.func.id
            if name in prohibited:
                raise RuntimeError(f"prohibited real-order API call: {name}")
        if isinstance(node, ast.ImportFrom):
            if any(alias.name in prohibited for alias in node.names):
                raise RuntimeError("prohibited real-order API import")
    return True
