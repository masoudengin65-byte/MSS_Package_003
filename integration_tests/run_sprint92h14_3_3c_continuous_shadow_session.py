"""Continuous causal Shadow Live session for MSS.

Sprint 92H.14.3.3c

Guarantees:
- no real MT5 order_send
- no real MT5 order_check
- no real order/position modification
- no True-OOS access
- completed M15 candles only
- NEXT_CANDLE_OPEN uses actual MT5 bar sequence
- entry transition freshness enforced
- broker time authority checked at runtime
- open Shadow positions recover from journal
- natural tick-driven SL/TP only
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.causal_next_candle_entry_watcher import (
    CausalNextCandleEntryWatcher,
)
from mss.analysis.global_time_authority import (
    GlobalTimeAuthority,
)
from mss.analysis.live_completed_candle_signal_engine import (
    LiveCompletedCandleSignalEngine,
)
from mss.analysis.live_market_observer import (
    LiveMarketObserver,
)
from mss.analysis.shadow_position_recovery import (
    ShadowPositionRecovery,
)
from mss.analysis.shadow_trade_engine import (
    ShadowTradeEngine,
)


ROOT = Path(__file__).resolve().parents[1]

TIMEFRAME = mt5.TIMEFRAME_M15

RATES_COUNT = 520
MIN_REQUIRED_RATES = 501

POLL_SECONDS = 0.25


def make_execution_guard(
    *,
    api_name: str,
    state: dict,
):
    def blocked_call(
        *args,
        **kwargs,
    ):
        state[
            f"{api_name}_called"
        ] = True

        state[
            f"{api_name}_attempt_count"
        ] += 1

        raise RuntimeError(
            "SHADOW_LIVE_REAL_EXECUTION_"
            f"GUARD_TRIGGERED:{api_name}"
        )

    return blocked_call


def rate_value(
    rate,
    name: str,
):
    try:
        return rate[name]
    except (
        TypeError,
        KeyError,
        IndexError,
        ValueError,
    ):
        return getattr(
            rate,
            name,
        )


def safe_symbol_name(
    symbol: str,
) -> str:
    value = "".join(
        character
        if (
            character.isalnum()
            or character in ("_", "-")
        )
        else "_"
        for character in symbol
    )

    return value or "SYMBOL"


def load_rates(
    symbol: str,
    count: int = RATES_COUNT,
):
    rates = mt5.copy_rates_from_pos(
        symbol,
        TIMEFRAME,
        0,
        count,
    )

    if rates is None:
        raise RuntimeError(
            "MT5_RATES_UNAVAILABLE: "
            f"{mt5.last_error()}"
        )

    return rates


def latest_bar_epoch(
    rates,
) -> int:
    if rates is None or len(rates) == 0:
        return 0

    return max(
        int(
            rate_value(
                rate,
                "time",
            )
        )
        for rate in rates
    )


def find_rate(
    rates,
    epoch: int,
):
    matching = [
        rate
        for rate in rates
        if int(
            rate_value(
                rate,
                "time",
            )
        )
        == int(epoch)
    ]

    if not matching:
        return None

    return matching[-1]


def observed_spread_points(
    *,
    current_rate,
    symbol_info,
    tick,
) -> float:

    try:
        value = float(
            rate_value(
                current_rate,
                "spread",
            )
        )

        if value >= 0:
            return value

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        pass

    reported = getattr(
        symbol_info,
        "spread",
        None,
    )

    if reported is not None:
        reported = float(
            reported
        )

        if reported >= 0:
            return reported

    point = float(
        getattr(
            symbol_info,
            "point",
            0.0,
        )
        or 0.0
    )

    bid = float(
        getattr(
            tick,
            "bid",
            0.0,
        )
        or 0.0
    )

    ask = float(
        getattr(
            tick,
            "ask",
            0.0,
        )
        or 0.0
    )

    if (
        point > 0
        and ask >= bid
        and bid > 0
    ):
        return (
            ask - bid
        ) / point

    raise RuntimeError(
        "SPREAD_POINTS_UNAVAILABLE"
    )


def build_transition_time_authority(
    *,
    symbol: str,
    current_bar_epoch: int,
    previous_broker_offset_seconds,
):

    utc_before = time.time()

    tick = mt5.symbol_info_tick(
        symbol
    )

    utc_after = time.time()

    if tick is None:
        raise RuntimeError(
            "MT5_TICK_UNAVAILABLE"
        )

    tick_epoch = int(
        getattr(
            tick,
            "time",
            0,
        )
        or 0
    )

    if tick_epoch <= 0:
        raise RuntimeError(
            "INVALID_MT5_TICK_EPOCH"
        )

    authority = (
        GlobalTimeAuthority()
        .build(
            utc_epoch_before_tick=(
                utc_before
            ),
            utc_epoch_after_tick=(
                utc_after
            ),
            tick_epoch=tick_epoch,
            current_bar_epoch=int(
                current_bar_epoch
            ),
            previous_broker_offset_seconds=(
                previous_broker_offset_seconds
            ),
        )
    )

    return (
        tick,
        authority,
    )


def validate_tick(
    tick,
):
    if tick is None:
        return False

    bid = float(
        getattr(
            tick,
            "bid",
            0.0,
        )
        or 0.0
    )

    ask = float(
        getattr(
            tick,
            "ask",
            0.0,
        )
        or 0.0
    )

    return (
        bid > 0
        and ask > 0
        and ask >= bid
    )


def write_session_report(
    *,
    report_path: Path,
    payload: dict,
):
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbol",
        default="USDJPY",
    )

    parser.add_argument(
        "--max-seconds",
        type=float,
        default=0.0,
        help=(
            "0 means continuous until Ctrl+C."
        ),
    )

    parser.add_argument(
        "--journal-path",
        default="",
        help=(
            "Optional Shadow-only journal path. "
            "Used for isolated validation/recovery sessions."
        ),
    )

    args = parser.parse_args()

    symbol = str(
        args.symbol
    ).strip()

    if not symbol:
        raise RuntimeError(
            "SYMBOL_REQUIRED"
        )

    safe_symbol = (
        safe_symbol_name(
            symbol
        )
    )

    if args.journal_path:
        journal_path = Path(
            args.journal_path
        )

        normalized_journal = (
            str(journal_path)
            .replace("\\", "/")
            .lower()
        )

        prohibited_fragments = (
            "sprint92h_true_oos",
            "true_oos_v2",
            "/true_oos/",
        )

        if any(
            fragment
            in normalized_journal
            for fragment
            in prohibited_fragments
        ):
            raise RuntimeError(
                "SHADOW_TRUE_OOS_NAMESPACE_COLLISION"
            )

    else:
        journal_path = (
            ROOT
            / "shadow_data"
            / "live"
            / "sprint92h14_3_3c"
            / safe_symbol
            / "shadow_positions.jsonl"
        )

    session_start_utc_epoch = int(
        time.time()
    )

    report_path = (
        ROOT
        / "reports"
        / (
            "MSS_Sprint92H14_3_3c_"
            "Continuous_Shadow_Session_"
            f"{session_start_utc_epoch}.json"
        )
    )

    journal_path.parent.mkdir(
        parents=True,
        exist_ok=True,
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

    execution_guard_state = {
        "order_send_called": False,
        "order_check_called": False,
        "order_send_attempt_count": 0,
        "order_check_attempt_count": 0,
    }

    initialized = False

    session_stats = {
        "bar_transitions_observed": 0,
        "wait_decisions": 0,
        "entry_windows_missed": 0,
        "positions_opened": 0,
        "positions_closed": 0,
        "positions_recovered": 0,
        "time_authority_blocks": 0,
        "decision_blocks": 0,
    }

    previous_broker_offset_seconds = None

    position = None
    anchor_bar_epoch = 0

    final_status = (
        "SESSION_NOT_STARTED"
    )

    try:
        mt5.order_send = (
            make_execution_guard(
                api_name="order_send",
                state=(
                    execution_guard_state
                ),
            )
        )

        if original_order_check is not None:
            mt5.order_check = (
                make_execution_guard(
                    api_name="order_check",
                    state=(
                        execution_guard_state
                    ),
                )
            )

        initial_observation = (
            LiveMarketObserver.observe(
                symbol=symbol,
            )
        )

        if not initial_observation[
            "safety"
        ][
            "shadow_observation_allowed"
        ]:
            raise RuntimeError(
                "INITIAL_SHADOW_OBSERVATION_NOT_SAFE"
            )

        initial_authority = (
            initial_observation[
                "time_authority"
            ]
        )

        authority_status = (
            initial_authority[
                "time_authority"
            ][
                "status"
            ]
        )

        if (
            authority_status
            != "BROKER_TIME_DOMAIN_CONFIRMED"
        ):
            raise RuntimeError(
                "INITIAL_TIME_AUTHORITY_NOT_CONFIRMED"
            )

        previous_broker_offset_seconds = int(
            initial_authority[
                "observation"
            ][
                "detected_broker_offset_seconds"
            ]
        )

        if not mt5.initialize():
            raise RuntimeError(
                "MT5_INITIALIZE_FAILED: "
                f"{mt5.last_error()}"
            )

        initialized = True

        if not mt5.symbol_select(
            symbol,
            True,
        ):
            raise RuntimeError(
                "MT5_SYMBOL_SELECT_FAILED"
            )

        symbol_info = mt5.symbol_info(
            symbol
        )

        if symbol_info is None:
            raise RuntimeError(
                "MT5_SYMBOL_INFO_UNAVAILABLE"
            )

        point = float(
            getattr(
                symbol_info,
                "point",
                0.0,
            )
            or 0.0
        )

        if point <= 0:
            raise RuntimeError(
                "INVALID_SYMBOL_POINT"
            )

        recovery = (
            ShadowPositionRecovery
            .recover(
                journal_path
            )
        )

        if not recovery.valid:
            raise RuntimeError(
                "SHADOW_POSITION_RECOVERY_FAILED: "
                f"{recovery.reason}"
            )

        if (
            recovery.open_position_count
            == 1
        ):
            position = (
                recovery.position
            )

            if (
                position.symbol
                != symbol
            ):
                raise RuntimeError(
                    "RECOVERED_POSITION_SYMBOL_MISMATCH"
                )

            session_stats[
                "positions_recovered"
            ] += 1

            print(
                "RECOVERY",
                "OPEN_SHADOW_POSITION_RECOVERED",
            )

            print(
                "POSITION_ID",
                position.position_id,
            )

        rates = load_rates(
            symbol
        )

        if len(rates) < MIN_REQUIRED_RATES:
            raise RuntimeError(
                "INSUFFICIENT_INITIAL_M15_HISTORY"
            )

        anchor_bar_epoch = (
            latest_bar_epoch(
                rates
            )
        )

        if anchor_bar_epoch <= 0:
            raise RuntimeError(
                "INVALID_INITIAL_BAR_EPOCH"
            )

        signal_engine = (
            LiveCompletedCandleSignalEngine()
        )

        start_monotonic = (
            time.monotonic()
        )

        final_status = (
            "SHADOW_SESSION_RUNNING"
        )

        print(
            "STATUS",
            final_status,
        )

        print(
            "SYMBOL",
            symbol,
        )

        print(
            "TIMEFRAME",
            "M15",
        )

        print(
            "POLL_SECONDS",
            POLL_SECONDS,
        )

        print(
            "REAL_ORDER_SEND_ALLOWED",
            False,
        )

        print(
            "ORDER_SEND_GUARD_INSTALLED",
            True,
        )

        print(
            "ORDER_CHECK_GUARD_INSTALLED",
            (
                original_order_check
                is not None
            ),
        )

        print(
            "TRUE_OOS_ACCESS",
            False,
        )

        print(
            "ANCHOR_BAR_EPOCH",
            anchor_bar_epoch,
        )

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

            # -------------------------------------------------
            # Existing open Shadow position:
            # monitor natural tick-driven SL / TP only.
            # -------------------------------------------------

            if position is not None:
                tick = mt5.symbol_info_tick(
                    symbol
                )

                if not validate_tick(
                    tick
                ):
                    time.sleep(
                        POLL_SECONDS
                    )

                    continue

                update_result = (
                    ShadowTradeEngine
                    .update_trade(
                        journal_path=(
                            journal_path
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
                        "SHADOW_POSITION_UPDATE_FAILED: "
                        f"{update_result.reason}"
                    )

                if (
                    update_result.action
                    == "POSITION_CLOSED"
                ):
                    position = (
                        update_result.position
                    )

                    session_stats[
                        "positions_closed"
                    ] += 1

                    print(
                        "SHADOW_POSITION_CLOSED",
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

                    rates = load_rates(
                        symbol
                    )

                    anchor_bar_epoch = (
                        latest_bar_epoch(
                            rates
                        )
                    )

                    print(
                        "NEW_ANCHOR_BAR_EPOCH",
                        anchor_bar_epoch,
                    )

                else:
                    position = (
                        update_result.position
                    )

                time.sleep(
                    POLL_SECONDS
                )

                continue

            # -------------------------------------------------
            # No open Shadow position:
            # wait for a real M15 transition.
            # -------------------------------------------------

            short_rates = mt5.copy_rates_from_pos(
                symbol,
                TIMEFRAME,
                0,
                3,
            )

            if (
                short_rates is None
                or len(short_rates) == 0
            ):
                time.sleep(
                    POLL_SECONDS
                )

                continue

            current_bar_epoch = (
                latest_bar_epoch(
                    short_rates
                )
            )

            if current_bar_epoch <= 0:
                time.sleep(
                    POLL_SECONDS
                )

                continue

            if (
                current_bar_epoch
                < anchor_bar_epoch
            ):
                raise RuntimeError(
                    "LIVE_BAR_TIME_REGRESSION"
                )

            if (
                current_bar_epoch
                == anchor_bar_epoch
            ):
                time.sleep(
                    POLL_SECONDS
                )

                continue

            session_stats[
                "bar_transitions_observed"
            ] += 1

            print(
                "BAR_TRANSITION",
                anchor_bar_epoch,
                "->",
                current_bar_epoch,
            )

            # Capture the first available tick around
            # transition and validate broker time authority.
            (
                transition_tick,
                transition_authority,
            ) = (
                build_transition_time_authority(
                    symbol=symbol,
                    current_bar_epoch=(
                        current_bar_epoch
                    ),
                    previous_broker_offset_seconds=(
                        previous_broker_offset_seconds
                    ),
                )
            )

            authority_status = (
                transition_authority[
                    "time_authority"
                ][
                    "status"
                ]
            )

            authority_confirmed = bool(
                transition_authority[
                    "time_authority"
                ][
                    "confirmed"
                ]
            )

            if not authority_confirmed:
                session_stats[
                    "time_authority_blocks"
                ] += 1

                print(
                    "TIME_AUTHORITY_BLOCK",
                    authority_status,
                )

                anchor_bar_epoch = (
                    current_bar_epoch
                )

                continue

            previous_broker_offset_seconds = int(
                transition_authority[
                    "observation"
                ][
                    "detected_broker_offset_seconds"
                ]
            )

            rates = load_rates(
                symbol
            )

            if len(rates) < MIN_REQUIRED_RATES:
                session_stats[
                    "decision_blocks"
                ] += 1

                print(
                    "DECISION_BLOCK",
                    "INSUFFICIENT_M15_HISTORY",
                )

                anchor_bar_epoch = (
                    current_bar_epoch
                )

                continue

            decision = (
                signal_engine.evaluate(
                    symbol=symbol,
                    rates=rates,
                    current_bar_epoch=(
                        current_bar_epoch
                    ),
                )
            )

            if not decision.valid:
                session_stats[
                    "decision_blocks"
                ] += 1

                print(
                    "DECISION_BLOCK",
                    decision.reason,
                )

                anchor_bar_epoch = (
                    current_bar_epoch
                )

                continue

            sequence_confirmed = (
                decision.signal_bar_epoch
                == anchor_bar_epoch
            )

            frozen_signal = (
                decision.frozen_signal
            )

            if (
                frozen_signal is None
                or not frozen_signal.valid
            ):
                session_stats[
                    "wait_decisions"
                ] += 1

                print(
                    "MSS_DECISION",
                    "WAIT",
                    decision.reason,
                )

                anchor_bar_epoch = (
                    current_bar_epoch
                )

                continue

            current_rate = find_rate(
                rates,
                current_bar_epoch,
            )

            if current_rate is None:
                session_stats[
                    "entry_windows_missed"
                ] += 1

                print(
                    "ENTRY_WINDOW_MISSED",
                    "CURRENT_RATE_NOT_FOUND",
                )

                anchor_bar_epoch = (
                    current_bar_epoch
                )

                continue

            current_open = float(
                rate_value(
                    current_rate,
                    "open",
                )
            )

            spread_points = (
                observed_spread_points(
                    current_rate=(
                        current_rate
                    ),
                    symbol_info=(
                        symbol_info
                    ),
                    tick=(
                        transition_tick
                    ),
                )
            )

            watch_result = (
                CausalNextCandleEntryWatcher
                .evaluate(
                    signal=frozen_signal,
                    previous_current_bar_epoch=(
                        anchor_bar_epoch
                    ),
                    current_bar_epoch=(
                        current_bar_epoch
                    ),
                    observation_broker_epoch=int(
                        transition_tick.time
                    ),
                    next_candle_sequence_confirmed=(
                        sequence_confirmed
                    ),
                    next_candle_open=(
                        current_open
                    ),
                    spread_points=(
                        spread_points
                    ),
                    point=point,
                )
            )

            if (
                not watch_result.valid
                or not watch_result
                .shadow_entry_allowed
            ):
                session_stats[
                    "entry_windows_missed"
                ] += 1

                print(
                    "ENTRY_BLOCK",
                    watch_result.action,
                    watch_result.reason,
                )

                anchor_bar_epoch = (
                    current_bar_epoch
                )

                continue

            entry = (
                watch_result.entry
            )

            account = (
                mt5.account_info()
            )

            if account is None:
                raise RuntimeError(
                    "MT5_ACCOUNT_INFO_UNAVAILABLE"
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
                f"{safe_symbol}-"
                f"{current_bar_epoch}"
            )

            open_result = (
                ShadowTradeEngine
                .open_trade(
                    journal_path=(
                        journal_path
                    ),
                    position_id=(
                        position_id
                    ),
                    symbol=symbol,
                    direction=(
                        entry.direction
                    ),
                    balance=balance,
                    risk_percent=(
                        entry.risk_percent
                    ),
                    entry_price=(
                        entry.entry_price
                    ),
                    stop_loss=(
                        entry.stop_loss
                    ),
                    take_profit=(
                        entry.take_profit
                    ),
                    broker_epoch=(
                        current_bar_epoch
                    ),
                )
            )

            if not open_result.valid:
                print(
                    "SHADOW_OPEN_BLOCKED",
                    open_result.reason,
                )

                anchor_bar_epoch = (
                    current_bar_epoch
                )

                continue

            position = (
                open_result.position
            )

            session_stats[
                "positions_opened"
            ] += 1

            print(
                "SHADOW_POSITION_OPENED",
                position.position_id,
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

            anchor_bar_epoch = (
                current_bar_epoch
            )

            time.sleep(
                POLL_SECONDS
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
        session_end_utc_epoch = int(
            time.time()
        )

        report = {
            "sprint": "92H.14.3.3c",

            "mode": (
                "CONTINUOUS_SHADOW_LIVE_SESSION"
            ),

            "symbol": symbol,
            "timeframe": "M15",

            "session": {
                "start_utc_epoch": (
                    session_start_utc_epoch
                ),
                "end_utc_epoch": (
                    session_end_utc_epoch
                ),
                "final_status": (
                    final_status
                ),
                "poll_seconds": (
                    POLL_SECONDS
                ),
            },

            "stats": (
                session_stats
            ),

            "safety": {
                "real_order_send_allowed": False,
                "order_send_called": (
                    execution_guard_state[
                        "order_send_called"
                    ]
                ),
                "order_check_called": (
                    execution_guard_state[
                        "order_check_called"
                    ]
                ),
                "order_send_attempt_count": (
                    execution_guard_state[
                        "order_send_attempt_count"
                    ]
                ),
                "order_check_attempt_count": (
                    execution_guard_state[
                        "order_check_attempt_count"
                    ]
                ),
                "order_send_guard_installed": True,
                "order_check_guard_installed": (
                    original_order_check
                    is not None
                ),
                "retrospective_entry_allowed": False,
                "synthetic_exit_allowed": False,
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

            "time_authority": {
                "runtime_broker_offset_detection": True,
                "hardcoded_broker_offset": False,
                "hardcoded_system_timezone": False,
                "hardcoded_broker_identity": False,
                "last_confirmed_broker_offset_seconds": (
                    previous_broker_offset_seconds
                ),
            },

            "recovery": {
                "journal_path": str(
                    journal_path
                ),
                "open_position_present_at_exit": (
                    position is not None
                ),
            },

            "research_segregation": {
                "true_oos_data_accessed": False,
                "true_oos_artifacts_modified": False,
                "performance_evidence": False,
                "strategy_retuning_performed": False,
            },
        }

        print(
            "FINAL_STATUS",
            final_status,
        )

        print(
            "ORDER_SEND_ATTEMPT_COUNT",
            execution_guard_state[
                "order_send_attempt_count"
            ],
        )

        print(
            "ORDER_CHECK_ATTEMPT_COUNT",
            execution_guard_state[
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
                str(report_path),
            )

        except Exception as exc:
            print(
                "SESSION_REPORT_WRITE_FAILED",
                repr(exc),
            )

        if initialized:
            mt5.shutdown()

        if original_order_send is not None:
            mt5.order_send = (
                original_order_send
            )

        if original_order_check is not None:
            mt5.order_check = (
                original_order_check
            )


if __name__ == "__main__":
    main()
