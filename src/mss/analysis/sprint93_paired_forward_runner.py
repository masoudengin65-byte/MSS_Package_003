"""Preverified paired boundaries and recovery-only virtual lifecycle management.

The continuous supervisor integrates both under one lease and MT5 session.
The bounded collector refuses to wait with outstanding virtual lifecycles.
The recovery manager never collects new decisions or certifies continuity.
Public GitHub verification belongs to the caller and must finish before this
module receives its in-memory VerifiedActivation. No verified context is cached
to disk and no live snapshot can be supplied through the CLI.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
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
from mss.analysis.indexed_shadow_trade_journal import IndexedShadowTradeJournal


PREPARATION_LEAD_SECONDS = 10.0
MAX_CLOCK_STEP_SECONDS = 0.5
LIFECYCLE_POLL_SECONDS = 1.0
MAX_LIFECYCLE_CYCLE_SECONDS = 5.0
BOUNDARY_PUBLICATION_POLL_SECONDS = 0.02


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


def _capture_pair_at_boundary(
    session: LiveMt5ReadOnlySession,
    *,
    target: int,
    previous_broker_offset_seconds: int | None,
) -> tuple[LiveMt5Snapshot, ...]:
    """Wait only for publication of the already-requested boundary.

    MT5 may briefly return the preceding bar immediately after an M15 boundary.
    Those transient snapshots are never written or relabelled.  The original
    two-second entry deadline remains authoritative.
    """
    snapshots = []
    for symbol in SYMBOL_MAP:
        while True:
            now = _utc_now_epoch()
            if not 0 <= now - target <= MAX_ENTRY_OBSERVATION_DELAY_SECONDS:
                raise RuntimeError(
                    "live MT5 boundary bar was not published inside the entry window"
                )
            snapshot = session.capture(
                symbol,
                previous_broker_offset_seconds=previous_broker_offset_seconds,
            )
            authority, _provenance = _validate_live_mt5_snapshot(snapshot)
            offset = _time_authority_offset(authority)
            normalized_bar = snapshot.current_bar_epoch - offset
            if normalized_bar == target:
                snapshots.append(snapshot)
                break
            if normalized_bar > target:
                raise RuntimeError("live MT5 bar advanced beyond the requested boundary")
            remaining = (
                target + MAX_ENTRY_OBSERVATION_DELAY_SECONDS - _utc_now_epoch()
            )
            if remaining <= 0:
                raise RuntimeError(
                    "live MT5 boundary bar was not published inside the entry window"
                )
            time.sleep(min(BOUNDARY_PUBLICATION_POLL_SECONDS, remaining))
    return tuple(snapshots)


def _commit_pair_snapshots(collector, snapshots) -> list[dict[str, object]]:
    """Keep the identical durable-entry path for bounded and continuous runs."""
    results = []
    for snapshot in snapshots:
        decision = collector.collect_decision(snapshot=snapshot)
        entry = collector.open_virtual_entries(
            pair_key=decision.pair_key, balance=snapshot.balance,
            point=snapshot.point, time_authority=snapshot.time_authority(),
        )
        payload = collector._event_for(decision.pair_key, "entry")["payload"]
        if any(branch["reason"] == "RESTART_AFTER_ENTRY_WINDOW"
               for branch in payload["branches"].values()):
            raise RuntimeError("durable entry missed deadline; partial evidence retained")
        results.append({
            "pair_key": list(decision.pair_key),
            "decision_appended": decision.write.appended,
            "entry_appended": entry.write.appended,
            "baseline_virtual_position_open": entry.baseline_position is not None,
            "candidate_virtual_position_open": entry.candidate_position is not None,
        })
    return results


def _latest_authority(collector) -> dict[str, object] | None:
    reader = getattr(collector, "latest_time_authority", None)
    if callable(reader):
        return reader()
    for event in reversed(collector._events()):
        authority = event.get("payload", {}).get("global_time_authority")
        if isinstance(authority, dict):
            return authority
    return None


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
        backend = IndexedShadowTradeJournal(journal_path)
        collector = PairedForwardEvidenceCollector(
            activation=activation, journal_path=journal_path,
            journal_backend=backend,
        )
        state = collector.recover()
        if state.pending_entry_pair_keys or state.open_pair_keys:
            raise RuntimeError("existing virtual lifecycle requires recovery/management first")
        start = _epoch_from_utc_z(activation.first_eligible_m15_open_utc, "activation start")
        # No MT5 initialization or market API access before the activation start.
        _wait_until_utc(start)
        verify_local_freeze(activation, repository_root)
        authority = _latest_authority(collector)
        previous_offset = (
            _time_authority_offset(authority, require_current=False)
            if authority is not None else None
        )
        with LiveMt5ReadOnlySession() as session:
            if _utc_now_epoch() >= target - PREPARATION_LEAD_SECONDS:
                raise RuntimeError("MT5 setup missed preparation deadline; no acquisition")
            _wait_until_utc(target)
            verify_local_freeze(activation, repository_root)
            if not 0 <= _utc_now_epoch() - target <= MAX_ENTRY_OBSERVATION_DELAY_SECONDS:
                raise RuntimeError("boundary deadline expired before acquisition")
            snapshots = _capture_pair_at_boundary(
                session,
                target=target,
                previous_broker_offset_seconds=previous_offset,
            )
            _validate_pair(snapshots, target)
            results = _commit_pair_snapshots(collector, snapshots)
        return {
            "result": "SPRINT93_2B_BOUNDARY_PAIR_COLLECTED",
            "entry_bar_open_utc": entry_bar_open_utc,
            "symbols": results,
            "bounded_cycle_only": True,
            "lifecycle_supervisor_running": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        }


class LifecycleCoordinator:
    """Manage existing evidence only; never evaluate a new signal or fill a gap.

    The caller owns the runner lease and the verified MT5 session. Frozen intents
    take precedence over fresh prices, including across the exclusive end.
    """

    def __init__(self, collector: PairedForwardEvidenceCollector):
        self.collector = collector
        self.end = _epoch_from_utc_z(
            collector.activation.exclusive_45_day_end_utc, "exclusive end"
        )

    def outstanding(self) -> tuple[tuple[tuple[str, str], str], ...]:
        reader = getattr(self.collector, "outstanding_branches", None)
        if callable(reader):
            return reader()
        indexed = self.collector._phase_events()
        return tuple(sorted(
            (pair, branch)
            for pair, phase in indexed if phase == "entry"
            for event in (indexed[(pair, phase)],)
            for branch in ("baseline", "candidate")
            if event["payload"]["branches"][branch]["is_actual_trade"]
            and (pair, f"terminal_{branch}") not in indexed
        ))

    def finalize_ready(self) -> None:
        # recover().open_pair_keys deliberately excludes fully terminal pairs.
        # Inspect entries as well so a crash before settlement cannot orphan one.
        reader = getattr(self.collector, "ready_settlement_pairs", None)
        if callable(reader):
            ready = reader()
        else:
            indexed = self.collector._phase_events()
            ready = []
            for pair, phase in sorted(indexed):
                if phase != "entry" or (pair, "settlement") in indexed:
                    continue
                event = indexed[(pair, phase)]
                actual = [
                    branch for branch in ("baseline", "candidate")
                    if event["payload"]["branches"][branch]["is_actual_trade"]
                ]
                if actual and all((pair, f"terminal_{branch}") in indexed for branch in actual):
                    ready.append(pair)
        for pair in ready:
            self.collector.finalize_settlement(pair_key=pair)

    def recover_frozen(self) -> None:
        """Resolve all pending entries/terminal intents without acquiring prices."""
        for symbol in SYMBOL_MAP:
            while True:
                pending = tuple(
                    pair for pair in self.collector.recover().pending_entry_pair_keys
                    if pair[0] == symbol
                )
                if not pending:
                    break
                result = self.collector.resume_pending_entry(canonical_symbol=symbol)
                if result is None or result.pair_key not in pending:
                    raise RuntimeError("pending entry recovery made no progress")
                if result.pair_key in self.collector.recover().pending_entry_pair_keys:
                    raise RuntimeError("pending entry recovery did not commit its outcome")
        indexed = self.collector._phase_events()
        for pair, branch in self.outstanding():
            event = indexed.get((pair, f"terminal_input_{branch}"))
            if event is None:
                continue
            frozen = event["payload"]
            if frozen["trigger"] == "TIMEBOX_MTM_CLOSE":
                self.collector.timebox_close_virtual_trade(
                    pair_key=pair, branch=branch,
                    final_completed_candle=frozen["final_completed_candle"],
                    point=frozen["point"], time_authority=frozen["global_time_authority"],
                )
            else:
                self.collector.update_virtual_trade(
                    pair_key=pair, branch=branch, bid=frozen["bid"], ask=frozen["ask"],
                    broker_epoch=event["broker_epoch"],
                    time_authority=frozen["global_time_authority"],
                )
        self.finalize_ready()

    def apply_snapshots(self, snapshots: tuple[LiveMt5Snapshot, ...]) -> None:
        """Validate the complete outstanding universe before any lifecycle write."""
        outstanding = self.outstanding()
        symbols = tuple(symbol for symbol in SYMBOL_MAP if any(p[0] == symbol for p, _ in outstanding))
        if tuple(snapshot.canonical_symbol for snapshot in snapshots) != symbols:
            raise RuntimeError("lifecycle acquisition must match the outstanding symbol universe")
        by_symbol = {}
        context = None
        post_end = _utc_now_epoch() >= self.end
        # Preflight final-candle availability for every pair before closing any.
        final_rows = {}
        indexed = self.collector._phase_events()
        for snapshot in snapshots:
            authority, provenance = _validate_live_mt5_snapshot(snapshot)
            offset = _time_authority_offset(authority)
            observed_context = (
                offset, provenance.get("account_server"),
                provenance.get("account_currency"), provenance.get("terminal_build"),
            )
            if context is not None and context != observed_context:
                raise RuntimeError("lifecycle acquisitions disagree on broker context")
            context = observed_context
            for pair, _branch in outstanding:
                if pair[0] != snapshot.canonical_symbol:
                    continue
                original = indexed[(pair, "decision")]["payload"]["live_mt5_acquisition"]
                for field in ("account_server", "account_currency", "terminal_build"):
                    if not original.get(field) or provenance.get(field) != original[field]:
                        raise RuntimeError("lifecycle broker context changed since the decision")
            normalized_tick = snapshot.tick_epoch - offset
            if post_end:
                if normalized_tick < self.end or snapshot.current_bar_epoch - offset < self.end:
                    raise RuntimeError("timebox requires a post-end snapshot; no stale tick update")
                for pair, _branch in outstanding:
                    if pair[0] != snapshot.canonical_symbol or pair in final_rows:
                        continue
                    boundary_offset, _ = self.collector.timebox_boundary_evidence(pair_key=pair)
                    final_epoch = self.end + boundary_offset - TIMEFRAME_SECONDS
                    rows = [asdict(rate) for rate in snapshot.rates if rate.time == final_epoch]
                    if len(rows) != 1:
                        raise RuntimeError("live MT5 snapshot lacks the frozen final M15 candle")
                    final_rows[pair] = rows[0]
            elif normalized_tick >= self.end:
                raise RuntimeError("post-end tick cannot be used for an ordinary update")
            by_symbol[snapshot.canonical_symbol] = snapshot
        if not post_end and _utc_now_epoch() >= self.end:
            raise RuntimeError("lifecycle preflight crossed the exclusive end; preserve evidence")
        boundary_recorded = set()
        for pair, branch in outstanding:
            snapshot = by_symbol[pair[0]]
            authority = snapshot.time_authority()
            if post_end:
                self.collector.timebox_close_virtual_trade(
                    pair_key=pair, branch=branch, final_completed_candle=final_rows[pair],
                    point=snapshot.point, time_authority=authority,
                )
            else:
                if _utc_now_epoch() >= self.end:
                    raise RuntimeError("lifecycle update crossed the exclusive end; preserve evidence")
                if pair not in boundary_recorded:
                    self.collector.record_timebox_boundary_authority_if_due(
                        pair_key=pair, time_authority=authority,
                    )
                    boundary_recorded.add(pair)
                self.collector.update_virtual_trade(
                    pair_key=pair, branch=branch, bid=snapshot.bid, ask=snapshot.ask,
                    broker_epoch=snapshot.tick_epoch, time_authority=authority,
                )
        self.finalize_ready()


def manage_existing_lifecycles(
    *, activation: VerifiedActivation, repository_root: Path, journal_path: Path,
) -> dict[str, object]:
    """Recovery-only polling, not permission to resume the experiment schedule.

    Every invocation records continuity as UNVERIFIED before recovering anything.
    A process crash leaves its start record without a finish. No new decisions are
    collected, no missed ticks are reconstructed, and no research-validity claim
    follows from completing existing virtual trades.
    """
    verify_local_freeze(activation, repository_root)
    start = _epoch_from_utc_z(activation.first_eligible_m15_open_utc, "activation start")
    if _utc_now_epoch() < start:
        raise RuntimeError("lifecycle recovery cannot run before activation")
    with runner_lease(journal_path):
        backend = IndexedShadowTradeJournal(journal_path)
        collector = PairedForwardEvidenceCollector(
            activation=activation, journal_path=journal_path,
            journal_backend=backend,
        )
        coordinator = LifecycleCoordinator(collector)
        operations = Path(journal_path).with_name(Path(journal_path).name + ".lifecycle.jsonl")

        def audit(event_type: str, **details) -> None:
            ShadowTradeJournal.append_event(
                path=operations, event_type=event_type,
                position_id=activation.manifest_sha256, broker_epoch=0,
                payload={
                    "activation_manifest_sha256": activation.manifest_sha256,
                    "observed_utc_epoch": _utc_now_epoch(),
                    "mode": "EXISTING_LIFECYCLES_ONLY",
                    "experiment_continuity": "UNVERIFIED",
                    "new_decisions_allowed": False,
                    "production_execution_enabled": False, **details,
                },
            )

        audit("LIFECYCLE_RECOVERY_STARTED")
        try:
            authority = _latest_authority(collector)
            previous_offset = (
                _time_authority_offset(authority, require_current=False)
                if authority is not None else None
            )
            # Setup also enables read-only valuation of previously frozen intents.
            with LiveMt5ReadOnlySession() as session:
                verify_local_freeze(activation, repository_root)
                indexed = collector._phase_events()
                recovery_pairs = set(collector.recover().pending_entry_pair_keys)
                recovery_pairs.update(pair for pair, _ in coordinator.outstanding())
                for pair in sorted(recovery_pairs):
                    session.require_context(indexed[pair, "decision"]["payload"]["live_mt5_acquisition"])
                coordinator.recover_frozen()
                utc_anchor, monotonic_anchor = _utc_now_epoch(), time.monotonic()
                next_poll = utc_anchor
                next_checkpoint = utc_anchor + TIMEFRAME_SECONDS
                while coordinator.outstanding():
                    _wait_until_utc(next_poll)
                    cycle_start = time.monotonic()
                    now = _utc_now_epoch()
                    if abs(now - utc_anchor - (cycle_start - monotonic_anchor)) > MAX_CLOCK_STEP_SECONDS:
                        raise RuntimeError("UTC clock stepped during lifecycle management")
                    if now - next_poll > MAX_LIFECYCLE_CYCLE_SECONDS:
                        raise RuntimeError("lifecycle polling gap exceeded its limit")
                    verify_local_freeze(activation, repository_root)
                    outstanding = coordinator.outstanding()
                    symbols = tuple(s for s in SYMBOL_MAP if any(p[0] == s for p, _ in outstanding))
                    snapshots = tuple(
                        session.capture(symbol, previous_broker_offset_seconds=previous_offset)
                        for symbol in symbols
                    )
                    if time.monotonic() - cycle_start > MAX_LIFECYCLE_CYCLE_SECONDS:
                        raise RuntimeError("lifecycle acquisition exceeded its cycle limit")
                    if abs(_utc_now_epoch() - utc_anchor - (time.monotonic() - monotonic_anchor)) > MAX_CLOCK_STEP_SECONDS:
                        raise RuntimeError("UTC clock stepped during lifecycle acquisition")
                    coordinator.apply_snapshots(snapshots)
                    previous_offset = _time_authority_offset(snapshots[-1].time_authority())
                    elapsed = time.monotonic() - cycle_start
                    if elapsed > MAX_LIFECYCLE_CYCLE_SECONDS:
                        raise RuntimeError("lifecycle writes exceeded their cycle limit; partial evidence retained")
                    if abs(_utc_now_epoch() - utc_anchor - (time.monotonic() - monotonic_anchor)) > MAX_CLOCK_STEP_SECONDS:
                        raise RuntimeError("UTC clock stepped during lifecycle management")
                    # No catch-up bursts or reconstructed historical ticks. The
                    # periodic checkpoint is operational, not tick evidence.
                    if _utc_now_epoch() >= next_checkpoint:
                        audit("LIFECYCLE_POLL_CHECKPOINT", cycle_seconds=elapsed,
                              observed_symbols=list(symbols))
                        next_checkpoint = _utc_now_epoch() + TIMEFRAME_SECONDS
                    next_poll = min(now + LIFECYCLE_POLL_SECONDS, coordinator.end)
                    if now >= coordinator.end and coordinator.outstanding():
                        raise RuntimeError("timebox pass left unresolved virtual positions")
            audit("LIFECYCLE_RECOVERY_COMPLETED")
        except BaseException as exc:
            audit("LIFECYCLE_RECOVERY_FAILED", error_type=type(exc).__name__,
                  partial_evidence_must_be_preserved=True)
            raise
        return {
            "result": "SPRINT93_2B_EXISTING_LIFECYCLES_COMPLETE",
            "experiment_continuity_verified": False,
            "new_decisions_collected": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        }


class _SupervisorClock:
    def __init__(self):
        self.utc = _utc_now_epoch()
        self.monotonic = time.monotonic()
        self.check()

    def check(self) -> float:
        now = _utc_now_epoch()
        elapsed = time.monotonic() - self.monotonic
        if not math.isfinite(now) or abs(now - self.utc - elapsed) > MAX_CLOCK_STEP_SECONDS:
            raise RuntimeError("UTC clock stepped during continuous supervision")
        return now


def run_forward_supervisor(
    *, activation: VerifiedActivation, repository_root: Path, journal_path: Path,
) -> dict[str, object]:
    """One fresh, fixed-window run. Never resume, backfill or shift a boundary.

    At a decision boundary, acquire both symbols, commit both entry outcomes,
    then apply the same snapshots to outstanding lifecycles. Between boundaries,
    poll only outstanding symbols. A synchronous poll that crosses a scheduled
    boundary is an explicit failure, not an opportunity to relabel its snapshot.
    Completion means collection finished and still requires evidence review.
    """
    verify_local_freeze(activation, repository_root)
    start = _epoch_from_utc_z(activation.first_eligible_m15_open_utc, "activation start")
    end = _epoch_from_utc_z(activation.exclusive_45_day_end_utc, "exclusive end")
    if start % TIMEFRAME_SECONDS or end % TIMEFRAME_SECONDS or end <= start + TIMEFRAME_SECONDS:
        raise RuntimeError("supervisor requires an aligned nonempty activation window")
    clock = _SupervisorClock()
    if clock.check() >= start:
        raise RuntimeError("continuous supervision must start before activation")
    journal_path = Path(journal_path)
    operations = journal_path.with_name(journal_path.name + ".supervisor.jsonl")
    recovery_log = journal_path.with_name(journal_path.name + ".lifecycle.jsonl")
    next_boundary = start + TIMEFRAME_SECONDS
    completed_boundaries = 0
    previous_context = None
    last_observations: dict[str, float] = {}
    with runner_lease(journal_path):
        # Even an empty/torn prior file is not a clean-start authorization. A
        # crash leaves the start marker permanently; recovery is a separate mode.
        index_path = IndexedShadowTradeJournal.index_path_for(journal_path)
        index_artifacts = (index_path, Path(str(index_path) + "-wal"), Path(str(index_path) + "-shm"))
        if any(path.exists() for path in (
            journal_path, operations, recovery_log, *index_artifacts,
        )):
            raise RuntimeError("supervisor requires pristine journals; automatic resume is prohibited")
        if any((journal_path.parent / "virtual_positions").rglob("*.jsonl")):
            raise RuntimeError("orphan virtual journals require review before a fresh run")
        backend = IndexedShadowTradeJournal(journal_path)
        collector = PairedForwardEvidenceCollector(
            activation=activation, journal_path=journal_path,
            journal_backend=backend,
        )
        coordinator = LifecycleCoordinator(collector)
        if backend.verify(journal_path)["event_count"]:
            raise RuntimeError("supervisor cannot inherit existing evidence")

        def audit(event_type: str, **details) -> None:
            ShadowTradeJournal.append_event(
                path=operations, event_type=event_type,
                position_id=activation.manifest_sha256, broker_epoch=0,
                payload={
                    "activation_manifest_sha256": activation.manifest_sha256,
                    "observed_utc_epoch": _utc_now_epoch(),
                    "first_eligible_m15_open_utc": activation.first_eligible_m15_open_utc,
                    "exclusive_end_utc": activation.exclusive_45_day_end_utc,
                    "next_entry_boundary_utc_epoch": next_boundary,
                    "completed_boundaries": completed_boundaries,
                    "last_observation_utc_epochs": dict(last_observations),
                    "poll_target_seconds": LIFECYCLE_POLL_SECONDS,
                    "maximum_cycle_seconds": MAX_LIFECYCLE_CYCLE_SECONDS,
                    "automatic_resume_allowed": False,
                    "research_validity_certified": False,
                    "real_order_send_allowed": False,
                    "production_execution_enabled": False, **details,
                },
            )

        def symbols_outstanding() -> tuple[str, ...]:
            outstanding = coordinator.outstanding()
            return tuple(s for s in SYMBOL_MAP if any(pair[0] == s for pair, _ in outstanding))

        def check_gaps(symbols, now: float) -> None:
            for symbol in symbols:
                previous = last_observations.get(symbol)
                if previous is None or not 0 <= now - previous <= MAX_LIFECYCLE_CYCLE_SECONDS:
                    raise RuntimeError("outstanding lifecycle observation gap exceeded its limit")

        def capture(session, symbols, active_symbols, *, boundary_target=None):
            nonlocal previous_context
            check_gaps(active_symbols, clock.check())
            offset = previous_context[0] if previous_context is not None else None
            if boundary_target is None:
                snapshots = tuple(
                    session.capture(symbol, previous_broker_offset_seconds=offset)
                    for symbol in symbols
                )
            else:
                if tuple(symbols) != tuple(SYMBOL_MAP):
                    raise RuntimeError("boundary acquisition requires the frozen pair")
                snapshots = _capture_pair_at_boundary(
                    session,
                    target=boundary_target,
                    previous_broker_offset_seconds=offset,
                )
            now = clock.check()
            check_gaps(active_symbols, now)
            for snapshot in snapshots:
                authority, provenance = _validate_live_mt5_snapshot(snapshot)
                context = (
                    _time_authority_offset(authority), provenance.get("account_server"),
                    provenance.get("account_currency"), provenance.get("terminal_build"),
                )
                if not all(context[1:]) or (previous_context is not None and context != previous_context):
                    raise RuntimeError("continuous supervisor broker context changed")
                previous_context = context
            return snapshots

        def apply_lifecycles(snapshots) -> None:
            active = symbols_outstanding()
            coordinator.apply_snapshots(tuple(s for s in snapshots if s.canonical_symbol in active))
            for snapshot in snapshots:
                last_observations[snapshot.canonical_symbol] = float(
                    snapshot.time_authority()["observation"]["utc_epoch_after_tick"]
                )

        def require_cycle(started: float) -> None:
            clock.check()
            if time.monotonic() - started > MAX_LIFECYCLE_CYCLE_SECONDS:
                raise RuntimeError("supervisor cycle exceeded its limit; partial evidence retained")

        audit("SUPERVISOR_STARTED")
        try:
            _wait_until_utc(start)
            clock.check()
            verify_local_freeze(activation, repository_root)
            with LiveMt5ReadOnlySession() as session:
                if clock.check() >= next_boundary - PREPARATION_LEAD_SECONDS:
                    raise RuntimeError("MT5 setup missed supervisor preparation deadline")
                next_poll = next_boundary
                while True:
                    active = symbols_outstanding()
                    wake = min(next_boundary, end, next_poll if active else end)
                    _wait_until_utc(wake)
                    now = clock.check()
                    started = time.monotonic()
                    verify_local_freeze(activation, repository_root)
                    now = clock.check()
                    if now >= end:
                        if next_boundary != end:
                            raise RuntimeError("experiment end reached with missed decision boundaries")
                        snapshots = capture(session, active, active)
                        require_cycle(started)
                        apply_lifecycles(snapshots)
                        require_cycle(started)
                        break
                    if now >= next_boundary:
                        if now - next_boundary > MAX_ENTRY_OBSERVATION_DELAY_SECONDS:
                            raise RuntimeError("missed decision boundary; no backfill or automatic retry")
                        snapshots = capture(
                            session, tuple(SYMBOL_MAP), active,
                            boundary_target=next_boundary,
                        )
                        _validate_pair(snapshots, next_boundary)
                        results = _commit_pair_snapshots(collector, snapshots)
                        if any(not r["decision_appended"] or not r["entry_appended"] for r in results):
                            raise RuntimeError("fresh supervisor encountered duplicate boundary evidence")
                        # No terminal valuation or audit append precedes the
                        # existing frozen durable-entry deadline checks above.
                        apply_lifecycles(snapshots)
                        require_cycle(started)
                        completed_target = next_boundary
                        next_boundary += TIMEFRAME_SECONDS
                        completed_boundaries += 1
                        evidence = backend.verify(journal_path)
                        if not evidence["valid"]:
                            raise RuntimeError("paired evidence integrity failure at boundary checkpoint")
                        audit("SUPERVISOR_BOUNDARY_COMPLETED",
                              entry_boundary_utc_epoch=completed_target,
                              pair_keys=[r["pair_key"] for r in results],
                              evidence_tip_sha256=evidence["last_event_sha256"],
                              broker_context=list(previous_context))
                        require_cycle(started)
                    else:
                        snapshots = capture(session, active, active)
                        if clock.check() >= min(next_boundary, end):
                            raise RuntimeError("lifecycle poll crossed a scheduled boundary; no relabeling")
                        require_cycle(started)
                        apply_lifecycles(snapshots)
                        require_cycle(started)
                    next_poll = now + LIFECYCLE_POLL_SECONDS

                expected = {
                    (symbol, datetime.fromtimestamp(target - TIMEFRAME_SECONDS, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
                    for target in range(start + TIMEFRAME_SECONDS, end, TIMEFRAME_SECONDS)
                    for symbol in SYMBOL_MAP
                }
                recovered = collector.recover()
                if (set(recovered.decision_pair_keys) != expected
                        or recovered.pending_entry_pair_keys or coordinator.outstanding()
                        or completed_boundaries != (end - start) // TIMEFRAME_SECONDS - 1):
                    raise RuntimeError("supervisor final coverage/lifecycle audit failed")
            final_evidence = backend.full_verify()
            if not final_evidence["valid"]:
                raise RuntimeError("paired evidence integrity failure at final checkpoint")
            audit("SUPERVISOR_FINISHED_PENDING_REVIEW",
                  evidence_tip_sha256=final_evidence["last_event_sha256"],
                  evidence_event_count=final_evidence["event_count"])
        except BaseException as exc:
            audit("SUPERVISOR_FAILED", error_type=type(exc).__name__,
                  reason=str(exc), partial_evidence_must_be_preserved=True)
            raise
        return {
            "result": "SPRINT93_2B_FORWARD_COLLECTION_FINISHED_PENDING_REVIEW",
            "completed_boundaries": completed_boundaries,
            "research_validity_certified": False,
            "automatic_resume_allowed": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        }
