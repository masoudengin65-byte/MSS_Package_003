"""Parallel causal multi-symbol Shadow Live session.

Sprint 92H.14.6

Key properties:
- multiple broker symbols observed
- fast batch transition capture
- concurrent pure signal analysis
- fresh broker tick revalidated immediately before entry
- frozen NEXT_CANDLE_OPEN contract
- freshness limit remains unchanged
- maximum ONE global Shadow position
- no real MT5 order_send/order_check
- no True-OOS access
"""

from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.causal_next_candle_entry_watcher import (
    CausalNextCandleEntryWatcher,
)
from mss.analysis.live_completed_candle_signal_engine import (
    LiveCompletedCandleSignalEngine,
)
from mss.analysis.live_market_observer import (
    LiveMarketObserver,
)
from mss.analysis.multi_asset_shadow_risk_policy import (
    MultiAssetShadowRiskPolicy,
    ShadowRiskCandidateInput,
)
from mss.analysis.shadow_position_recovery import (
    ShadowPositionRecovery,
)
from mss.analysis.shadow_portfolio_risk_aggregator import (
    ShadowPortfolioJournalSource,
    ShadowPortfolioRiskAggregator,
)
from mss.analysis.shadow_portfolio_risk_state import (
    ShadowPortfolioRiskState,
)
from mss.analysis.shadow_portfolio_continuity_policy import (
    ShadowPortfolioContinuityPolicy,
)
from mss.analysis.shadow_portfolio_carry_forward import (
    ShadowPortfolioCarryForward,
)
from mss.analysis.shadow_trade_engine import (
    ShadowTradeEngine,
)
from mss.analysis.shadow_live_runtime_safety_adapter import (
    ShadowLiveRuntimeSafetyAdapter,
    ShadowLiveRuntimeSafetyFacts,
)
from mss.analysis.shadow_live_safety_governor import (
    ShadowLiveSafetyGovernor,
)
from mss.analysis.shadow_live_runtime_supervisor import (
    ShadowLiveRuntimeSupervisor,
    ShadowLiveRuntimeSupervisorInput,
)
from mss.analysis.shadow_live_runtime_telemetry import (
    ShadowLiveRuntimeTelemetry,
)
from mss.analysis.portfolio_risk_governor import (
    PortfolioRiskGovernor,
)

from run_sprint92h14_3_3c_continuous_shadow_session import (
    MIN_REQUIRED_RATES,
    POLL_SECONDS,
    TIMEFRAME,
    build_transition_time_authority,
    find_rate,
    latest_bar_epoch,
    load_rates,
    make_execution_guard,
    observed_spread_points,
    rate_value,
    safe_symbol_name,
    validate_tick,
    write_session_report,
)


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SYMBOLS = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "XAUUSD",
    "XAGUSD",
    "WTI",
    "BITCOIN",
    "ETHEREUM",
)

MAX_OPEN_SHADOW_POSITIONS = 1
MAX_ANALYSIS_WORKERS = 8

RUNTIME_HEARTBEAT_MAX_GAP_SECONDS = max(
    5.0,
    float(POLL_SECONDS) * 20.0,
)

MANUAL_KILL_SWITCH_PATH = (
    ROOT
    / "runtime_controls"
    / "MSS_MANUAL_KILL_SWITCH"
)



def manual_kill_switch_requested() -> bool:
    """Return True when operator entry-inhibit sentinel exists.

    Read-only:
    - does not create the control file
    - does not delete the control file
    - does not touch journals
    """

    try:
        return bool(
            MANUAL_KILL_SWITCH_PATH
            .is_file()
        )
    except OSError:
        # Fail-safe: inability to inspect the control
        # state must inhibit new entries.
        return True



def evaluate_session_runtime_health(
    *,
    manual_kill_switch_active,
    mt5_connected,
    terminal_available,
    account_available,
    runtime_portfolio_risk_recovery,
    current_risk_snapshot,
):
    """Evaluate non-candidate global runtime health.

    This watchdog runs before candidate discovery.

    Time Authority is intentionally NOT evaluated here,
    because authoritative candidate-specific broker-time
    evidence is established later in the causal entry path.

    The final pre-entry Safety Governor remains responsible
    for enforcing fresh Time Authority immediately before
    Shadow position creation.
    """

    portfolio_recovery_valid = bool(
        runtime_portfolio_risk_recovery
        is not None
        and
        runtime_portfolio_risk_recovery.valid
    )

    portfolio_snapshot_present = bool(
        current_risk_snapshot is not None
    )

    if (
        portfolio_recovery_valid
        and
        portfolio_snapshot_present
    ):
        try:
            open_position_count = int(
                runtime_portfolio_risk_recovery
                .open_position_count
            )

            total_open_risk_percent = float(
                current_risk_snapshot
                .total_risk_percent
            )

            limits_valid = (
                open_position_count >= 0
                and
                open_position_count
                <=
                MAX_OPEN_SHADOW_POSITIONS
                and
                total_open_risk_percent >= 0.0
                and
                total_open_risk_percent
                <=
                PortfolioRiskGovernor
                .MAX_TOTAL_OPEN_RISK_PERCENT
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            limits_valid = False

    else:
        limits_valid = False

    kill_conditions = []

    if manual_kill_switch_active:
        kill_conditions.append(
            "MANUAL_KILL_SWITCH_ACTIVE"
        )

    if not mt5_connected:
        kill_conditions.append(
            "MT5_NOT_CONNECTED"
        )

    if not terminal_available:
        kill_conditions.append(
            "MT5_TERMINAL_UNAVAILABLE"
        )

    if not account_available:
        kill_conditions.append(
            "MT5_ACCOUNT_UNAVAILABLE"
        )

    if not portfolio_recovery_valid:
        kill_conditions.append(
            "PORTFOLIO_RECOVERY_INVALID"
        )

    if not portfolio_snapshot_present:
        kill_conditions.append(
            "PORTFOLIO_SNAPSHOT_MISSING"
        )

    if not limits_valid:
        kill_conditions.append(
            "PORTFOLIO_LIMITS_INVALID"
        )

    return tuple(
        kill_conditions
    )


def evaluate_entry_safety(
    *,
    manual_kill_switch_active,
    mt5_initialized,
    terminal_available,
    account_available,
    time_authority_confirmed,
    runtime_portfolio_risk_recovery,
    current_risk_snapshot,
):
    """Build and evaluate final pre-entry safety state.

    No MT5 calls and no journal I/O occur here.
    All inputs are already-established runtime facts.
    """

    portfolio_recovery_valid = bool(
        runtime_portfolio_risk_recovery
        is not None
        and
        runtime_portfolio_risk_recovery.valid
    )

    portfolio_snapshot_present = bool(
        current_risk_snapshot is not None
    )

    lifecycle_state_valid = bool(
        portfolio_recovery_valid
        and
        portfolio_snapshot_present
    )

    memory_state_consistent = bool(
        portfolio_recovery_valid
        and
        portfolio_snapshot_present
    )

    governor_state_consistent = bool(
        portfolio_recovery_valid
        and
        portfolio_snapshot_present
    )

    open_position_count = (
        int(
            runtime_portfolio_risk_recovery
            .open_position_count
        )
        if portfolio_recovery_valid
        else -1
    )

    total_open_risk_percent = (
        float(
            current_risk_snapshot
            .total_risk_percent
        )
        if portfolio_snapshot_present
        else float("nan")
    )

    facts = ShadowLiveRuntimeSafetyFacts(
        manual_kill_switch_active=bool(
            manual_kill_switch_active
        ),
        mt5_initialized=bool(
            mt5_initialized
        ),
        terminal_available=bool(
            terminal_available
        ),
        account_available=bool(
            account_available
        ),
        time_authority_confirmed=bool(
            time_authority_confirmed
        ),
        portfolio_recovery_valid=(
            portfolio_recovery_valid
        ),
        portfolio_snapshot_present=(
            portfolio_snapshot_present
        ),
        lifecycle_state_valid=(
            lifecycle_state_valid
        ),
        memory_state_consistent=(
            memory_state_consistent
        ),
        governor_state_consistent=(
            governor_state_consistent
        ),
        open_position_count=(
            open_position_count
        ),
        total_open_risk_percent=(
            total_open_risk_percent
        ),
        max_open_positions=(
            MAX_OPEN_SHADOW_POSITIONS
        ),
        max_total_open_risk_percent=(
            PortfolioRiskGovernor
            .MAX_TOTAL_OPEN_RISK_PERCENT
        ),
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter
        .build(
            facts
        )
    )

    return (
        ShadowLiveSafetyGovernor
        .evaluate(
            state
        )
    )


def journal_path_for(
    symbol: str,
) -> Path:
    return (
        ROOT
        / "shadow_data"
        / "live"
        / "sprint92h14_6"
        / safe_symbol_name(symbol)
        / "shadow_positions.jsonl"
    )


def predecessor_journal_path_for(
    symbol: str,
) -> Path:
    """
    Read-only predecessor namespace.

    H14.6 must never ignore an open H14.5c
    Shadow position merely because the new sprint
    uses a separate journal namespace.
    """
    return (
        ROOT
        / "shadow_data"
        / "live"
        / "sprint92h14_5c"
        / safe_symbol_name(symbol)
        / "shadow_positions.jsonl"
    )




class RuntimePortfolioSafetyError(RuntimeError):
    def __init__(
        self,
        reason: str,
        detail: str = "",
    ):
        self.reason = reason
        self.detail = detail

        message = reason

        if detail:
            message = (
                f"{reason}:{detail}"
            )

        super().__init__(
            message
        )

class PostOpenPortfolioSafetyStop(RuntimeError):
    def __init__(
        self,
        reason: str,
        detail: str = "",
    ):
        self.reason = reason
        self.detail = detail

        message = reason

        if detail:
            message = (
                f"{reason}:{detail}"
            )

        super().__init__(
            message
        )


def refresh_runtime_portfolio_state(
    *,
    symbols,
    states,
    position,
    position_symbol,
):
    """Recover authoritative current portfolio state.

    This function is read-only with respect to journals.
    It cross-checks:
    - per-symbol lifecycle recovery
    - aggregated portfolio risk recovery
    - governor position conversion
    - in-memory single-position lifecycle state
    """

    if (
        (position is None)
        !=
        (position_symbol is None)
    ):
        raise RuntimePortfolioSafetyError(
            "MEMORY_STATE_INCONSISTENT",
            "RUNTIME_POSITION_MEMORY_STATE_INVALID",
        )

    runtime_sources = tuple(
        ShadowPortfolioJournalSource(
            symbol=symbol,
            journal_path=str(
                states[symbol][
                    "journal_path"
                ]
            ),
        )
        for symbol in symbols
    )

    runtime_portfolio_recovery = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=runtime_sources
        )
    )

    if not runtime_portfolio_recovery.valid:
        raise RuntimePortfolioSafetyError(
            "PORTFOLIO_RECOVERY_INVALID",
            (
                "RUNTIME_PORTFOLIO_RISK_RECOVERY_FAILED:"
                f"{runtime_portfolio_recovery.reason}:"
                f"{runtime_portfolio_recovery.failed_symbol}:"
                f"{runtime_portfolio_recovery.failed_reason}"
            ),
        )

    if (
        runtime_portfolio_recovery.snapshot
        is None
    ):
        raise RuntimePortfolioSafetyError(
            "PORTFOLIO_SNAPSHOT_MISSING",
            "RUNTIME_PORTFOLIO_RISK_SNAPSHOT_MISSING",
        )

    runtime_snapshot = (
        runtime_portfolio_recovery.snapshot
    )

    runtime_governor_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            runtime_snapshot
        )
    )

    if (
        len(runtime_governor_positions)
        !=
        len(runtime_snapshot.positions)
    ):
        raise RuntimePortfolioSafetyError(
            "GOVERNOR_STATE_INCONSISTENT",
            (
                "RUNTIME_PORTFOLIO_GOVERNOR_"
                "POSITION_CONVERSION_MISMATCH"
            ),
        )

    lifecycle_positions = []

    for symbol in symbols:
        lifecycle_recovery = (
            ShadowPositionRecovery
            .recover(
                states[symbol][
                    "journal_path"
                ]
            )
        )

        if not lifecycle_recovery.valid:
            raise RuntimePortfolioSafetyError(
                "LIFECYCLE_STATE_INVALID",
                (
                    "RUNTIME_LIFECYCLE_RECOVERY_FAILED:"
                    f"{symbol}:"
                    f"{lifecycle_recovery.reason}"
                ),
            )

        if (
            lifecycle_recovery
            .open_position_count
            > 1
        ):
            raise RuntimePortfolioSafetyError(
                "PORTFOLIO_LIMITS_INVALID",
                (
                    "RUNTIME_SYMBOL_MULTI_POSITION_"
                    f"STATE_DETECTED:{symbol}"
                ),
            )

        if (
            lifecycle_recovery
            .open_position_count
            == 1
        ):
            if (
                lifecycle_recovery.position
                is None
            ):
                raise RuntimePortfolioSafetyError(
                    "LIFECYCLE_STATE_INVALID",
                    (
                        "RUNTIME_LIFECYCLE_"
                        f"POSITION_MISSING:{symbol}"
                    ),
                )

            lifecycle_positions.append(
                (
                    symbol,
                    lifecycle_recovery.position,
                )
            )

    lifecycle_identity = tuple(
        sorted(
            (
                symbol,
                recovered_position.position_id,
            )
            for (
                symbol,
                recovered_position,
            ) in lifecycle_positions
        )
    )

    risk_identity = tuple(
        sorted(
            (
                risk_position.symbol,
                risk_position.position_id,
            )
            for risk_position
            in runtime_snapshot.positions
        )
    )

    if lifecycle_identity != risk_identity:
        raise RuntimePortfolioSafetyError(
            "LIFECYCLE_STATE_INVALID",
            (
                "RUNTIME_PORTFOLIO_LIFECYCLE_"
                "RISK_IDENTITY_MISMATCH"
            ),
        )

    if (
        len(lifecycle_positions)
        >
        MAX_OPEN_SHADOW_POSITIONS
    ):
        raise RuntimePortfolioSafetyError(
            "PORTFOLIO_LIMITS_INVALID",
            "RUNTIME_GLOBAL_SHADOW_POSITION_LIMIT_VIOLATED",
        )

    if position is None:
        memory_identity = ()
    else:
        memory_identity = (
            (
                position_symbol,
                position.position_id,
            ),
        )

    if lifecycle_identity != memory_identity:
        raise RuntimePortfolioSafetyError(
            "MEMORY_STATE_INCONSISTENT",
            (
                "RUNTIME_PORTFOLIO_MEMORY_"
                "IDENTITY_MISMATCH:"
                f"{lifecycle_identity}:"
                f"{memory_identity}"
            ),
        )

    return (
        runtime_portfolio_recovery,
        runtime_snapshot,
        runtime_governor_positions,
    )


