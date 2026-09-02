"""One preverified, single-writer paired collection at an explicit M15 boundary.

This is a bounded acquisition command, not a 45-day lifecycle supervisor. It
refuses to wait while virtual positions or unresolved entry intents exist.
Public GitHub verification belongs to the caller and must finish before this
module receives its in-memory VerifiedActivation. No verified context is cached
to disk and no live snapshot can be supplied through the CLI.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
import time

from mss.analysis.sprint93_paired_forward_activation import (
    DEFAULT_MANIFEST_RELATIVE_PATH,
    LiveMt5ReadOnlySession,
    LiveMt5Snapshot,
    MAX_ENTRY_OBSERVATION_DELAY_SECONDS,
    PairedForwardEvidenceCollector,
    SYMBOL_MAP,
    TIMEFRAME_SECONDS,
    VerifiedActivation,
    _VERIFIED_ACTIVATION_MARKER,
    _epoch_from_utc_z,
    _normalise_lf,
    _time_authority_offset,
    _utc_now_epoch,
    _validate_live_mt5_snapshot,
    observed_runtime_versions,
)
from mss.analysis.shadow_trade_journal import ShadowTradeJournal


PREPARATION_LEAD_SECONDS = 10.0
MAX_CLOCK_STEP_SECONDS = 0.5


@contextmanager
def runner_lease(journal_path: Path):
    """All mutating CLI commands share this fail-fast process ownership lock."""
    journal_path = Path(journal_path)
    lease_path = journal_path.with_name(journal_path.name + ".runner")
    with ShadowTradeJournal.exclusive_transaction(lease_path):
        yield


def verify_local_freeze(activation: VerifiedActivation, root: Path) -> None:
    """Recheck local bytes after waiting, without network calls in the deadline."""
    if activation._verification_marker is not _VERIFIED_ACTIVATION_MARKER:
        raise RuntimeError("a verified activation is required")
    runtime = observed_runtime_versions()
    if runtime != {
        "python_version": activation.python_version,
        "numpy_version": activation.numpy_version,
    }:
        raise RuntimeError("runtime changed after public verification")
    root = Path(root).resolve()
    for relative, digest in activation.execution_identity:
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise RuntimeError("execution source escaped the repository")
        observed = hashlib.sha256(_normalise_lf(path.read_bytes())).hexdigest()
        if observed != digest:
            raise RuntimeError(f"execution source changed after verification: {relative}")
    manifest = _normalise_lf((root / DEFAULT_MANIFEST_RELATIVE_PATH).read_bytes())
    if hashlib.sha256(manifest).hexdigest() != activation.manifest_sha256:
        raise RuntimeError("manifest changed after public verification")


def _wait_until_utc(target: float) -> None:
    """Wait in bounded increments; reject clock steps instead of hiding gaps."""
    utc_anchor = _utc_now_epoch()
    monotonic_anchor = time.monotonic()
    while True:
        now = _utc_now_epoch()
        elapsed = time.monotonic() - monotonic_anchor
        if not math.isfinite(now) or abs(now - utc_anchor - elapsed) > MAX_CLOCK_STEP_SECONDS:
            raise RuntimeError("UTC clock stepped while waiting for the boundary")
        remaining = target - now
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.25))


def _validate_target(activation: VerifiedActivation, entry_bar_open_utc: str) -> int:
    target = _epoch_from_utc_z(entry_bar_open_utc, "entry bar open")
    if target % TIMEFRAME_SECONDS:
        raise RuntimeError("entry boundary must be aligned to M15")
    decision = datetime.fromtimestamp(target - TIMEFRAME_SECONDS, timezone.utc)
    activation.require_eligible_decision(decision.strftime("%Y-%m-%dT%H:%M:%SZ"))
    end = _epoch_from_utc_z(activation.exclusive_45_day_end_utc, "exclusive end")
    if target >= end:
        raise RuntimeError("entry boundary must precede the exclusive end")
    if _utc_now_epoch() >= target - PREPARATION_LEAD_SECONDS:
        raise RuntimeError("insufficient preparation time; boundary will not be shifted")
    return target


def _validate_pair(snapshots: tuple[LiveMt5Snapshot, ...], target: int) -> None:
    if tuple(s.canonical_symbol for s in snapshots) != tuple(SYMBOL_MAP):
        raise RuntimeError("acquisition must contain the exact ordered frozen universe")
    common_context = None
    for snapshot in snapshots:
        authority, provenance = _validate_live_mt5_snapshot(snapshot)
        offset = _time_authority_offset(authority)
        if snapshot.current_bar_epoch - offset != target:
            raise RuntimeError("live MT5 bar does not match the requested boundary")
        acquisition_end = float(authority["observation"]["utc_epoch_after_tick"])
        if not (
            0 <= snapshot.tick_epoch - offset - target <= MAX_ENTRY_OBSERVATION_DELAY_SECONDS
            and 0 <= acquisition_end - target <= MAX_ENTRY_OBSERVATION_DELAY_SECONDS
        ):
            raise RuntimeError("paired acquisition missed the frozen entry window")
        context = (
            offset,
            provenance.get("account_server"),
            provenance.get("account_currency"),
            provenance.get("terminal_build"),
        )
        if common_context is not None and context != common_context:
            raise RuntimeError("paired acquisitions disagree on broker context")
        common_context = context
    if not 0 <= _utc_now_epoch() - target <= MAX_ENTRY_OBSERVATION_DELAY_SECONDS:
        raise RuntimeError("paired acquisition exceeded the write preparation deadline")


def collect_pair_at_boundary(
    *,
    activation: VerifiedActivation,
    repository_root: Path,
    journal_path: Path,
    entry_bar_open_utc: str,
) -> dict[str, object]:
    """Capture both symbols before writing; retain evidence on any later failure.

    A failed cycle is never silently moved to another bar, retried from fresh
    prices, or reported as a success. Existing per-branch durable-entry deadlines
    remain authoritative even if acquisition itself completed in time.
    """
    verify_local_freeze(activation, repository_root)
    target = _validate_target(activation, entry_bar_open_utc)
    with runner_lease(journal_path):
        collector = PairedForwardEvidenceCollector(
            activation=activation, journal_path=journal_path
        )
        state = collector.recover()
        if state.pending_entry_pair_keys or state.open_pair_keys:
            raise RuntimeError("existing virtual lifecycle requires recovery/management first")
        start = _epoch_from_utc_z(activation.first_eligible_m15_open_utc, "activation start")
        # No MT5 initialization or market API access before the activation start.
        _wait_until_utc(start)
        verify_local_freeze(activation, repository_root)
        previous_offset = None
        for event in reversed(collector._events()):
            authority = event.get("payload", {}).get("global_time_authority")
            if isinstance(authority, dict):
                previous_offset = _time_authority_offset(authority, require_current=False)
                break
        with LiveMt5ReadOnlySession() as session:
            if _utc_now_epoch() >= target - PREPARATION_LEAD_SECONDS:
                raise RuntimeError("MT5 setup missed preparation deadline; no acquisition")
            _wait_until_utc(target)
            verify_local_freeze(activation, repository_root)
            if not 0 <= _utc_now_epoch() - target <= MAX_ENTRY_OBSERVATION_DELAY_SECONDS:
                raise RuntimeError("boundary deadline expired before acquisition")
            snapshots = tuple(
                session.capture(symbol, previous_broker_offset_seconds=previous_offset)
                for symbol in SYMBOL_MAP
            )
            _validate_pair(snapshots, target)
            results = []
            for snapshot in snapshots:
                decision = collector.collect_decision(snapshot=snapshot)
                entry = collector.open_virtual_entries(
                    pair_key=decision.pair_key,
                    balance=snapshot.balance,
                    point=snapshot.point,
                    time_authority=snapshot.time_authority(),
                )
                payload = collector._event_for(decision.pair_key, "entry")["payload"]
                if any(
                    branch["reason"] == "RESTART_AFTER_ENTRY_WINDOW"
                    for branch in payload["branches"].values()
                ):
                    raise RuntimeError("durable entry missed deadline; partial evidence retained")
                results.append({
                    "pair_key": list(decision.pair_key),
                    "decision_appended": decision.write.appended,
                    "entry_appended": entry.write.appended,
                    "baseline_virtual_position_open": entry.baseline_position is not None,
                    "candidate_virtual_position_open": entry.candidate_position is not None,
                })
        return {
            "result": "SPRINT93_2B_BOUNDARY_PAIR_COLLECTED",
            "entry_bar_open_utc": entry_bar_open_utc,
            "symbols": results,
            "bounded_cycle_only": True,
            "lifecycle_supervisor_running": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        }
