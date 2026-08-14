"""Parallel causal multi-symbol Shadow Live session.

Sprint 92H.14.5a

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
MAX_ANALYSIS_WORKERS = 8


def journal_path_for(
    symbol: str,
) -> Path:
    return (
        ROOT
        / "shadow_data"
        / "live"
        / "sprint92h14_5a"
        / safe_symbol_name(symbol)
        / "shadow_positions.jsonl"
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
            "MSS_Sprint92H14_5a_"
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
    }

    initialized = False
    final_status = (
        "SESSION_NOT_STARTED"
    )

    position = None
    position_symbol = None

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
                        f"{recovery.reason}"
                    )

                if (
                    recovery.open_position_count
                    == 1
                ):
                    rp = (
                        recovery.position
                    )

                    if (
                        rp.symbol
                        != symbol
                    ):
                        raise RuntimeError(
                            "RECOVERED_POSITION_"
                            "SYMBOL_MISMATCH"
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

        final_status = (
            "LIVE_POLICY_MULTI_SYMBOL_"
            "SHADOW_SESSION_RUNNING"
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
                            open_positions=(),
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
                                        open_positions=(),
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

        report = {
            "sprint": "92H.14.5a",
            "mode": (
                "LIVE_POLICY_MULTI_SYMBOL_"
                "POLICY_SINGLE_POSITION_SHADOW_SESSION"
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