def new_stats():
    return {
        "bar_transitions_observed": 0,
        "wait_decisions": 0,
        "decision_blocks": 0,
        "time_authority_blocks": 0,
        "entry_windows_missed": 0,
        "portfolio_lock_blocks": 0,
        "positions_opened": 0,
        "positions_closed": 0,
        "positions_recovered": 0,
        "analysis_completed": 0,
        "analysis_failed": 0,
        "policy_candidates": 0,
        "policy_allowed": 0,
        "policy_blocks": 0,
        "arbitration_selections": 0,
        "global_safety_blocks": 0,
    }


def evaluate_signal_snapshot(
    symbol: str,
    rates,
    current_bar_epoch: int,
):
    engine = (
        LiveCompletedCandleSignalEngine()
    )

    return engine.evaluate(
        symbol=symbol,
        rates=rates,
        current_bar_epoch=(
            current_bar_epoch
        ),
    )


def direction_trade_allowed(
    *,
    symbol_info,
    direction: str,
) -> bool:
    if symbol_info is None:
        return False

    mode = int(
        getattr(
            symbol_info,
            "trade_mode",
            -1,
        )
    )

    direction = (
        str(direction)
        .strip()
        .upper()
    )

    full_mode = int(
        getattr(
            mt5,
            "SYMBOL_TRADE_MODE_FULL",
            4,
        )
    )

    long_only_mode = int(
        getattr(
            mt5,
            "SYMBOL_TRADE_MODE_LONGONLY",
            1,
        )
    )

    short_only_mode = int(
        getattr(
            mt5,
            "SYMBOL_TRADE_MODE_SHORTONLY",
            2,
        )
    )

    if direction == "BUY":
        return mode in (
            full_mode,
            long_only_mode,
        )

    if direction == "SELL":
        return mode in (
            full_mode,
            short_only_mode,
        )

    return False


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbols",
        default=",".join(
            DEFAULT_SYMBOLS
        ),
    )

    parser.add_argument(
        "--max-seconds",
        type=float,
        default=0.0,
        help=(
            "0 means continuous until Ctrl+C."
        ),
    )

    args = parser.parse_args()

    symbols = tuple(
        item.strip()
        for item in str(
            args.symbols
        ).split(",")
        if item.strip()
    )

    if not symbols:
        raise RuntimeError(
            "SYMBOLS_REQUIRED"
        )

    if (
        len(set(symbols))
        != len(symbols)
    ):
        raise RuntimeError(
            "DUPLICATE_SYMBOLS_NOT_ALLOWED"
        )

    session_start = int(
        time.time()
    )

    report_path = (
        ROOT
        / "reports"
        / (
            "MSS_Sprint92H14_6_"
            "Live_Policy_Multi_Symbol_"
            f"Shadow_Session_{session_start}.json"
        )
    )

    original_order_send = getattr(
        mt5,
        "order_send",
        None,
    )

    original_order_check = getattr(
        mt5,
        "order_check",
        None,
    )

    guard_state = {
        "order_send_called": False,
        "order_check_called": False,
        "order_send_attempt_count": 0,
        "order_check_attempt_count": 0,
    }

    states = {}

    global_stats = {
        "symbols_requested": len(symbols),
        "symbols_enabled": 0,
        "symbols_disabled": 0,
        "bar_transitions_observed": 0,
        "wait_decisions": 0,
        "decision_blocks": 0,
        "time_authority_blocks": 0,
        "entry_windows_missed": 0,
        "portfolio_lock_blocks": 0,
        "positions_opened": 0,
        "positions_closed": 0,
        "positions_recovered": 0,
        "analysis_completed": 0,
        "analysis_failed": 0,
        "policy_candidates": 0,
        "policy_allowed": 0,
        "policy_blocks": 0,
        "arbitration_selections": 0,
        "global_safety_blocks": 0,
    }

    initialized = False
    final_status = (
        "SESSION_NOT_STARTED"
    )

    position = None
    position_symbol = None

    portfolio_risk_recovery = None
    portfolio_governor_positions = ()

    predecessor_portfolio_recovery = None
    predecessor_consumption_result = None
    predecessor_consumed = False
    portfolio_continuity_result = None

    safety_runtime = {
        "manual_kill_switch_observed": False,
        "manual_kill_switch_block_count": 0,
        "last_global_safety_reason": None,
        "last_global_safety_detail": None,
    }

    runtime_telemetry_state = None
    runtime_heartbeat_last_monotonic = None
    runtime_heartbeat_sequence = 0

    runtime_supervisor_last_reason = None
    runtime_supervisor_last_detail = None
    runtime_supervisor_hard_block_count = 0

    runtime_test_stall_injected = False

    runtime_test_disconnect_cycles = int(
        os.environ.get(
            "MSS_H14_6_TEST_MT5_DISCONNECT_CYCLES",
            "0",
        )
    )

    if runtime_test_disconnect_cycles < 0:
        raise ValueError(
            "INVALID_H14_6_TEST_MT5_DISCONNECT_CYCLES"
        )

    runtime_test_disconnect_cycles_remaining = (
        runtime_test_disconnect_cycles
    )

    runtime_test_disconnect_observed = False

    runtime_test_stall_seconds = float(
        os.environ.get(
            "MSS_H14_6_TEST_RUNTIME_STALL_SECONDS",
            "0",
        )
    )

    if runtime_test_stall_seconds < 0.0:
        raise ValueError(
            "INVALID_H14_6_TEST_RUNTIME_STALL_SECONDS"
        )

    try:
        mt5.order_send = (
            make_execution_guard(
                api_name="order_send",
                state=guard_state,
            )
        )

        if (
            original_order_check
            is not None
        ):
            mt5.order_check = (
                make_execution_guard(
                    api_name="order_check",
                    state=guard_state,
                )
            )

        # ---------------------------------------------
        # Initial read-only safety check per symbol.
        # ---------------------------------------------

        for symbol in symbols:
            state = {
                "enabled": False,
                "disabled_reason": "",
                "anchor_bar_epoch": 0,
                "previous_broker_offset_seconds": None,
                "point": 0.0,
                "symbol_info": None,
                "journal_path": (
                    journal_path_for(
                        symbol
                    )
                ),
                "stats": new_stats(),
            }

            states[symbol] = state

            try:
                observation = (
                    LiveMarketObserver.observe(
                        symbol=symbol,
                    )
                )

                if not observation[
                    "safety"
                ][
                    "shadow_observation_allowed"
                ]:
                    raise RuntimeError(
                        "INITIAL_SHADOW_"
                        "OBSERVATION_NOT_SAFE"
                    )

                authority = observation[
                    "time_authority"
                ]

                if (
                    authority[
                        "time_authority"
                    ][
                        "status"
                    ]
                    !=
                    "BROKER_TIME_DOMAIN_CONFIRMED"
                ):
                    raise RuntimeError(
                        "INITIAL_TIME_AUTHORITY_"
                        "NOT_CONFIRMED"
                    )

                state[
                    "previous_broker_offset_seconds"
                ] = int(
                    authority[
                        "observation"
                    ][
                        "detected_broker_offset_seconds"
                    ]
                )

            except Exception as exc:
                state[
                    "disabled_reason"
                ] = (
                    "INITIAL_OBSERVATION_FAILED:"
                    f"{exc}"
                )

                global_stats[
                    "symbols_disabled"
                ] += 1

                print(
                    "SYMBOL_DISABLED",
                    symbol,
                    state[
                        "disabled_reason"
                    ],
                )

        if not mt5.initialize():
            raise RuntimeError(
                "MT5_INITIALIZE_FAILED:"
                f"{mt5.last_error()}"
            )

        initialized = True

        recovered = []

        # ---------------------------------------------
        # Metadata/history/recovery.
        # ---------------------------------------------

        for symbol in symbols:
            state = states[symbol]

            # =========================================
            # H14.5c STARTUP LIFECYCLE CONTINUITY.
            #
            # Journal recovery is independent from
            # current feed/entry eligibility.
            #
            # A symbol may be unsafe for NEW entries
            # while still owning an existing Shadow
            # position that MUST remain recoverable
            # and monitorable.
            # =========================================

            recovery = (
                ShadowPositionRecovery
                .recover(
                    state[
                        "journal_path"
                    ]
                )
            )

            if not recovery.valid:
                raise RuntimeError(
                    "SHADOW_POSITION_"
                    "RECOVERY_FAILED:"
                    f"{symbol}:"
                    f"{recovery.reason}"
                )

            if (
                recovery.open_position_count
                == 1
            ):
                rp = (
                    recovery.position
                )

                if rp is None:
                    raise RuntimeError(
                        "RECOVERED_POSITION_MISSING:"
                        f"{symbol}"
                    )

                if (
                    rp.symbol
                    != symbol
                ):
                    raise RuntimeError(
                        "RECOVERED_POSITION_"
                        "SYMBOL_MISMATCH:"
                        f"{symbol}:"
                        f"{rp.symbol}"
                    )

                recovered.append(
                    (
                        symbol,
                        rp,
                    )
                )

                state[
                    "stats"
                ][
                    "positions_recovered"
                ] += 1

            # Feed/entry eligibility remains separate.
            # Do not force an unsafe symbol enabled.
            if state[
                "disabled_reason"
            ]:
                continue

            try:
                if not mt5.symbol_select(
                    symbol,
                    True,
                ):
                    raise RuntimeError(
                        "MT5_SYMBOL_SELECT_FAILED"
                    )

                info = mt5.symbol_info(
                    symbol
                )

                if info is None:
                    raise RuntimeError(
                        "MT5_SYMBOL_INFO_UNAVAILABLE"
                    )

                point = float(
                    getattr(
                        info,
                        "point",
                        0.0,
                    )
                    or 0.0
                )

                if point <= 0:
                    raise RuntimeError(
                        "INVALID_SYMBOL_POINT"
                    )

                state[
                    "symbol_info"
                ] = info

                state[
                    "point"
                ] = point

                state[
                    "journal_path"
                ].parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                rates = load_rates(
                    symbol
                )

                if (
                    len(rates)
                    < MIN_REQUIRED_RATES
                ):
                    raise RuntimeError(
                        "INSUFFICIENT_INITIAL_"
                        "M15_HISTORY"
                    )

                anchor = (
                    latest_bar_epoch(
                        rates
                    )
                )

                if anchor <= 0:
                    raise RuntimeError(
                        "INVALID_INITIAL_BAR_EPOCH"
                    )

                state[
                    "anchor_bar_epoch"
                ] = anchor

                state[
                    "enabled"
                ] = True

                global_stats[
                    "symbols_enabled"
                ] += 1

                print(
                    "SYMBOL_READY",
                    symbol,
                    "ANCHOR",
                    anchor,
                )

            except Exception as exc:
                state[
                    "enabled"
                ] = False

                state[
                    "disabled_reason"
                ] = (
                    "INITIALIZATION_FAILED:"
                    f"{exc}"
                )

                global_stats[
                    "symbols_disabled"
                ] += 1

                print(
                    "SYMBOL_DISABLED",
                    symbol,
                    state[
                        "disabled_reason"
                    ],
                )

        if (
            global_stats[
                "symbols_enabled"
            ]
            <= 0
        ):
            raise RuntimeError(
                "NO_SAFE_SYMBOLS_AVAILABLE"
            )

        # =============================================
        # H14.5b.1:
        # Recover deterministic portfolio risk state
        # from ALL current per-symbol journals.
        #
        # This is cross-checked against the existing
        # lifecycle recovery before any live loop starts.
        # =============================================

        current_portfolio_sources = tuple(
            ShadowPortfolioJournalSource(
                symbol=symbol,
                journal_path=str(
                    states[symbol][
                        "journal_path"
                    ]
                ),
            )
            for symbol in symbols
        )

        portfolio_risk_recovery = (
            ShadowPortfolioRiskAggregator
            .recover(
                sources=current_portfolio_sources
            )
        )

        if not portfolio_risk_recovery.valid:
            raise RuntimeError(
                "PORTFOLIO_RISK_RECOVERY_FAILED:"
                f"{portfolio_risk_recovery.reason}:"
                f"{portfolio_risk_recovery.failed_symbol}:"
                f"{portfolio_risk_recovery.failed_reason}"
            )

        if (
            portfolio_risk_recovery.snapshot
            is None
        ):
            raise RuntimeError(
                "PORTFOLIO_RISK_SNAPSHOT_MISSING"
            )

        current_risk_snapshot = (
            portfolio_risk_recovery.snapshot
        )

        portfolio_governor_positions = (
            ShadowPortfolioRiskState
            .governor_positions(
                current_risk_snapshot
            )
        )

        if (
            len(portfolio_governor_positions)
            !=
            len(current_risk_snapshot.positions)
        ):
            raise RuntimeError(
                "PORTFOLIO_GOVERNOR_POSITION_"
                "CONVERSION_MISMATCH"
            )

        lifecycle_recovery_identity = tuple(
            sorted(
                (
                    symbol,
                    recovered_position.position_id,
                )
                for (
                    symbol,
                    recovered_position,
                ) in recovered
            )
        )

        portfolio_recovery_identity = tuple(
            sorted(
                (
                    risk_position.symbol,
                    risk_position.position_id,
                )
                for risk_position
                in current_risk_snapshot.positions
            )
        )

        if (
            lifecycle_recovery_identity
            !=
            portfolio_recovery_identity
        ):
            raise RuntimeError(
                "PORTFOLIO_LIFECYCLE_"
                "RECOVERY_MISMATCH:"
                f"{lifecycle_recovery_identity}:"
                f"{portfolio_recovery_identity}"
            )

        if (
            portfolio_risk_recovery
            .open_position_count
            >
            MAX_OPEN_SHADOW_POSITIONS
        ):
            raise RuntimeError(
                "GLOBAL_PORTFOLIO_RISK_"
                "POSITION_LIMIT_VIOLATED_"
                "ON_RECOVERY"
            )

        print(
            "PORTFOLIO_RISK_RECOVERY",
            portfolio_risk_recovery.reason,
        )

        print(
            "PORTFOLIO_RISK_OPEN_POSITION_COUNT",
            portfolio_risk_recovery
            .open_position_count,
        )

        print(
            "PORTFOLIO_RISK_TOTAL_PERCENT",
            current_risk_snapshot
            .total_risk_percent,
        )

        print(
            "PORTFOLIO_RISK_TOTAL_AMOUNT",
            current_risk_snapshot
            .total_risk_amount,
        )

        print(
            "PORTFOLIO_LIFECYCLE_CROSSCHECK_OK",
            True,
        )

        # =============================================
        # Read-only predecessor safety guard.
        #
        # H14.5c is frozen evidence and is NEVER
        # written by this runner.
        #
        # If an H14.5c position is still open,
        # H14.6 must not start a fresh portfolio
        # as though that exposure did not exist.
        # =============================================

        predecessor_sources = tuple(
            ShadowPortfolioJournalSource(
                symbol=symbol,
                journal_path=str(
                    predecessor_journal_path_for(
                        symbol
                    )
                ),
            )
            for symbol in symbols
        )

        predecessor_portfolio_recovery = (
            ShadowPortfolioRiskAggregator
            .recover(
                sources=predecessor_sources
            )
        )

        if not predecessor_portfolio_recovery.valid:
            raise RuntimeError(
                "PREDECESSOR_PORTFOLIO_"
                "RECOVERY_FAILED:"
                f"{predecessor_portfolio_recovery.reason}:"
                f"{predecessor_portfolio_recovery.failed_symbol}:"
                f"{predecessor_portfolio_recovery.failed_reason}"
            )

        if (
            predecessor_portfolio_recovery.snapshot
            is None
        ):
            raise RuntimeError(
                "PREDECESSOR_PORTFOLIO_"
                "SNAPSHOT_MISSING"
            )

        predecessor_snapshot = (
            predecessor_portfolio_recovery.snapshot
        )

        print(
            "PREDECESSOR_H14_5C_OPEN_POSITION_COUNT",
            predecessor_portfolio_recovery
            .open_position_count,
        )

        print(
            "PREDECESSOR_H14_5C_TOTAL_RISK_PERCENT",
            predecessor_snapshot
            .total_risk_percent,
        )

        for legacy_position in (
            predecessor_snapshot.positions
        ):
            print(
                "PREDECESSOR_OPEN_POSITION",
                legacy_position.symbol,
                legacy_position.position_id,
                "RISK_PERCENT",
                legacy_position.risk_percent,
            )

        # =============================================
        # Read-only predecessor consumption evidence.
        #
        # If exactly one predecessor position exists,
        # determine whether that exact position has
        # already been carried into the H14.6
        # journal namespace.
        #
        # No journal write is permitted here.
        # =============================================

        predecessor_consumed = False

        if (
            predecessor_portfolio_recovery
            .open_position_count
            == 1
        ):
            legacy_position = (
                predecessor_snapshot.positions[0]
            )

            current_consumption_journal_path = (
                ROOT
                / "shadow_data"
                / "live"
                / "sprint92h14_6"
                / safe_symbol_name(
                    legacy_position.symbol
                )
                / "shadow_positions.jsonl"
            )

            predecessor_consumption_result = (
                ShadowPortfolioCarryForward
                .inspect_consumption(
                    predecessor_journal_path=(
                        predecessor_journal_path_for(
                            legacy_position.symbol
                        )
                    ),
                    current_journal_path=(
                        current_consumption_journal_path
                    ),
                    expected_position_id=(
                        legacy_position.position_id
                    ),
                    expected_symbol=(
                        legacy_position.symbol
                    ),
                )
            )

            print(
                "PREDECESSOR_CONSUMPTION_VALID",
                predecessor_consumption_result.valid,
            )
            print(
                "PREDECESSOR_CONSUMED",
                predecessor_consumption_result.consumed,
            )
            print(
                "PREDECESSOR_CONSUMPTION_REASON",
                predecessor_consumption_result.reason,
            )
            print(
                "PREDECESSOR_CONSUMPTION_SYMBOL",
                predecessor_consumption_result.symbol,
            )
            print(
                "PREDECESSOR_CONSUMPTION_POSITION_ID",
                predecessor_consumption_result.position_id,
            )

            if not predecessor_consumption_result.valid:
                raise RuntimeError(
                    "PREDECESSOR_CONSUMPTION_"
                    "INSPECTION_FAILED:"
                    f"{predecessor_consumption_result.reason}"
                )

            if (
                predecessor_consumption_result.position_id
                !=
                legacy_position.position_id
                or
                predecessor_consumption_result.symbol
                !=
                legacy_position.symbol
            ):
                raise RuntimeError(
                    "PREDECESSOR_CONSUMPTION_"
                    "IDENTITY_MISMATCH"
                )

            predecessor_consumed = (
                predecessor_consumption_result
                .consumed
            )

        else:
            print(
                "PREDECESSOR_CONSUMPTION_VALID",
                True,
            )
            print(
                "PREDECESSOR_CONSUMED",
                False,
            )
            print(
                "PREDECESSOR_CONSUMPTION_REASON",
                (
                    "NO_SINGLE_PREDECESSOR_"
                    "POSITION_TO_INSPECT"
                ),
            )

        # =============================================
        # Continuity-aware predecessor gate.
        #
        # The predecessor journal remains READ-ONLY.
        #
        # Allowed:
        # - both namespaces empty
        # - current namespace has its own active position
        #   and predecessor has none
        # - current position is the exact carry-forward
        #   successor of the predecessor position
        #
        # Blocked:
        # - predecessor-only open position
        #   (migration still required)
        # - any current/predecessor conflict
        # - invalid/multiple-position state
        # - unknown continuity action/reason
        # =============================================

        portfolio_continuity_result = (
            ShadowPortfolioContinuityPolicy
            .evaluate(
                current_snapshot=(
                    current_risk_snapshot
                ),
                predecessor_snapshot=(
                    predecessor_snapshot
                ),
                predecessor_consumed=(
                    predecessor_consumed
                ),
            )
        )

        print(
            "PORTFOLIO_CONTINUITY_VALID",
            portfolio_continuity_result.valid,
        )
        print(
            "PORTFOLIO_CONTINUITY_ACTION",
            portfolio_continuity_result.action,
        )
        print(
            "PORTFOLIO_CONTINUITY_REASON",
            portfolio_continuity_result.reason,
        )
        print(
            "PORTFOLIO_CONTINUITY_SYMBOL",
            portfolio_continuity_result.symbol,
        )
        print(
            "PORTFOLIO_CONTINUITY_POSITION_ID",
            portfolio_continuity_result.position_id,
        )

        if not portfolio_continuity_result.valid:
            raise RuntimeError(
                "SHADOW_PORTFOLIO_CONTINUITY_BLOCK:"
                f"{portfolio_continuity_result.reason}"
            )

        if (
            portfolio_continuity_result.action
            == "IMPORT_REQUIRED"
        ):
            raise RuntimeError(
                "PREDECESSOR_H14_5C_"
                "POSITION_IMPORT_REQUIRED:"
                f"{portfolio_continuity_result.symbol}:"
                f"{portfolio_continuity_result.position_id}"
            )

        allowed_continuity_reasons = {
            "CONTINUITY_CLEAR",
            "CURRENT_POSITION_ACTIVE",
            "CURRENT_SUPERSEDES_PREDECESSOR",
            "PREDECESSOR_POSITION_ALREADY_CONSUMED",
        }

        if (
            portfolio_continuity_result.action
            != "CONTINUE"
            or
            portfolio_continuity_result.reason
            not in allowed_continuity_reasons
        ):
            raise RuntimeError(
                "UNEXPECTED_SHADOW_PORTFOLIO_"
                "CONTINUITY_STATE:"
                f"{portfolio_continuity_result.action}:"
                f"{portfolio_continuity_result.reason}"
            )

        print(
            "PORTFOLIO_CONTINUITY_GATE_OK",
            True,
        )

        print(
            "PREDECESSOR_H14_5C_CLEAR",
            (
                predecessor_portfolio_recovery
                .open_position_count
                == 0
            ),
        )

        print(
            "PREDECESSOR_H14_5C_SUPERSEDED",
            (
                portfolio_continuity_result.reason
                ==
                "CURRENT_SUPERSEDES_PREDECESSOR"
            ),
        )

        if (
            len(recovered)
            >
            MAX_OPEN_SHADOW_POSITIONS
        ):
            raise RuntimeError(
                "GLOBAL_SHADOW_POSITION_"
                "LIMIT_VIOLATED_ON_RECOVERY"
            )

        if recovered:
            (
                position_symbol,
                position,
            ) = recovered[0]

            global_stats[
                "positions_recovered"
            ] = 1

            print(
                "RECOVERY",
                "OPEN_SHADOW_POSITION_RECOVERED",
            )

            print(
                "POSITION_SYMBOL",
                position_symbol,
            )

            print(
                "POSITION_ID",
                position.position_id,
            )

        start_monotonic = (
            time.monotonic()
        )

        runtime_telemetry_state = (
            ShadowLiveRuntimeTelemetry
            .initialize(
                started_monotonic=(
                    start_monotonic
                )
            )
        )

        final_status = (
            "LONG_RUNNING_SHADOW_LIVE_"
            "SESSION_RUNNING"
        )

        print(
            "STATUS",
            final_status,
        )

        print(
            "SYMBOLS_ENABLED",
            global_stats[
                "symbols_enabled"
            ],
        )

        print(
            "ANALYSIS_WORKERS",
            min(
                MAX_ANALYSIS_WORKERS,
                len(symbols),
            ),
        )

        print(
            "MAX_OPEN_SHADOW_POSITIONS",
            MAX_OPEN_SHADOW_POSITIONS,
        )

        print(
            "ENTRY_FRESHNESS_LIMIT_SECONDS",
            CausalNextCandleEntryWatcher
            .MAX_ENTRY_OBSERVATION_DELAY_SECONDS,
        )

        print(
            "REAL_ORDER_SEND_ALLOWED",
            False,
        )

        print(
            "TRUE_OOS_ACCESS",
            False,
        )

        with ThreadPoolExecutor(
            max_workers=min(
                MAX_ANALYSIS_WORKERS,
                len(symbols),
            )
        ) as executor:

            while True:
                if (
                    args.max_seconds > 0
                    and (
                        time.monotonic()
                        - start_monotonic
                    )
                    >= args.max_seconds
                ):
                    final_status = (
                        "SESSION_MAX_SECONDS_REACHED"
                    )
                    break

                # -----------------------------------------
                # Natural monitoring of the single
                # currently-open virtual position.
                # -----------------------------------------

                if (
                    position is not None
                    and
                    position_symbol is not None
                ):
                    tick = (
                        mt5.symbol_info_tick(
                            position_symbol
                        )
                    )

                    if validate_tick(
                        tick
                    ):
                        state = states[
                            position_symbol
                        ]

                        update_result = (
                            ShadowTradeEngine
                            .update_trade(
                                journal_path=(
                                    state[
                                        "journal_path"
                                    ]
                                ),
                                position=position,
                                bid=float(
                                    tick.bid
                                ),
                                ask=float(
                                    tick.ask
                                ),
                                broker_epoch=int(
                                    tick.time
                                ),
                            )
                        )

                        if not update_result.valid:
                            raise RuntimeError(
                                "SHADOW_POSITION_"
                                "UPDATE_FAILED:"
                                f"{update_result.reason}"
                            )

                        position = (
                            update_result.position
                        )

                        if (
                            update_result.action
                            ==
                            "POSITION_CLOSED"
                        ):
                            state[
                                "stats"
                            ][
                                "positions_closed"
                            ] += 1

                            global_stats[
                                "positions_closed"
                            ] += 1

                            print(
                                "SHADOW_POSITION_CLOSED",
                                position_symbol,
                                position.position_id,
                            )

                            print(
                                "EXIT_REASON",
                                position.exit_reason,
                            )

                            print(
                                "PNL_ACCOUNT_CURRENCY",
                                position.pnl_account_currency,
                            )

                            print(
                                "R_MULTIPLE",
                                position.r_multiple,
                            )

                            position = None
                            position_symbol = None

                # =========================================
                # H14.5b.1 runtime authoritative portfolio
                # refresh.
                #
                # This occurs AFTER current-position lifecycle
                # monitoring and BEFORE candidate discovery.
                # Any POSITION_CLOSED event written above is
                # therefore reflected immediately.
                # =========================================

                try:
                    (
                        runtime_portfolio_risk_recovery,
                        current_risk_snapshot,
                        portfolio_governor_positions,
                    ) = refresh_runtime_portfolio_state(
                        symbols=symbols,
                        states=states,
                        position=position,
                        position_symbol=position_symbol,
                    )

                except RuntimePortfolioSafetyError as exc:
                    safety_runtime[
                        "last_global_safety_reason"
                    ] = exc.reason

                    safety_runtime[
                        "last_global_safety_detail"
                    ] = exc.detail

                    global_stats[
                        "global_safety_blocks"
                    ] += 1

                    if (
                        runtime_telemetry_state
                        is not None
                    ):
                        runtime_telemetry_state = (
                            ShadowLiveRuntimeTelemetry
                            .record_portfolio_recovery_failure(
                                runtime_telemetry_state,
                                reason=exc.reason,
                                detail=exc.detail,
                            )
                        )

                        runtime_telemetry_state = (
                            ShadowLiveRuntimeTelemetry
                            .record_safety_block(
                                runtime_telemetry_state,
                                reason=exc.reason,
                                detail=exc.detail,
                            )
                        )

                    print(
                        "GLOBAL_SESSION_ENTRY_INHIBIT",
                        exc.reason,
                    )

                    print(
                        "GLOBAL_SESSION_SAFETY_DETAIL",
                        exc.detail,
                    )

                    time.sleep(
                        POLL_SECONDS
                    )

                    continue

                # =========================================
                # H14.5c GLOBAL RUNTIME HEALTH WATCHDOG.
                #
                # Existing Shadow position lifecycle has
                # already been monitored above.
                #
                # Authoritative Portfolio state has already
                # been refreshed above.
                #
                # This gate inhibits NEW candidate discovery
                # only. Candidate-specific fresh Time
                # Authority is enforced later immediately
                # before Shadow position creation.
                # =========================================

                manual_kill_now = (
                    manual_kill_switch_requested()
                )

                terminal_now = (
                    mt5.terminal_info()
                    if initialized
                    else None
                )

                account_now = (
                    mt5.account_info()
                    if initialized
                    else None
                )

                terminal_connected = bool(
                    initialized
                    and
                    terminal_now is not None
                    and
                    getattr(
                        terminal_now,
                        "connected",
                        False,
                    )
                )

                effective_terminal_connected = (
                    terminal_connected
                )

                if (
                    runtime_test_disconnect_cycles_remaining
                    > 0
                ):
                    runtime_test_disconnect_observed = True

                    runtime_test_disconnect_cycles_remaining -= 1

                    effective_terminal_connected = False

                    print(
                        "H14_6_TEST_MT5_DISCONNECT_ACTIVE",
                        runtime_test_disconnect_cycles_remaining,
                    )

                runtime_kill_conditions = (
                    evaluate_session_runtime_health(
                        manual_kill_switch_active=(
                            manual_kill_now
                        ),
                        mt5_connected=(
                            effective_terminal_connected
                        ),
                        terminal_available=(
                            terminal_now is not None
                        ),
                        account_available=(
                            account_now is not None
                        ),
                        runtime_portfolio_risk_recovery=(
                            runtime_portfolio_risk_recovery
                        ),
                        current_risk_snapshot=(
                            current_risk_snapshot
                        ),
                    )
                )

                if runtime_kill_conditions:
                    runtime_reason = (
                        runtime_kill_conditions[0]
                    )

                    safety_runtime[
                        "last_global_safety_reason"
                    ] = runtime_reason

                    safety_runtime[
                        "last_global_safety_detail"
                    ] = (
                        repr(
                            runtime_kill_conditions
                        )
                    )

                    global_stats[
                        "global_safety_blocks"
                    ] += 1

                    if (
                        runtime_telemetry_state
                        is not None
                    ):
                        if runtime_reason in (
                            "MT5_NOT_CONNECTED",
                            "MT5_TERMINAL_UNAVAILABLE",
                            "MT5_ACCOUNT_UNAVAILABLE",
                        ):
                            runtime_telemetry_state = (
                                ShadowLiveRuntimeTelemetry
                                .record_disconnect(
                                    runtime_telemetry_state,
                                    reason=runtime_reason,
                                    detail=repr(
                                        runtime_kill_conditions
                                    ),
                                )
                            )

                        runtime_telemetry_state = (
                            ShadowLiveRuntimeTelemetry
                            .record_safety_block(
                                runtime_telemetry_state,
                                reason=runtime_reason,
                                detail=repr(
                                    runtime_kill_conditions
                                ),
                            )
                        )

                    if (
                        "MANUAL_KILL_SWITCH_ACTIVE"
                        in runtime_kill_conditions
                    ):
                        safety_runtime[
                            "manual_kill_switch_observed"
                        ] = True

                        safety_runtime[
                            "manual_kill_switch_block_count"
                        ] += 1

                    print(
                        "GLOBAL_SESSION_ENTRY_INHIBIT",
                        runtime_reason,
                    )

                    print(
                        "GLOBAL_SESSION_KILL_CONDITIONS",
                        runtime_kill_conditions,
                    )

                    time.sleep(
                        POLL_SECONDS
                    )

                    continue

                # =========================================
                # H14.6 LONG-RUNNING RUNTIME SUPERVISOR.
                #
                # Existing-position lifecycle monitoring
                # already occurred above.
                #
                # Authoritative portfolio recovery and the
                # H14.5c global safety watchdog have also
                # already passed.
                #
                # This layer adds monotonic heartbeat and
                # long-running runtime telemetry. It may
                # inhibit NEW candidate discovery only.
                # =========================================

                supervisor_now_monotonic = (
                    time.monotonic()
                )

                runtime_supervisor_decision = (
                    ShadowLiveRuntimeSupervisor
                    .evaluate(
                        supervisor=(
                            ShadowLiveRuntimeSupervisorInput(
                                started_monotonic=(
                                    start_monotonic
                                ),
                                now_monotonic=(
                                    supervisor_now_monotonic
                                ),
                                last_heartbeat_monotonic=(
                                    runtime_heartbeat_last_monotonic
                                ),
                                heartbeat_sequence=(
                                    runtime_heartbeat_sequence
                                ),
                                max_heartbeat_gap_seconds=(
                                    RUNTIME_HEARTBEAT_MAX_GAP_SECONDS
                                ),
                                mt5_connected=(
                                    effective_terminal_connected
                                ),
                                terminal_available=(
                                    terminal_now is not None
                                ),
                                account_available=(
                                    account_now is not None
                                ),
                                portfolio_recovery_valid=bool(
                                    runtime_portfolio_risk_recovery
                                    is not None
                                    and
                                    runtime_portfolio_risk_recovery
                                    .valid
                                    and
                                    current_risk_snapshot
                                    is not None
                                ),
                            )
                        ),
                        telemetry_state=(
                            runtime_telemetry_state
                        ),
                    )
                )

                runtime_telemetry_state = (
                    runtime_supervisor_decision
                    .telemetry_state
                )

                runtime_heartbeat_last_monotonic = (
                    runtime_supervisor_decision
                    .next_last_heartbeat_monotonic
                )

                runtime_heartbeat_sequence = (
                    runtime_supervisor_decision
                    .next_heartbeat_sequence
                )

                runtime_supervisor_last_reason = (
                    runtime_supervisor_decision.reason
                )

                runtime_supervisor_last_detail = (
                    runtime_supervisor_decision.detail
                )

                if (
                    runtime_test_stall_seconds > 0.0
                    and
                    not runtime_test_stall_injected
                    and
                    runtime_supervisor_decision.valid
                    and
                    not runtime_supervisor_decision.hard_block
                ):
                    runtime_test_stall_injected = True

                    print(
                        "H14_6_TEST_RUNTIME_STALL_BEGIN",
                        runtime_test_stall_seconds,
                    )

                    time.sleep(
                        runtime_test_stall_seconds
                    )

                    print(
                        "H14_6_TEST_RUNTIME_STALL_END",
                        runtime_test_stall_seconds,
                    )

                    continue

                if (
                    not runtime_supervisor_decision.valid
                    or
                    runtime_supervisor_decision.hard_block
                ):
                    runtime_supervisor_hard_block_count += 1

                    global_stats[
                        "global_safety_blocks"
                    ] += 1

                    safety_runtime[
                        "last_global_safety_reason"
                    ] = (
                        runtime_supervisor_decision
                        .reason
                    )

                    safety_runtime[
                        "last_global_safety_detail"
                    ] = (
                        runtime_supervisor_decision
                        .detail
                    )

                    print(
                        "RUNTIME_SUPERVISOR_ENTRY_INHIBIT",
                        runtime_supervisor_decision.reason,
                    )

                    print(
                        "RUNTIME_SUPERVISOR_DETAIL",
                        runtime_supervisor_decision.detail,
                    )

                    time.sleep(
                        POLL_SECONDS
                    )

                    continue

                # =========================================
                # PHASE 1:
                # Fast transition discovery for ALL symbols
                # before doing expensive MSS analysis.
                # =========================================

                transitions = []

                for symbol in symbols:
                    state = states[
                        symbol
                    ]

                    if not state[
                        "enabled"
                    ]:
                        continue

                    short_rates = (
                        mt5.copy_rates_from_pos(
                            symbol,
                            TIMEFRAME,
                            0,
                            3,
                        )
                    )

                    if (
                        short_rates is None
                        or
                        len(short_rates) == 0
                    ):
                        continue

                    current_epoch = (
                        latest_bar_epoch(
                            short_rates
                        )
                    )

                    anchor = int(
                        state[
                            "anchor_bar_epoch"
                        ]
                    )

                    if current_epoch <= 0:
                        continue

                    if (
                        current_epoch
                        < anchor
                    ):
                        raise RuntimeError(
                            "LIVE_BAR_TIME_REGRESSION:"
                            f"{symbol}"
                        )

                    if (
                        current_epoch
                        == anchor
                    ):
                        continue

                    state[
                        "stats"
                    ][
                        "bar_transitions_observed"
                    ] += 1

                    global_stats[
                        "bar_transitions_observed"
                    ] += 1

                    print(
                        "BAR_TRANSITION",
                        symbol,
                        anchor,
                        "->",
                        current_epoch,
                    )

                    transitions.append(
                        (
                            symbol,
                            anchor,
                            current_epoch,
                        )
                    )

                if not transitions:
                    time.sleep(
                        POLL_SECONDS
                    )
                    continue

                # =========================================
                # PHASE 2:
                # Capture authoritative market snapshots
                # quickly, before CPU signal analysis.
                # =========================================

                snapshots = []

                for (
                    symbol,
                    anchor,
                    current_epoch,
                ) in transitions:

                    state = states[
                        symbol
                    ]

                    try:
                        (
                            transition_tick,
                            authority,
                        ) = (
                            build_transition_time_authority(
                                symbol=symbol,
                                current_bar_epoch=(
                                    current_epoch
                                ),
                                previous_broker_offset_seconds=(
                                    state[
                                        "previous_broker_offset_seconds"
                                    ]
                                ),
                            )
                        )

                        if not bool(
                            authority[
                                "time_authority"
                            ][
                                "confirmed"
                            ]
                        ):
                            state[
                                "stats"
                            ][
                                "time_authority_blocks"
                            ] += 1

                            global_stats[
                                "time_authority_blocks"
                            ] += 1

                            print(
                                "TIME_AUTHORITY_BLOCK",
                                symbol,
                                authority[
                                    "time_authority"
                                ][
                                    "status"
                                ],
                            )

                            state[
                                "anchor_bar_epoch"
                            ] = current_epoch

                            continue

                        state[
                            "previous_broker_offset_seconds"
                        ] = int(
                            authority[
                                "observation"
                            ][
                                "detected_broker_offset_seconds"
                            ]
                        )

                        rates = load_rates(
                            symbol
                        )

                        if (
                            len(rates)
                            < MIN_REQUIRED_RATES
                        ):
                            state[
                                "stats"
                            ][
                                "decision_blocks"
                            ] += 1

                            global_stats[
                                "decision_blocks"
                            ] += 1

                            print(
                                "DECISION_BLOCK",
                                symbol,
                                "INSUFFICIENT_M15_HISTORY",
                            )

                            state[
                                "anchor_bar_epoch"
                            ] = current_epoch

                            continue

                        snapshots.append(
                            {
                                "symbol": symbol,
                                "anchor": anchor,
                                "current_epoch": (
                                    current_epoch
                                ),
                                "rates": rates,
                            }
                        )

                    except Exception as exc:
                        state[
                            "enabled"
                        ] = False

                        state[
                            "disabled_reason"
                        ] = (
                            "SNAPSHOT_FAILURE:"
                            f"{exc}"
                        )

                        print(
                            "SYMBOL_DISABLED",
                            symbol,
                            state[
                                "disabled_reason"
                            ],
                        )

                # =========================================
                # PHASE 3:
                # Pure MSS signal evaluation concurrently.
                # No MT5 calls inside workers.
                # =========================================

                futures = {}

                for snap in snapshots:
                    future = executor.submit(
                        evaluate_signal_snapshot,
                        snap[
                            "symbol"
                        ],
                        snap[
                            "rates"
                        ],
                        snap[
                            "current_epoch"
                        ],
                    )

                    futures[
                        future
                    ] = snap

                # =========================================
                # PHASE 3A:
                # Collect concurrent analysis results only.
                #
                # Future completion order must never choose
                # the traded symbol.
                # =========================================

                analysis_results = {}

                for future in as_completed(
                    futures
                ):
                    snap = futures[
                        future
                    ]

                    symbol = snap[
                        "symbol"
                    ]

                    state = states[
                        symbol
                    ]

                    try:
                        decision = (
                            future.result()
                        )

                        state[
                            "stats"
                        ][
                            "analysis_completed"
                        ] += 1

                        global_stats[
                            "analysis_completed"
                        ] += 1

                        analysis_results[
                            symbol
                        ] = {
                            "snap": snap,
                            "decision": decision,
                        }

                    except Exception as exc:
                        state[
                            "stats"
                        ][
                            "analysis_failed"
                        ] += 1

                        global_stats[
                            "analysis_failed"
                        ] += 1

                        print(
                            "ANALYSIS_BLOCK",
                            symbol,
                            repr(exc),
                        )

                # =========================================
                # H14.5a integration continues below.
                #
                # At this checkpoint we intentionally do
                # NOT open any new Shadow position from
                # collected results.
                # =========================================

                # =========================================
                # PHASE 4:
                # Deterministic causal candidate preparation.
                #
                # IMPORTANT:
                # analysis_results were produced concurrently,
                # but candidates are processed strictly in the
                # frozen `symbols` priority order.
                # =========================================

                policy_inputs = []
                candidate_context = {}

                for symbol in symbols:
                    item = (
                        analysis_results.get(
                            symbol
                        )
                    )

                    if item is None:
                        continue

                    snap = item[
                        "snap"
                    ]

                    decision = item[
                        "decision"
                    ]

                    anchor_epoch = snap[
                        "anchor"
                    ]

                    current_epoch = snap[
                        "current_epoch"
                    ]

                    rates = snap[
                        "rates"
                    ]

                    state = states[
                        symbol
                    ]

                    if not decision.valid:
                        state[
                            "stats"
                        ][
                            "decision_blocks"
                        ] += 1

                        global_stats[
                            "decision_blocks"
                        ] += 1

                        print(
                            "DECISION_BLOCK",
                            symbol,
                            decision.reason,
                        )

                        continue

                    sequence_confirmed = (
                        decision.signal_bar_epoch
                        == anchor_epoch
                    )

                    frozen_signal = (
                        decision.frozen_signal
                    )

                    if (
                        frozen_signal is None
                        or
                        not frozen_signal.valid
                    ):
                        state[
                            "stats"
                        ][
                            "wait_decisions"
                        ] += 1

                        global_stats[
                            "wait_decisions"
                        ] += 1

                        print(
                            "MSS_DECISION",
                            symbol,
                            "WAIT",
                            decision.reason,
                        )

                        continue

                    current_rate = find_rate(
                        rates,
                        current_epoch,
                    )

                    if current_rate is None:
                        state[
                            "stats"
                        ][
                            "entry_windows_missed"
                        ] += 1

                        global_stats[
                            "entry_windows_missed"
                        ] += 1

                        print(
                            "ENTRY_WINDOW_MISSED",
                            symbol,
                            "CURRENT_RATE_NOT_FOUND",
                        )

                        continue

                    # -------------------------------------
                    # Fresh causal observation AFTER all
                    # concurrent CPU analysis is complete.
                    # -------------------------------------

                    try:
                        (
                            fresh_tick,
                            fresh_authority,
                        ) = (
                            build_transition_time_authority(
                                symbol=symbol,
                                current_bar_epoch=(
                                    current_epoch
                                ),
                                previous_broker_offset_seconds=(
                                    state[
                                        "previous_broker_offset_seconds"
                                    ]
                                ),
                            )
                        )

                    except Exception as exc:
                        state[
                            "stats"
                        ][
                            "time_authority_blocks"
                        ] += 1

                        global_stats[
                            "time_authority_blocks"
                        ] += 1

                        print(
                            "FINAL_TIME_AUTHORITY_BLOCK",
                            symbol,
                            repr(exc),
                        )

                        continue

                    if not bool(
                        fresh_authority[
                            "time_authority"
                        ][
                            "confirmed"
                        ]
                    ):
                        state[
                            "stats"
                        ][
                            "time_authority_blocks"
                        ] += 1

                        global_stats[
                            "time_authority_blocks"
                        ] += 1

                        print(
                            "FINAL_TIME_AUTHORITY_BLOCK",
                            symbol,
                            fresh_authority[
                                "time_authority"
                            ][
                                "status"
                            ],
                        )

                        continue

                    state[
                        "previous_broker_offset_seconds"
                    ] = int(
                        fresh_authority[
                            "observation"
                        ][
                            "detected_broker_offset_seconds"
                        ]
                    )

                    spread_points = (
                        observed_spread_points(
                            current_rate=(
                                current_rate
                            ),
                            symbol_info=(
                                state[
                                    "symbol_info"
                                ]
                            ),
                            tick=fresh_tick,
                        )
                    )

                    watch_result = (
                        CausalNextCandleEntryWatcher
                        .evaluate(
                            signal=(
                                frozen_signal
                            ),
                            previous_current_bar_epoch=(
                                anchor_epoch
                            ),
                            current_bar_epoch=(
                                current_epoch
                            ),
                            observation_broker_epoch=int(
                                fresh_tick.time
                            ),
                            next_candle_sequence_confirmed=(
                                sequence_confirmed
                            ),
                            next_candle_open=float(
                                rate_value(
                                    current_rate,
                                    "open",
                                )
                            ),
                            spread_points=(
                                spread_points
                            ),
                            point=float(
                                state[
                                    "point"
                                ]
                            ),
                        )
                    )

                    if (
                        not watch_result.valid
                        or
                        not watch_result
                        .shadow_entry_allowed
                    ):
                        state[
                            "stats"
                        ][
                            "entry_windows_missed"
                        ] += 1

                        global_stats[
                            "entry_windows_missed"
                        ] += 1

                        print(
                            "ENTRY_BLOCK",
                            symbol,
                            watch_result.action,
                            watch_result.reason,
                        )

                        continue

                    entry = (
                        watch_result.entry
                    )

                    if entry is None:
                        state[
                            "stats"
                        ][
                            "decision_blocks"
                        ] += 1

                        global_stats[
                            "decision_blocks"
                        ] += 1

                        print(
                            "DECISION_BLOCK",
                            symbol,
                            "WATCH_ENTRY_MISSING",
                        )

                        continue

                    quote_fresh = bool(
                        validate_tick(
                            fresh_tick
                        )
                        and
                        watch_result
                        .observation_delay_seconds
                        >= 0
                        and
                        watch_result
                        .observation_delay_seconds
                        <=
                        CausalNextCandleEntryWatcher
                        .MAX_ENTRY_OBSERVATION_DELAY_SECONDS
                    )

                    symbol_tradable = (
                        direction_trade_allowed(
                            symbol_info=(
                                state[
                                    "symbol_info"
                                ]
                            ),
                            direction=(
                                entry.direction
                            ),
                        )
                    )

                    policy_inputs.append(
                        ShadowRiskCandidateInput(
                            symbol=symbol,
                            direction=(
                                entry.direction
                            ),
                            bid=float(
                                fresh_tick.bid
                            ),
                            ask=float(
                                fresh_tick.ask
                            ),
                            entry_price=float(
                                entry.entry_price
                            ),
                            stop_loss=float(
                                entry.stop_loss
                            ),
                            symbol_tradable=(
                                symbol_tradable
                            ),
                            quote_fresh=(
                                quote_fresh
                            ),
                            risk_percent=float(
                                entry.risk_percent
                            ),
                        )
                    )

                    candidate_context[
                        symbol
                    ] = {
                        "anchor": (
                            anchor_epoch
                        ),
                        "current_epoch": (
                            current_epoch
                        ),
                        "current_rate": (
                            current_rate
                        ),
                        "frozen_signal": (
                            frozen_signal
                        ),
                        "sequence_confirmed": (
                            sequence_confirmed
                        ),
                    }

                    state[
                        "stats"
                    ][
                        "policy_candidates"
                    ] += 1

                    global_stats[
                        "policy_candidates"
                    ] += 1

                    print(
                        "POLICY_CANDIDATE_READY",
                        symbol,
                        entry.direction,
                        "DELAY_SECONDS",
                        watch_result
                        .observation_delay_seconds,
                    )

                print(
                    "POLICY_CANDIDATE_COUNT",
                    len(policy_inputs),
                )

                # =========================================
                # PHASE 5:
                # Deterministic H14.5 policy evaluation.
                #
                # Still observation-only at this checkpoint:
                # NO ShadowTradeEngine.open_trade here.
                # =========================================

                selected_symbol = None
                policy_result = None

                # H14.5a remains SINGLE-POSITION.
                # Portfolio multi-position enablement is
                # explicitly deferred to a later sprint.
                if (
                    policy_inputs
                    and
                    position is not None
                ):
                    for candidate in policy_inputs:
                        state = states[
                            candidate.symbol
                        ]

                        state[
                            "stats"
                        ][
                            "portfolio_lock_blocks"
                        ] += 1

                        global_stats[
                            "portfolio_lock_blocks"
                        ] += 1

                        print(
                            "PORTFOLIO_LOCK_BLOCK",
                            candidate.symbol,
                            "OPEN_POSITION_SYMBOL",
                            position_symbol,
                        )

                    policy_inputs = []

                if policy_inputs:
                    policy_result = (
                        MultiAssetShadowRiskPolicy
                        .evaluate(
                            candidates=(
                                policy_inputs
                            ),
                            open_positions=portfolio_governor_positions,
                            symbol_priority=(
                                symbols
                            ),
                        )
                    )

                    for evaluation in (
                        policy_result.evaluations
                    ):
                        state = states[
                            evaluation.symbol
                        ]

                        print(
                            "POLICY_EVALUATION",
                            evaluation.symbol,
                            "ELIGIBLE",
                            evaluation.eligible,
                            "REASON",
                            evaluation.reason,
                            "SPREAD_STOP_RATIO",
                            (
                                evaluation
                                .spread_to_stop_ratio
                            ),
                        )

                        if evaluation.eligible:
                            state[
                                "stats"
                            ][
                                "policy_allowed"
                            ] += 1

                            global_stats[
                                "policy_allowed"
                            ] += 1

                        else:
                            state[
                                "stats"
                            ][
                                "policy_blocks"
                            ] += 1

                            global_stats[
                                "policy_blocks"
                            ] += 1

                    if policy_result.allowed:
                        selected_symbol = (
                            policy_result
                            .selected_symbol
                        )

                        if selected_symbol is None:
                            raise RuntimeError(
                                "POLICY_ALLOWED_WITHOUT_"
                                "SELECTED_SYMBOL"
                            )

                        states[
                            selected_symbol
                        ][
                            "stats"
                        ][
                            "arbitration_selections"
                        ] += 1

                        global_stats[
                            "arbitration_selections"
                        ] += 1

                        print(
                            "POLICY_SELECTED",
                            selected_symbol,
                            policy_result.reason,
                        )

                        print(
                            "POLICY_ELIGIBLE_SYMBOLS",
                            ",".join(
                                policy_result
                                .arbitration
                                .eligible_symbols
                            ),
                        )

                    else:
                        print(
                            "POLICY_ARBITRATION_BLOCK",
                            policy_result.reason,
                        )

                else:
                    print(
                        "POLICY_NO_CANDIDATES"
                    )

                # =========================================
                # PHASE 6:
                # FINAL selected-candidate causal
                # revalidation immediately before opening.
                #
                # If the selected candidate becomes stale,
                # it is blocked. We DO NOT fall back to a
                # lower-priority candidate retrospectively.
                # =========================================

                if selected_symbol is not None:
                    context = candidate_context[
                        selected_symbol
                    ]

                    state = states[
                        selected_symbol
                    ]

                    anchor_epoch = context[
                        "anchor"
                    ]

                    current_epoch = context[
                        "current_epoch"
                    ]

                    current_rate = context[
                        "current_rate"
                    ]

                    frozen_signal = context[
                        "frozen_signal"
                    ]

                    sequence_confirmed = context[
                        "sequence_confirmed"
                    ]

                    try:
                        (
                            final_tick,
                            final_authority,
                        ) = (
                            build_transition_time_authority(
                                symbol=selected_symbol,
                                current_bar_epoch=(
                                    current_epoch
                                ),
                                previous_broker_offset_seconds=(
                                    state[
                                        "previous_broker_offset_seconds"
                                    ]
                                ),
                            )
                        )

                    except Exception as exc:
                        state[
                            "stats"
                        ][
                            "time_authority_blocks"
                        ] += 1

                        global_stats[
                            "time_authority_blocks"
                        ] += 1

                        print(
                            "SELECTED_FINAL_TIME_AUTHORITY_BLOCK",
                            selected_symbol,
                            repr(exc),
                        )

                        final_tick = None
                        final_authority = None

                    if (
                        final_tick is not None
                        and
                        final_authority is not None
                    ):
                        if not bool(
                            final_authority[
                                "time_authority"
                            ][
                                "confirmed"
                            ]
                        ):
                            state[
                                "stats"
                            ][
                                "time_authority_blocks"
                            ] += 1

                            global_stats[
                                "time_authority_blocks"
                            ] += 1

                            print(
                                "SELECTED_FINAL_TIME_AUTHORITY_BLOCK",
                                selected_symbol,
                                final_authority[
                                    "time_authority"
                                ][
                                    "status"
                                ],
                            )

                        else:
                            state[
                                "previous_broker_offset_seconds"
                            ] = int(
                                final_authority[
                                    "observation"
                                ][
                                    "detected_broker_offset_seconds"
                                ]
                            )

                            final_spread_points = (
                                observed_spread_points(
                                    current_rate=(
                                        current_rate
                                    ),
                                    symbol_info=(
                                        state[
                                            "symbol_info"
                                        ]
                                    ),
                                    tick=final_tick,
                                )
                            )

                            final_watch = (
                                CausalNextCandleEntryWatcher
                                .evaluate(
                                    signal=frozen_signal,
                                    previous_current_bar_epoch=(
                                        anchor_epoch
                                    ),
                                    current_bar_epoch=(
                                        current_epoch
                                    ),
                                    observation_broker_epoch=int(
                                        final_tick.time
                                    ),
                                    next_candle_sequence_confirmed=(
                                        sequence_confirmed
                                    ),
                                    next_candle_open=float(
                                        rate_value(
                                            current_rate,
                                            "open",
                                        )
                                    ),
                                    spread_points=(
                                        final_spread_points
                                    ),
                                    point=float(
                                        state[
                                            "point"
                                        ]
                                    ),
                                )
                            )

                            if (
                                not final_watch.valid
                                or
                                not final_watch
                                .shadow_entry_allowed
                            ):
                                state[
                                    "stats"
                                ][
                                    "entry_windows_missed"
                                ] += 1

                                global_stats[
                                    "entry_windows_missed"
                                ] += 1

                                print(
                                    "SELECTED_FINAL_ENTRY_BLOCK",
                                    selected_symbol,
                                    final_watch.action,
                                    final_watch.reason,
                                )

                            elif final_watch.entry is None:
                                state[
                                    "stats"
                                ][
                                    "decision_blocks"
                                ] += 1

                                global_stats[
                                    "decision_blocks"
                                ] += 1

                                print(
                                    "SELECTED_FINAL_ENTRY_BLOCK",
                                    selected_symbol,
                                    "ENTRY_OBJECT_MISSING",
                                )

                            else:
                                final_entry = (
                                    final_watch.entry
                                )

                                final_quote_fresh = bool(
                                    validate_tick(
                                        final_tick
                                    )
                                    and
                                    final_watch
                                    .observation_delay_seconds
                                    >= 0
                                    and
                                    final_watch
                                    .observation_delay_seconds
                                    <=
                                    CausalNextCandleEntryWatcher
                                    .MAX_ENTRY_OBSERVATION_DELAY_SECONDS
                                )

                                final_tradable = (
                                    direction_trade_allowed(
                                        symbol_info=(
                                            state[
                                                "symbol_info"
                                            ]
                                        ),
                                        direction=(
                                            final_entry
                                            .direction
                                        ),
                                    )
                                )

                                try:
                                    (
                                        runtime_portfolio_risk_recovery,
                                        current_risk_snapshot,
                                        portfolio_governor_positions,
                                    ) = refresh_runtime_portfolio_state(
                                        symbols=symbols,
                                        states=states,
                                        position=position,
                                        position_symbol=position_symbol,
                                    )

                                except RuntimePortfolioSafetyError as exc:
                                    safety_runtime[
                                        "last_global_safety_reason"
                                    ] = exc.reason

                                    safety_runtime[
                                        "last_global_safety_detail"
                                    ] = exc.detail

                                    global_stats[
                                        "global_safety_blocks"
                                    ] += 1

                                    state[
                                        "stats"
                                    ][
                                        "policy_blocks"
                                    ] += 1

                                    global_stats[
                                        "policy_blocks"
                                    ] += 1

                                    print(
                                        "GLOBAL_ENTRY_SAFETY_HARD_BLOCK",
                                        selected_symbol,
                                        exc.reason,
                                    )

                                    print(
                                        "GLOBAL_ENTRY_SAFETY_DETAIL",
                                        exc.detail,
                                    )

                                    continue

                                final_policy = (
                                    MultiAssetShadowRiskPolicy
                                    .evaluate(
                                        candidates=(
                                            ShadowRiskCandidateInput(
                                                symbol=(
                                                    selected_symbol
                                                ),
                                                direction=(
                                                    final_entry
                                                    .direction
                                                ),
                                                bid=float(
                                                    final_tick.bid
                                                ),
                                                ask=float(
                                                    final_tick.ask
                                                ),
                                                entry_price=float(
                                                    final_entry
                                                    .entry_price
                                                ),
                                                stop_loss=float(
                                                    final_entry
                                                    .stop_loss
                                                ),
                                                symbol_tradable=(
                                                    final_tradable
                                                ),
                                                quote_fresh=(
                                                    final_quote_fresh
                                                ),
                                                risk_percent=float(
                                                    final_entry
                                                    .risk_percent
                                                ),
                                            ),
                                        ),
                                        open_positions=portfolio_governor_positions,
                                        symbol_priority=(
                                            selected_symbol,
                                        ),
                                    )
                                )

                                if not final_policy.allowed:
                                    state[
                                        "stats"
                                    ][
                                        "policy_blocks"
                                    ] += 1

                                    global_stats[
                                        "policy_blocks"
                                    ] += 1

                                    print(
                                        "SELECTED_FINAL_POLICY_BLOCK",
                                        selected_symbol,
                                        final_policy.reason,
                                    )

                                    for evaluation in (
                                        final_policy.evaluations
                                    ):
                                        print(
                                            "FINAL_POLICY_EVALUATION",
                                            evaluation.symbol,
                                            evaluation.reason,
                                            "SPREAD_STOP_RATIO",
                                            evaluation
                                            .spread_to_stop_ratio,
                                        )

                                else:
                                    # =====================================
                                    # H14.5c FINAL PRE-ENTRY GLOBAL
                                    # SAFETY GOVERNOR.
                                    #
                                    # This is the last global safety gate
                                    # before any new Shadow position may
                                    # be created.
                                    # =====================================

                                    terminal = (
                                        mt5.terminal_info()
                                    )

                                    account = (
                                        mt5.account_info()
                                    )

                                    entry_safety = (
                                        evaluate_entry_safety(
                                            manual_kill_switch_active=(
                                                manual_kill_switch_requested()
                                            ),
                                            mt5_initialized=(
                                                initialized
                                            ),
                                            terminal_available=(
                                                terminal
                                                is not None
                                            ),
                                            account_available=(
                                                account
                                                is not None
                                            ),
                                            time_authority_confirmed=bool(
                                                fresh_authority[
                                                    "time_authority"
                                                ][
                                                    "confirmed"
                                                ]
                                            ),
                                            runtime_portfolio_risk_recovery=(
                                                runtime_portfolio_risk_recovery
                                            ),
                                            current_risk_snapshot=(
                                                current_risk_snapshot
                                            ),
                                        )
                                    )

                                    if not (
                                        entry_safety
                                        .trading_allowed
                                    ):
                                        safety_runtime[
                                            "last_global_safety_reason"
                                        ] = (
                                            entry_safety.reason
                                        )

                                        safety_runtime[
                                            "last_global_safety_detail"
                                        ] = repr(
                                            entry_safety
                                            .kill_conditions
                                        )

                                        if (
                                            "MANUAL_KILL_SWITCH_ACTIVE"
                                            in
                                            entry_safety.kill_conditions
                                        ):
                                            safety_runtime[
                                                "manual_kill_switch_observed"
                                            ] = True

                                            safety_runtime[
                                                "manual_kill_switch_block_count"
                                            ] += 1

                                        global_stats[
                                            "global_safety_blocks"
                                        ] += 1

                                        state[
                                            "stats"
                                        ][
                                            "policy_blocks"
                                        ] += 1

                                        global_stats[
                                            "policy_blocks"
                                        ] += 1

                                        print(
                                            "GLOBAL_ENTRY_SAFETY_HARD_BLOCK",
                                            selected_symbol,
                                            entry_safety.reason,
                                        )

                                        print(
                                            "GLOBAL_ENTRY_SAFETY_KILL_CONDITIONS",
                                            entry_safety.kill_conditions,
                                        )

                                        continue

                                    print(
                                        "GLOBAL_ENTRY_SAFETY_CONFIRMED",
                                        selected_symbol,
                                        entry_safety.reason,
                                    )

                                    balance = float(
                                        getattr(
                                            account,
                                            "balance",
                                            0.0,
                                        )
                                        or 0.0
                                    )

                                    if balance <= 0:
                                        raise RuntimeError(
                                            "INVALID_ACCOUNT_BALANCE"
                                        )

                                    position_id = (
                                        "SHADOW-"
                                        f"{safe_symbol_name(selected_symbol)}-"
                                        f"{current_epoch}"
                                    )

                                    open_result = (
                                        ShadowTradeEngine
                                        .open_trade(
                                            journal_path=(
                                                state[
                                                    "journal_path"
                                                ]
                                            ),
                                            position_id=(
                                                position_id
                                            ),
                                            symbol=(
                                                selected_symbol
                                            ),
                                            direction=(
                                                final_entry
                                                .direction
                                            ),
                                            balance=balance,
                                            risk_percent=(
                                                final_entry
                                                .risk_percent
                                            ),
                                            entry_price=(
                                                final_entry
                                                .entry_price
                                            ),
                                            stop_loss=(
                                                final_entry
                                                .stop_loss
                                            ),
                                            take_profit=(
                                                final_entry
                                                .take_profit
                                            ),
                                            broker_epoch=(
                                                current_epoch
                                            ),
                                        )
                                    )

                                    if not open_result.valid:
                                        print(
                                            "SHADOW_OPEN_BLOCKED",
                                            selected_symbol,
                                            open_result.reason,
                                        )

                                    else:
                                        position = (
                                            open_result.position
                                        )

                                        position_symbol = (
                                            selected_symbol
                                        )

                                        state[
                                            "stats"
                                        ][
                                            "positions_opened"
                                        ] += 1

                                        global_stats[
                                            "positions_opened"
                                        ] += 1

                                        print(
                                            "SHADOW_POSITION_OPENED",
                                            selected_symbol,
                                            position.position_id,
                                        )

                                        try:
                                            (
                                                runtime_portfolio_risk_recovery,
                                                current_risk_snapshot,
                                                portfolio_governor_positions,
                                            ) = refresh_runtime_portfolio_state(
                                                symbols=symbols,
                                                states=states,
                                                position=position,
                                                position_symbol=position_symbol,
                                            )

                                        except RuntimePortfolioSafetyError as exc:
                                            safety_runtime[
                                                "last_global_safety_reason"
                                            ] = exc.reason

                                            safety_runtime[
                                                "last_global_safety_detail"
                                            ] = exc.detail

                                            global_stats[
                                                "global_safety_blocks"
                                            ] += 1

                                            print(
                                                "POST_OPEN_PORTFOLIO_SAFETY_FAILURE",
                                                exc.reason,
                                            )

                                            print(
                                                "POST_OPEN_PORTFOLIO_SAFETY_DETAIL",
                                                exc.detail,
                                            )

                                            raise PostOpenPortfolioSafetyStop(
                                                exc.reason,
                                                exc.detail,
                                            ) from exc

                                        print(
                                            "RUNTIME_PORTFOLIO_REFRESH_AFTER_OPEN",
                                            True,
                                        )
                                        print(
                                            "RUNTIME_PORTFOLIO_OPEN_POSITION_COUNT",
                                            runtime_portfolio_risk_recovery
                                            .open_position_count,
                                        )
                                        print(
                                            "RUNTIME_PORTFOLIO_TOTAL_RISK_PERCENT",
                                            current_risk_snapshot
                                            .total_risk_percent,
                                        )

                                        print(
                                            "DIRECTION",
                                            position.direction,
                                        )

                                        print(
                                            "VOLUME",
                                            position.volume,
                                        )

                                        print(
                                            "ENTRY_PRICE",
                                            position.entry_price,
                                        )

                                        print(
                                            "STOP_LOSS",
                                            position.stop_loss,
                                        )

                                        print(
                                            "TAKE_PROFIT",
                                            position.take_profit,
                                        )

                                        print(
                                            "REAL_ORDER_SENT",
                                            False,
                                        )

                # Ensure transitions whose futures were
                # processed always advance their anchor.
                for snap in snapshots:
                    symbol = snap[
                        "symbol"
                    ]

                    state = states[
                        symbol
                    ]

                    if (
                        state[
                            "anchor_bar_epoch"
                        ]
                        < snap[
                            "current_epoch"
                        ]
                    ):
                        state[
                            "anchor_bar_epoch"
                        ] = snap[
                            "current_epoch"
                        ]

                time.sleep(
                    POLL_SECONDS
                )

    except PostOpenPortfolioSafetyStop as exc:
        final_status = (
            "SESSION_STOPPED_POST_OPEN_"
            "PORTFOLIO_SAFETY_FAILURE"
        )

        print(
            "STATUS",
            final_status,
        )

        print(
            "POST_OPEN_PORTFOLIO_SAFETY_REASON",
            exc.reason,
        )

        print(
            "POST_OPEN_PORTFOLIO_SAFETY_DETAIL",
            exc.detail,
        )

    except KeyboardInterrupt:
        final_status = (
            "SESSION_STOPPED_BY_USER"
        )

        print()
        print(
            "STATUS",
            final_status,
        )

    finally:
        session_end = int(
            time.time()
        )

        runtime_telemetry_snapshot = None

        if (
            runtime_telemetry_state
            is not None
        ):
            runtime_telemetry_snapshot = (
                ShadowLiveRuntimeTelemetry
                .snapshot(
                    runtime_telemetry_state,
                    now_monotonic=(
                        time.monotonic()
                    ),
                )
            )

        report = {
            "sprint": "92H.14.6",
            "mode": (
                "LIVE_POLICY_MULTI_SYMBOL_"
                "LONG_RUNNING_SUPERVISED_SINGLE_POSITION_SHADOW_SESSION"
            ),
            "symbols": list(
                symbols
            ),
            "max_open_shadow_positions": (
                MAX_OPEN_SHADOW_POSITIONS
            ),
            "analysis_workers": min(
                MAX_ANALYSIS_WORKERS,
                len(symbols),
            ),
            "session": {
                "start_utc_epoch": (
                    session_start
                ),
                "end_utc_epoch": (
                    session_end
                ),
                "final_status": (
                    final_status
                ),
                "poll_seconds": (
                    POLL_SECONDS
                ),
            },
            "stats": (
                global_stats
            ),
            "runtime_telemetry": {
                "available": (
                    runtime_telemetry_snapshot
                    is not None
                ),
                "valid": (
                    runtime_telemetry_snapshot.valid
                    if runtime_telemetry_snapshot
                    is not None
                    else False
                ),
                "reason": (
                    runtime_telemetry_snapshot.reason
                    if runtime_telemetry_snapshot
                    is not None
                    else None
                ),
                "uptime_seconds": (
                    runtime_telemetry_snapshot
                    .uptime_seconds
                    if runtime_telemetry_snapshot
                    is not None
                    else None
                ),
                "heartbeat_sequence": (
                    runtime_telemetry_snapshot
                    .heartbeat_sequence
                    if runtime_telemetry_snapshot
                    is not None
                    else 0
                ),
                "heartbeat_count": (
                    runtime_telemetry_snapshot
                    .heartbeat_count
                    if runtime_telemetry_snapshot
                    is not None
                    else 0
                ),
                "stale_heartbeat_count": (
                    runtime_telemetry_snapshot
                    .stale_heartbeat_count
                    if runtime_telemetry_snapshot
                    is not None
                    else 0
                ),
                "global_safety_block_count": (
                    runtime_telemetry_snapshot
                    .global_safety_block_count
                    if runtime_telemetry_snapshot
                    is not None
                    else 0
                ),
                "runtime_disconnect_count": (
                    runtime_telemetry_snapshot
                    .runtime_disconnect_count
                    if runtime_telemetry_snapshot
                    is not None
                    else 0
                ),
                "portfolio_recovery_failure_count": (
                    runtime_telemetry_snapshot
                    .portfolio_recovery_failure_count
                    if runtime_telemetry_snapshot
                    is not None
                    else 0
                ),
                "last_runtime_reason": (
                    runtime_telemetry_snapshot
                    .last_runtime_reason
                    if runtime_telemetry_snapshot
                    is not None
                    else None
                ),
                "last_runtime_detail": (
                    runtime_telemetry_snapshot
                    .last_runtime_detail
                    if runtime_telemetry_snapshot
                    is not None
                    else None
                ),
                "supervisor_last_reason": (
                    runtime_supervisor_last_reason
                ),
                "supervisor_last_detail": (
                    runtime_supervisor_last_detail
                ),
                "supervisor_hard_block_count": (
                    runtime_supervisor_hard_block_count
                ),
                "max_heartbeat_gap_seconds": (
                    RUNTIME_HEARTBEAT_MAX_GAP_SECONDS
                ),
                "test_runtime_stall_seconds": (
                    runtime_test_stall_seconds
                ),
                "test_runtime_stall_injected": (
                    runtime_test_stall_injected
                ),
                "test_disconnect_cycles": (
                    runtime_test_disconnect_cycles
                ),
                "test_disconnect_cycles_remaining": (
                    runtime_test_disconnect_cycles_remaining
                ),
                "test_disconnect_observed": (
                    runtime_test_disconnect_observed
                ),
            },
            "per_symbol": {
                symbol: {
                    "enabled": (
                        states[
                            symbol
                        ][
                            "enabled"
                        ]
                    ),
                    "disabled_reason": (
                        states[
                            symbol
                        ][
                            "disabled_reason"
                        ]
                    ),
                    "anchor_bar_epoch": (
                        states[
                            symbol
                        ][
                            "anchor_bar_epoch"
                        ]
                    ),
                    "journal_path": str(
                        states[
                            symbol
                        ][
                            "journal_path"
                        ]
                    ),
                    "stats": (
                        states[
                            symbol
                        ][
                            "stats"
                        ]
                    ),
                }
                for symbol in symbols
            },
            "safety": {
                "real_order_send_allowed": False,
                "order_send_called": (
                    guard_state[
                        "order_send_called"
                    ]
                ),
                "order_check_called": (
                    guard_state[
                        "order_check_called"
                    ]
                ),
                "order_send_attempt_count": (
                    guard_state[
                        "order_send_attempt_count"
                    ]
                ),
                "order_check_attempt_count": (
                    guard_state[
                        "order_check_attempt_count"
                    ]
                ),
                "global_single_position_lock": True,
                "retrospective_entry_allowed": False,
                "synthetic_exit_allowed": False,
                "fresh_tick_revalidated_after_analysis": True,
                "global_safety_governor_enabled": True,
                "manual_kill_switch_path": str(
                    MANUAL_KILL_SWITCH_PATH
                ),
                "manual_kill_switch_active_at_exit": (
                    manual_kill_switch_requested()
                ),
                "manual_kill_switch_observed": (
                    safety_runtime[
                        "manual_kill_switch_observed"
                    ]
                ),
                "manual_kill_switch_block_count": (
                    safety_runtime[
                        "manual_kill_switch_block_count"
                    ]
                ),
                "last_global_safety_reason": (
                    safety_runtime[
                        "last_global_safety_reason"
                    ]
                ),
                "last_global_safety_detail": (
                    safety_runtime[
                        "last_global_safety_detail"
                    ]
                ),
            },
            "strategy_contract": {
                "entry_rule": (
                    "NEXT_CANDLE_OPEN"
                ),
                "next_candle_definition": (
                    "ACTUAL_MT5_TRADING_BAR_SEQUENCE"
                ),
                "entry_transition_max_delay_seconds": (
                    CausalNextCandleEntryWatcher
                    .MAX_ENTRY_OBSERVATION_DELAY_SECONDS
                ),
                "completed_candles_only": True,
                "required_completed_candles": 500,
                "risk_percent": 1.0,
                "reward_risk_ratio": 2.0,
                "retuning": False,
                "direction_filtering": False,
                "confluence_used_as_gate": False,
            },
            "research_segregation": {
                "true_oos_data_accessed": False,
                "true_oos_artifacts_modified": False,
                "performance_evidence": False,
                "strategy_retuning_performed": False,
            },
            "open_position_at_exit": {
                "present": (
                    position is not None
                ),
                "symbol": (
                    position_symbol
                ),
                "position_id": (
                    position.position_id
                    if position is not None
                    else None
                ),
            },
        }

        print(
            "FINAL_STATUS",
            final_status,
        )

        print(
            "ORDER_SEND_ATTEMPT_COUNT",
            guard_state[
                "order_send_attempt_count"
            ],
        )

        print(
            "ORDER_CHECK_ATTEMPT_COUNT",
            guard_state[
                "order_check_attempt_count"
            ],
        )

        try:
            write_session_report(
                report_path=(
                    report_path
                ),
                payload=report,
            )

            print(
                "SESSION_REPORT",
                str(
                    report_path
                ),
            )

        except Exception as exc:
            print(
                "SESSION_REPORT_WRITE_FAILED",
                repr(exc),
            )

        if initialized:
            mt5.shutdown()

        if (
            original_order_send
            is not None
        ):
            mt5.order_send = (
                original_order_send
            )

        if (
            original_order_check
            is not None
        ):
            mt5.order_check = (
                original_order_check
            )


if __name__ == "__main__":
    main()
