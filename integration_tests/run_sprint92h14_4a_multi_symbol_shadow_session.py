"""Multi-symbol causal Shadow Live session.

Sprint 92H.14.4a

Purpose:
- observe multiple broker symbols concurrently
- preserve frozen completed-candle MSS contract
- actual MT5 next-trading-bar sequence
- causal entry freshness <= existing frozen limit
- broker-aware virtual sizing/execution
- maximum ONE open Shadow position globally
- no real MT5 order_send / order_check
- no True-OOS access
"""

from __future__ import annotations

import argparse
import time
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
from mss.analysis.shadow_position_recovery import (
    ShadowPositionRecovery,
)
from mss.analysis.shadow_trade_engine import (
    ShadowTradeEngine,
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


def journal_path_for(symbol: str) -> Path:
    return (
        ROOT
        / "shadow_data"
        / "live"
        / "sprint92h14_4a"
        / safe_symbol_name(symbol)
        / "shadow_positions.jsonl"
    )


def new_symbol_stats() -> dict:
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
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated exact MT5 broker symbol names.",
    )

    parser.add_argument(
        "--max-seconds",
        type=float,
        default=0.0,
        help="0 means continuous until Ctrl+C.",
    )

    args = parser.parse_args()

    symbols = tuple(
        value.strip()
        for value in str(args.symbols).split(",")
        if value.strip()
    )

    if not symbols:
        raise RuntimeError("SYMBOLS_REQUIRED")

    if len(set(symbols)) != len(symbols):
        raise RuntimeError("DUPLICATE_SYMBOLS_NOT_ALLOWED")

    session_start_utc_epoch = int(time.time())

    report_path = (
        ROOT
        / "reports"
        / (
            "MSS_Sprint92H14_4a_"
            "Multi_Symbol_Shadow_Session_"
            f"{session_start_utc_epoch}.json"
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

    execution_guard_state = {
        "order_send_called": False,
        "order_check_called": False,
        "order_send_attempt_count": 0,
        "order_check_attempt_count": 0,
    }

    initialized = False

    symbol_states = {}

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
    }

    position = None
    position_symbol = None

    final_status = "SESSION_NOT_STARTED"

    try:
        mt5.order_send = make_execution_guard(
            api_name="order_send",
            state=execution_guard_state,
        )

        if original_order_check is not None:
            mt5.order_check = make_execution_guard(
                api_name="order_check",
                state=execution_guard_state,
            )

        # -----------------------------------------------------
        # Per-symbol initial safety/time observation.
        # A closed/unavailable market disables only that symbol;
        # it does NOT weaken safety for other symbols.
        # -----------------------------------------------------

        for symbol in symbols:
            state = {
                "enabled": False,
                "disabled_reason": "",
                "anchor_bar_epoch": 0,
                "previous_broker_offset_seconds": None,
                "point": 0.0,
                "symbol_info": None,
                "journal_path": journal_path_for(symbol),
                "stats": new_symbol_stats(),
            }

            symbol_states[symbol] = state

            try:
                observation = LiveMarketObserver.observe(
                    symbol=symbol,
                )

                if not observation[
                    "safety"
                ][
                    "shadow_observation_allowed"
                ]:
                    raise RuntimeError(
                        "INITIAL_SHADOW_OBSERVATION_NOT_SAFE"
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
                    != "BROKER_TIME_DOMAIN_CONFIRMED"
                ):
                    raise RuntimeError(
                        "INITIAL_TIME_AUTHORITY_NOT_CONFIRMED"
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
                state["disabled_reason"] = (
                    f"INITIAL_OBSERVATION_FAILED:{exc}"
                )

                global_stats[
                    "symbols_disabled"
                ] += 1

                print(
                    "SYMBOL_DISABLED",
                    symbol,
                    state["disabled_reason"],
                )

        if not mt5.initialize():
            raise RuntimeError(
                "MT5_INITIALIZE_FAILED: "
                f"{mt5.last_error()}"
            )

        initialized = True

        # -----------------------------------------------------
        # Broker metadata/history/recovery for enabled symbols.
        # -----------------------------------------------------

        recovered_positions = []

        for symbol in symbols:
            state = symbol_states[symbol]

            if state["disabled_reason"]:
                continue

            try:
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

                state["symbol_info"] = symbol_info
                state["point"] = point

                state[
                    "journal_path"
                ].parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                recovery = (
                    ShadowPositionRecovery.recover(
                        state["journal_path"]
                    )
                )

                if not recovery.valid:
                    raise RuntimeError(
                        "SHADOW_POSITION_RECOVERY_FAILED:"
                        f"{recovery.reason}"
                    )

                if (
                    recovery.open_position_count
                    == 1
                ):
                    recovered = recovery.position

                    if recovered.symbol != symbol:
                        raise RuntimeError(
                            "RECOVERED_POSITION_SYMBOL_MISMATCH"
                        )

                    recovered_positions.append(
                        (
                            symbol,
                            recovered,
                        )
                    )

                    state["stats"][
                        "positions_recovered"
                    ] += 1

                rates = load_rates(
                    symbol
                )

                if (
                    len(rates)
                    < MIN_REQUIRED_RATES
                ):
                    raise RuntimeError(
                        "INSUFFICIENT_INITIAL_M15_HISTORY"
                    )

                anchor = latest_bar_epoch(
                    rates
                )

                if anchor <= 0:
                    raise RuntimeError(
                        "INVALID_INITIAL_BAR_EPOCH"
                    )

                state[
                    "anchor_bar_epoch"
                ] = anchor

                state["enabled"] = True

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
                state["enabled"] = False
                state["disabled_reason"] = (
                    f"INITIALIZATION_FAILED:{exc}"
                )

                global_stats[
                    "symbols_disabled"
                ] += 1

                print(
                    "SYMBOL_DISABLED",
                    symbol,
                    state["disabled_reason"],
                )

        if (
            global_stats["symbols_enabled"]
            <= 0
        ):
            raise RuntimeError(
                "NO_SAFE_SYMBOLS_AVAILABLE"
            )

        if (
            len(recovered_positions)
            > MAX_OPEN_SHADOW_POSITIONS
        ):
            raise RuntimeError(
                "GLOBAL_SHADOW_POSITION_LIMIT_"
                "VIOLATED_ON_RECOVERY"
            )

        if recovered_positions:
            (
                position_symbol,
                position,
            ) = recovered_positions[0]

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

        signal_engine = (
            LiveCompletedCandleSignalEngine()
        )

        start_monotonic = time.monotonic()

        final_status = (
            "MULTI_SYMBOL_SHADOW_SESSION_RUNNING"
        )

        print(
            "STATUS",
            final_status,
        )

        print(
            "SYMBOLS",
            ",".join(symbols),
        )

        print(
            "SYMBOLS_ENABLED",
            global_stats["symbols_enabled"],
        )

        print(
            "MAX_OPEN_SHADOW_POSITIONS",
            MAX_OPEN_SHADOW_POSITIONS,
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
            original_order_check is not None,
        )

        print(
            "TRUE_OOS_ACCESS",
            False,
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
            # Natural tick-driven monitoring of the ONE
            # globally open Shadow position.
            # -------------------------------------------------

            if (
                position is not None
                and position_symbol is not None
            ):
                tick = mt5.symbol_info_tick(
                    position_symbol
                )

                if validate_tick(tick):
                    state = symbol_states[
                        position_symbol
                    ]

                    update_result = (
                        ShadowTradeEngine.update_trade(
                            journal_path=(
                                state["journal_path"]
                            ),
                            position=position,
                            bid=float(tick.bid),
                            ask=float(tick.ask),
                            broker_epoch=int(
                                tick.time
                            ),
                        )
                    )

                    if not update_result.valid:
                        raise RuntimeError(
                            "SHADOW_POSITION_UPDATE_FAILED:"
                            f"{update_result.reason}"
                        )

                    position = (
                        update_result.position
                    )

                    if (
                        update_result.action
                        == "POSITION_CLOSED"
                    ):
                        state["stats"][
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

            # -------------------------------------------------
            # Scan every enabled symbol independently.
            # -------------------------------------------------

            for symbol in symbols:
                state = symbol_states[
                    symbol
                ]

                if not state["enabled"]:
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
                    or len(short_rates) == 0
                ):
                    continue

                current_bar_epoch = (
                    latest_bar_epoch(
                        short_rates
                    )
                )

                anchor_bar_epoch = int(
                    state[
                        "anchor_bar_epoch"
                    ]
                )

                if current_bar_epoch <= 0:
                    continue

                if (
                    current_bar_epoch
                    < anchor_bar_epoch
                ):
                    raise RuntimeError(
                        "LIVE_BAR_TIME_REGRESSION:"
                        f"{symbol}"
                    )

                if (
                    current_bar_epoch
                    == anchor_bar_epoch
                ):
                    continue

                state["stats"][
                    "bar_transitions_observed"
                ] += 1

                global_stats[
                    "bar_transitions_observed"
                ] += 1

                print(
                    "BAR_TRANSITION",
                    symbol,
                    anchor_bar_epoch,
                    "->",
                    current_bar_epoch,
                )

                try:
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
                                state[
                                    "previous_broker_offset_seconds"
                                ]
                            ),
                        )
                    )

                    authority_confirmed = bool(
                        transition_authority[
                            "time_authority"
                        ][
                            "confirmed"
                        ]
                    )

                    authority_status = (
                        transition_authority[
                            "time_authority"
                        ][
                            "status"
                        ]
                    )

                    if not authority_confirmed:
                        state["stats"][
                            "time_authority_blocks"
                        ] += 1

                        global_stats[
                            "time_authority_blocks"
                        ] += 1

                        print(
                            "TIME_AUTHORITY_BLOCK",
                            symbol,
                            authority_status,
                        )

                        state[
                            "anchor_bar_epoch"
                        ] = current_bar_epoch

                        continue

                    state[
                        "previous_broker_offset_seconds"
                    ] = int(
                        transition_authority[
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
                        state["stats"][
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
                        ] = current_bar_epoch

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
                        state["stats"][
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

                        state[
                            "anchor_bar_epoch"
                        ] = current_bar_epoch

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
                        state["stats"][
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

                        state[
                            "anchor_bar_epoch"
                        ] = current_bar_epoch

                        continue

                    current_rate = find_rate(
                        rates,
                        current_bar_epoch,
                    )

                    if current_rate is None:
                        state["stats"][
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

                        state[
                            "anchor_bar_epoch"
                        ] = current_bar_epoch

                        continue

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
                                state["point"]
                            ),
                        )
                    )

                    if (
                        not watch_result.valid
                        or not watch_result
                        .shadow_entry_allowed
                    ):
                        state["stats"][
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

                        state[
                            "anchor_bar_epoch"
                        ] = current_bar_epoch

                        continue

                    # -----------------------------------------
                    # H14.4a GLOBAL SINGLE POSITION LOCK.
                    # Signal is valid, but no second position
                    # may be opened before H14.5 governor.
                    # -----------------------------------------

                    if position is not None:
                        state["stats"][
                            "portfolio_lock_blocks"
                        ] += 1

                        global_stats[
                            "portfolio_lock_blocks"
                        ] += 1

                        print(
                            "PORTFOLIO_LOCK_BLOCK",
                            symbol,
                            "OPEN_POSITION_SYMBOL",
                            position_symbol,
                        )

                        state[
                            "anchor_bar_epoch"
                        ] = current_bar_epoch

                        continue

                    entry = (
                        watch_result.entry
                    )

                    account = mt5.account_info()

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
                        f"{safe_symbol_name(symbol)}-"
                        f"{current_bar_epoch}"
                    )

                    open_result = (
                        ShadowTradeEngine.open_trade(
                            journal_path=(
                                state["journal_path"]
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
                            symbol,
                            open_result.reason,
                        )

                        state[
                            "anchor_bar_epoch"
                        ] = current_bar_epoch

                        continue

                    position = (
                        open_result.position
                    )

                    position_symbol = symbol

                    state["stats"][
                        "positions_opened"
                    ] += 1

                    global_stats[
                        "positions_opened"
                    ] += 1

                    print(
                        "SHADOW_POSITION_OPENED",
                        symbol,
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

                    state[
                        "anchor_bar_epoch"
                    ] = current_bar_epoch

                except Exception as exc:
                    # A single-symbol runtime defect must not
                    # silently weaken the rest of the session.
                    # Disable that symbol fail-safe.
                    state["enabled"] = False
                    state["disabled_reason"] = (
                        f"RUNTIME_SYMBOL_FAILURE:{exc}"
                    )

                    print(
                        "SYMBOL_DISABLED",
                        symbol,
                        state["disabled_reason"],
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
            "sprint": "92H.14.4a",
            "mode": (
                "MULTI_SYMBOL_SINGLE_POSITION_"
                "SHADOW_LIVE_SESSION"
            ),
            "symbols": list(symbols),
            "max_open_shadow_positions": (
                MAX_OPEN_SHADOW_POSITIONS
            ),
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
            "stats": global_stats,
            "per_symbol": {
                symbol: {
                    "enabled": (
                        symbol_states[
                            symbol
                        ][
                            "enabled"
                        ]
                    ),
                    "disabled_reason": (
                        symbol_states[
                            symbol
                        ][
                            "disabled_reason"
                        ]
                    ),
                    "anchor_bar_epoch": (
                        symbol_states[
                            symbol
                        ][
                            "anchor_bar_epoch"
                        ]
                    ),
                    "journal_path": str(
                        symbol_states[
                            symbol
                        ][
                            "journal_path"
                        ]
                    ),
                    "stats": (
                        symbol_states[
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
                "global_single_position_lock": True,
            },
            "strategy_contract": {
                "entry_rule": "NEXT_CANDLE_OPEN",
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
                report_path=report_path,
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
