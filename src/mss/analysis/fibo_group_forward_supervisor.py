"""Fail-closed live supervisor for the FIBO paired forward-shadow runtime.

The supervisor owns only read-only MT5 acquisition and the append-only shadow
journal.  It never exposes an order-capable API, resumes a partial run, or
relabels a missed M15 boundary.  A verified activation object is required
before any boundary can be evaluated or committed.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import math
from pathlib import Path
import time
from typing import Any, Callable

from mss.analysis.fibo_group_forward_activation import (
    FiboVerifiedActivation,
    _FIBO_VERIFIED_ACTIVATION_MARKER,
)
from mss.analysis.fibo_group_paired_forward_runtime import (
    FiboBoundarySnapshot,
    FiboGroupPairedForwardRuntime,
    SYMBOL_MAP,
)
from mss.analysis.live_completed_candle_signal_engine import (
    LiveCompletedCandleSignalEngine,
)
from mss.analysis.shadow_trade_journal import ShadowTradeJournal


EXPECTED_SERVER = "FIBOGroup-MT5 Server"
RELEASE_CYCLE = "S93.3F-FIBO-FORWARD-REFREEZE-20260915"
TIMEFRAME_SECONDS = 15 * 60
REQUIRED_RATE_COUNT = LiveCompletedCandleSignalEngine.REQUIRED_COMPLETED_CANDLES + 1
MAX_BOUNDARY_OBSERVATION_DELAY_SECONDS = 2.0
POLL_SECONDS = 0.25


def _utc_now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _rate_epoch(rate: Any) -> int:
    try:
        return int(rate["time"])
    except (TypeError, KeyError, IndexError):
        return int(getattr(rate, "time"))


class FiboMt5ReadOnlySession:
    """One connected, read-only MT5 session bound to the FIBO demo server."""

    def __init__(
        self,
        terminal_path: Path | None = None,
        *,
        mt5_module: Any | None = None,
    ) -> None:
        self.terminal_path = Path(terminal_path) if terminal_path is not None else None
        self._mt5 = mt5_module
        self._active = False
        self._server = None

    @property
    def mt5(self) -> Any:
        if self._mt5 is None:
            import MetaTrader5 as mt5

            self._mt5 = mt5
        return self._mt5

    def __enter__(self) -> "FiboMt5ReadOnlySession":
        if self._active:
            raise RuntimeError("FIBO MT5 read-only session is already active")
        kwargs: dict[str, object] = {"timeout": 120_000}
        if self.terminal_path is not None:
            kwargs["path"] = str(self.terminal_path)
        if not self.mt5.initialize(**kwargs):
            error = getattr(self.mt5, "last_error", lambda: "unknown")()
            self.mt5.shutdown()
            raise RuntimeError(f"FIBO MT5 initialization failed: {error}")
        self._active = True
        try:
            self._validate_context()
            for broker_symbol in SYMBOL_MAP.values():
                if not self.mt5.symbol_select(broker_symbol, True):
                    raise RuntimeError(
                        f"FIBO symbol selection failed: {broker_symbol}"
                    )
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._active:
            try:
                self.mt5.shutdown()
            finally:
                self._active = False

    def _validate_context(self) -> str:
        if not self._active:
            raise RuntimeError("FIBO MT5 read-only session is not active")
        terminal = self.mt5.terminal_info()
        account = self.mt5.account_info()
        if terminal is None or not bool(getattr(terminal, "connected", False)):
            raise RuntimeError("connected FIBO MT5 terminal evidence is required")
        if account is None:
            raise RuntimeError("FIBO MT5 account evidence is required")
        server = getattr(account, "server", None)
        if server != EXPECTED_SERVER:
            raise RuntimeError("active MT5 session is not the required FIBO demo server")
        demo_mode = getattr(self.mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
        if demo_mode is None or getattr(account, "trade_mode", None) != demo_mode:
            raise RuntimeError("non-demo FIBO MT5 account is blocked")
        self._server = server
        return server

    def capture(
        self,
        canonical_symbol: str,
        *,
        boundary_epoch: int | None = None,
    ) -> FiboBoundarySnapshot:
        if canonical_symbol not in SYMBOL_MAP:
            raise RuntimeError("canonical symbol is outside the frozen FIBO universe")
        self._validate_context()
        broker_symbol = SYMBOL_MAP[canonical_symbol]
        info = self.mt5.symbol_info(broker_symbol)
        if info is None:
            raise RuntimeError(f"FIBO symbol metadata unavailable: {broker_symbol}")
        rates = self.mt5.copy_rates_from_pos(
            broker_symbol,
            self.mt5.TIMEFRAME_M15,
            0,
            REQUIRED_RATE_COUNT,
        )
        if rates is None or len(rates) < REQUIRED_RATE_COUNT:
            raise RuntimeError(
                f"FIBO requires {REQUIRED_RATE_COUNT} M15 rates for {broker_symbol}"
            )
        epochs = tuple(_rate_epoch(rate) for rate in rates)
        if not epochs or any(epoch <= 0 for epoch in epochs):
            raise RuntimeError("FIBO M15 rate epochs are invalid")
        current_bar_epoch = max(epochs)
        if current_bar_epoch % TIMEFRAME_SECONDS:
            raise RuntimeError("FIBO current M15 bar is not boundary-aligned")
        if boundary_epoch is not None:
            target = int(boundary_epoch)
            if target <= 0 or target % TIMEFRAME_SECONDS:
                raise RuntimeError("FIBO requested boundary is invalid")
            if current_bar_epoch < target:
                raise RuntimeError("FIBO requested boundary has not been published")
            if current_bar_epoch > target:
                raise RuntimeError("FIBO requested boundary was missed; no backfill allowed")
        return FiboBoundarySnapshot(
            canonical_symbol=canonical_symbol,
            broker_symbol=broker_symbol,
            account_server=self._server,
            current_bar_epoch=current_bar_epoch,
            rates=rates,
        )

    def capture_pair(self, boundary_epoch: int) -> tuple[FiboBoundarySnapshot, ...]:
        return tuple(
            self.capture(symbol, boundary_epoch=boundary_epoch)
            for symbol in SYMBOL_MAP
        )


@contextmanager
def runner_lease(journal_path: Path):
    """Prevent two FIBO supervisors from owning the same run."""

    path = Path(journal_path)
    lease_path = path.with_name(path.name + ".runner")
    with ShadowTradeJournal.exclusive_transaction(lease_path):
        yield


def _wait_until(
    target_epoch: int,
    *,
    utc_now: Callable[[], float],
    sleep: Callable[[float], None],
) -> float:
    previous = float(utc_now())
    if not math.isfinite(previous):
        raise RuntimeError("UTC clock returned a non-finite value")
    while previous < target_epoch:
        remaining = target_epoch - previous
        sleep(min(POLL_SECONDS, remaining))
        current = float(utc_now())
        if not math.isfinite(current) or current < previous:
            raise RuntimeError("UTC clock moved backwards while waiting")
        previous = current
    return previous


def _audit(
    *,
    path: Path,
    activation: FiboVerifiedActivation,
    event_type: str,
    next_boundary: int,
    completed_boundaries: int,
    **details: object,
) -> dict[str, object]:
    return ShadowTradeJournal.append_event(
        path=path,
        event_type=event_type,
        position_id=activation.manifest_sha256,
        broker_epoch=0,
        payload={
            "activation_manifest_sha256": activation.manifest_sha256,
            "first_eligible_m15_open_epoch": activation.first_eligible_epoch,
            "exclusive_end_epoch": activation.exclusive_end_epoch,
            "next_boundary_epoch": next_boundary,
            "completed_boundaries": completed_boundaries,
            "automatic_resume_allowed": False,
            "research_validity_certified": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
            **details,
        },
    )


def run_fibo_forward_supervisor(
    *,
    activation: FiboVerifiedActivation,
    journal_path: Path,
    terminal_path: Path | None = None,
    runtime: FiboGroupPairedForwardRuntime | None = None,
    session_factory: Callable[[], FiboMt5ReadOnlySession] | None = None,
    utc_now: Callable[[], float] = _utc_now_epoch,
    sleep: Callable[[float], None] = time.sleep,
    max_boundary_delay_seconds: float = MAX_BOUNDARY_OBSERVATION_DELAY_SECONDS,
) -> dict[str, object]:
    """Run one fresh FIBO shadow window; never resume or backfill evidence."""

    if not isinstance(activation, FiboVerifiedActivation):
        raise RuntimeError("a verified FIBO activation context is required")
    if activation._verification_marker is not _FIBO_VERIFIED_ACTIVATION_MARKER:
        raise RuntimeError("a verified FIBO activation context is required")
    start = int(activation.first_eligible_epoch)
    end = int(activation.exclusive_end_epoch)
    if start <= 0 or end <= start or start % TIMEFRAME_SECONDS or end % TIMEFRAME_SECONDS:
        raise RuntimeError("FIBO activation window must be aligned and nonempty")
    if not math.isfinite(float(max_boundary_delay_seconds)) or max_boundary_delay_seconds < 0:
        raise RuntimeError("FIBO boundary delay limit is invalid")

    journal_path = Path(journal_path)
    operations_path = journal_path.with_name(journal_path.name + ".supervisor.jsonl")
    active_runtime = runtime or FiboGroupPairedForwardRuntime()
    factory = session_factory or (
        lambda: FiboMt5ReadOnlySession(terminal_path=terminal_path)
    )
    now = float(utc_now())
    if not math.isfinite(now) or now >= start:
        raise RuntimeError("FIBO supervisor must start before activation")

    with runner_lease(journal_path):
        if any(path.exists() for path in (journal_path, operations_path)):
            raise RuntimeError("FIBO supervisor requires pristine journals")
        completed = 0
        next_boundary = start
        _audit(
            path=operations_path,
            activation=activation,
            event_type="FIBO_SUPERVISOR_STARTED",
            next_boundary=next_boundary,
            completed_boundaries=completed,
            maximum_cycle_seconds=5.0,
            poll_target_seconds=POLL_SECONDS,
            release_cycle=RELEASE_CYCLE,
        )
        try:
            with factory() as session:
                while next_boundary < end:
                    observed = _wait_until(next_boundary, utc_now=utc_now, sleep=sleep)
                    if observed - next_boundary > max_boundary_delay_seconds:
                        raise RuntimeError("FIBO boundary observation window expired")
                    started = time.monotonic()
                    snapshots = session.capture_pair(next_boundary)
                    captured_at = float(utc_now())
                    if (
                        not math.isfinite(captured_at)
                        or captured_at - next_boundary > max_boundary_delay_seconds
                    ):
                        raise RuntimeError("FIBO boundary observation window expired")
                    evaluated = active_runtime.evaluate_pair(snapshots)
                    event = active_runtime.commit_pair(
                        activation=activation,
                        journal_path=journal_path,
                        evaluated=evaluated,
                    )
                    elapsed = time.monotonic() - started
                    if elapsed > 5.0:
                        raise RuntimeError("FIBO supervisor cycle exceeded its limit")
                    completed += 1
                    _audit(
                        path=operations_path,
                        activation=activation,
                        event_type="FIBO_SUPERVISOR_BOUNDARY_COMPLETED",
                        next_boundary=next_boundary + TIMEFRAME_SECONDS,
                        completed_boundaries=completed,
                        boundary_epoch=next_boundary,
                        evidence_event_sha256=event["event_sha256"],
                    )
                    next_boundary += TIMEFRAME_SECONDS
            evidence = ShadowTradeJournal.verify(journal_path)
            if not evidence["valid"]:
                raise RuntimeError("FIBO journal integrity failure")
            _audit(
                path=operations_path,
                activation=activation,
                event_type="FIBO_SUPERVISOR_FINISHED_PENDING_REVIEW",
                next_boundary=next_boundary,
                completed_boundaries=completed,
                evidence_event_count=evidence["event_count"],
                evidence_tip_sha256=evidence["last_event_sha256"],
            )
        except BaseException as exc:
            _audit(
                path=operations_path,
                activation=activation,
                event_type="FIBO_SUPERVISOR_FAILED",
                next_boundary=next_boundary,
                completed_boundaries=completed,
                error_type=type(exc).__name__,
                reason=str(exc),
                partial_evidence_must_be_preserved=True,
            )
            raise

    return {
        "result": "FIBO_FORWARD_COLLECTION_FINISHED_PENDING_REVIEW",
        "completed_boundaries": completed,
        "research_validity_certified": False,
        "automatic_resume_allowed": False,
        "real_order_send_allowed": False,
        "production_execution_enabled": False,
    }


run_forward_supervisor = run_fibo_forward_supervisor
