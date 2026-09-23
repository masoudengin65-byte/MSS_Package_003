"""Build and verify a write-once FIBO paired-forward activation manifest."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Mapping, Sequence

from mss.analysis.fibo_group_paired_forward_runtime import (
    FiboVerifiedActivation,
    _FIBO_VERIFIED_ACTIVATION_MARKER,
)

VERSION = "MSS_SPRINT93_3F_FIBO_GROUP_FORWARD_ACTIVATION_V1"
EXECUTION_ID = "MSS_93_3F_FIBO_GROUP_PAIRED_FORWARD_SHADOW_V1"
TIMEFRAME_SECONDS = 900
DURATION_SECONDS = 45 * 24 * 60 * 60
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
REQUIRED_EXECUTION_PATHS = frozenset(
    {
        "src/mss/analysis/fibo_group_forward_activation.py",
        "src/mss/analysis/fibo_group_forward_shadow_preregistration.py",
        "src/mss/analysis/fibo_group_paired_forward_runtime.py",
        "src/mss/analysis/fibo_group_forward_supervisor.py",
        "src/mss/analysis/live_completed_candle_signal_engine.py",
        "src/mss/analysis/smart_money_pipeline.py",
        "src/mss/analysis/confluence_gated_smart_money_pipeline.py",
        "src/mss/analysis/frozen_shadow_strategy_adapter.py",
        "src/mss/analysis/shadow_trade_journal.py",
        "integration_tests/run_sprint93_3f_fibo_group_forward_activation.py",
    }
)


def canonical_bytes(value: object) -> bytes:
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


def _parse_utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError(f"{label} must be canonical UTC Z text")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RuntimeError(f"{label} is invalid") from exc
    if parsed.tzinfo != timezone.utc or parsed.microsecond:
        raise RuntimeError(f"{label} must have whole-second UTC precision")
    return parsed


def _render(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def activation_window(freeze_merged_at_utc: str) -> tuple[str, str]:
    merged = _parse_utc(freeze_merged_at_utc, "freeze mergedAt")
    earliest = merged + timedelta(hours=2)
    epoch = int(earliest.timestamp())
    start_epoch = (
        (epoch + TIMEFRAME_SECONDS - 1) // TIMEFRAME_SECONDS
    ) * TIMEFRAME_SECONDS
    start = datetime.fromtimestamp(start_epoch, timezone.utc)
    return _render(start), _render(start + timedelta(seconds=DURATION_SECONDS))


def _validate_identity(
    identity: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, str], ...]:
    rows = []
    for item in identity:
        if set(item) != {"path", "git_blob_sha256"}:
            raise RuntimeError("execution identity record is malformed")
        path, digest = item["path"], item["git_blob_sha256"]
        if (
            not isinstance(path, str)
            or not path
            or not isinstance(digest, str)
            or not SHA256_RE.fullmatch(digest)
        ):
            raise RuntimeError("execution identity value is invalid")
        rows.append((path, digest))
    result = tuple(rows)
    if result != tuple(sorted(result)) or len(result) != len(
        set(path for path, _ in result)
    ):
        raise RuntimeError("execution identity must be unique and path-sorted")
    if not REQUIRED_EXECUTION_PATHS.issubset(path for path, _ in result):
        raise RuntimeError("execution identity is incomplete")
    return result


def _validate_freeze_metadata(metadata: Mapping[str, object]) -> None:
    if metadata.get("state") != "MERGED":
        raise RuntimeError("FIBO runtime freeze PR must be merged")
    if not isinstance(metadata.get("number"), int) or isinstance(
        metadata.get("number"), bool
    ):
        raise RuntimeError("freeze PR number is invalid")
    if not isinstance(metadata.get("url"), str) or not metadata["url"].startswith(
        "https://github.com/"
    ):
        raise RuntimeError("freeze PR URL is invalid")
    if not isinstance(
        metadata.get("merge_commit_sha"), str
    ) or not FULL_SHA_RE.fullmatch(metadata["merge_commit_sha"]):
        raise RuntimeError("freeze merge commit is invalid")
    _parse_utc(metadata.get("merged_at_utc"), "freeze mergedAt")


def build_manifest(
    *,
    freeze_metadata: Mapping[str, object],
    manifest_created_at_utc: str,
    runtime_versions: Mapping[str, str],
    execution_identity: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    _validate_freeze_metadata(freeze_metadata)
    created = _parse_utc(manifest_created_at_utc, "manifest creation")
    merged = _parse_utc(freeze_metadata["merged_at_utc"], "freeze mergedAt")
    if created <= merged:
        raise RuntimeError("manifest must be created after the runtime freeze merge")
    identity = _validate_identity(execution_identity)
    start, end = activation_window(freeze_metadata["merged_at_utc"])
    versions = {
        key: runtime_versions.get(key) for key in ("python_version", "numpy_version")
    }
    if not all(isinstance(value, str) and value for value in versions.values()):
        raise RuntimeError("Python and NumPy versions must be frozen")
    return {
        "schema_version": VERSION,
        "execution_id": EXECUTION_ID,
        "write_once": True,
        "provider": "FIBO Group",
        "required_server": "FIBOGroup-MT5 Server",
        "required_account_class": "DEMO",
        "canonical_to_broker_symbol": {"BTCUSD": "BTC", "ETHUSD": "ETH"},
        "timeframe": "M15",
        "duration_seconds": DURATION_SECONDS,
        "runtime_freeze_pr": dict(freeze_metadata),
        "manifest_created_at_utc": manifest_created_at_utc,
        "computed_first_eligible_m15_open_utc": start,
        "computed_exclusive_45_day_end_utc": end,
        "runtime_versions": versions,
        "complete_execution_identity": [
            {"path": path, "git_blob_sha256": digest} for path, digest in identity
        ],
        "all_pre_activation_data_permanently_ineligible": True,
        "no_forward_outcome_access_before_activation": True,
        "safety": {
            "shadow_only": True,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }


def verify_manifest(
    *,
    manifest: Mapping[str, object],
    manifest_bytes: bytes,
    freeze_metadata: Mapping[str, object],
    publication_metadata: Mapping[str, object],
    runtime_versions: Mapping[str, str],
    observed_execution_identity: Sequence[Mapping[str, object]],
    no_forward_outcome_access_verified: bool,
) -> FiboVerifiedActivation:
    if canonical_bytes(manifest) != manifest_bytes:
        raise RuntimeError("FIBO manifest bytes are not canonical")
    if (
        manifest.get("schema_version") != VERSION
        or manifest.get("execution_id") != EXECUTION_ID
    ):
        raise RuntimeError("FIBO manifest identity is invalid")
    expected_contract = {
        "provider": "FIBO Group",
        "required_server": "FIBOGroup-MT5 Server",
        "required_account_class": "DEMO",
        "canonical_to_broker_symbol": {"BTCUSD": "BTC", "ETHUSD": "ETH"},
        "timeframe": "M15",
        "duration_seconds": DURATION_SECONDS,
    }
    if any(manifest.get(key) != value for key, value in expected_contract.items()):
        raise RuntimeError("FIBO manifest broker contract is invalid")
    if (
        manifest.get("write_once") is not True
        or manifest.get("all_pre_activation_data_permanently_ineligible") is not True
    ):
        raise RuntimeError("FIBO manifest write-once boundary is invalid")
    if (
        manifest.get("no_forward_outcome_access_before_activation") is not True
        or no_forward_outcome_access_verified is not True
    ):
        raise RuntimeError("no-forward-outcome-access proof is required")
    _validate_freeze_metadata(freeze_metadata)
    if manifest.get("runtime_freeze_pr") != dict(freeze_metadata):
        raise RuntimeError("manifest freeze metadata mismatch")
    expected_start, expected_end = activation_window(freeze_metadata["merged_at_utc"])
    if (
        manifest.get("computed_first_eligible_m15_open_utc") != expected_start
        or manifest.get("computed_exclusive_45_day_end_utc") != expected_end
    ):
        raise RuntimeError("manifest activation window mismatch")
    if manifest.get("runtime_versions") != {
        key: runtime_versions.get(key) for key in ("python_version", "numpy_version")
    }:
        raise RuntimeError("runtime version mismatch")
    frozen_identity = _validate_identity(
        manifest.get("complete_execution_identity", [])
    )
    if frozen_identity != _validate_identity(observed_execution_identity):
        raise RuntimeError("execution identity mismatch")
    if (
        publication_metadata.get("state") != "MERGED"
        or publication_metadata.get("base_branch") != "main"
    ):
        raise RuntimeError("manifest publication PR must be merged into main")
    published_at = _parse_utc(
        publication_metadata.get("merged_at_utc"), "manifest publication mergedAt"
    )
    created = _parse_utc(manifest.get("manifest_created_at_utc"), "manifest creation")
    freeze_merged = _parse_utc(freeze_metadata["merged_at_utc"], "freeze mergedAt")
    start = _parse_utc(expected_start, "activation start")
    end = _parse_utc(expected_end, "activation end")
    if not freeze_merged < created <= published_at < end:
        raise RuntimeError(
            "manifest was not created after freeze and published before window end"
        )
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if publication_metadata.get("manifest_blob_sha256") != manifest_sha256:
        raise RuntimeError("published manifest blob mismatch")
    safety = manifest.get("safety", {})
    if (
        not isinstance(safety, Mapping)
        or safety.get("real_order_send_allowed") is not False
        or safety.get("production_execution_enabled") is not False
    ):
        raise RuntimeError("manifest safety boundary is invalid")
    return FiboVerifiedActivation(
        manifest_sha256=manifest_sha256,
        first_eligible_epoch=int(start.timestamp()),
        exclusive_end_epoch=int(end.timestamp()),
        _verification_marker=_FIBO_VERIFIED_ACTIVATION_MARKER,
    )
