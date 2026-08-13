"""Sprint 92H.14.3.2 live completed-candle MSS decision observation."""

from __future__ import annotations

import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.live_completed_candle_signal_engine import (
    LiveCompletedCandleSignalEngine,
)
from mss.analysis.live_market_observer import (
    LiveMarketObserver,
)


ROOT = Path(__file__).resolve().parents[1]

SYMBOL = "USDJPY"
TIMEFRAME = mt5.TIMEFRAME_M15

REPORT_PATH = (
    ROOT
    / "reports"
    / "MSS_Sprint92H14_3_2_Live_Completed_Candle_Decision_000001.json"
)


def prohibited_execution_call(*args, **kwargs):
    raise RuntimeError(
        "SHADOW_LIVE_EXECUTION_GUARD_TRIGGERED"
    )


def rate_value(rate, name):
    try:
        return rate[name]
    except (TypeError, KeyError, IndexError):
        return getattr(rate, name)


def main():
    if REPORT_PATH.exists():
        raise RuntimeError(
            "H14_3_2_REPORT_ALREADY_EXISTS"
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

    initialized = False

    try:
        mt5.order_send = prohibited_execution_call

        if hasattr(mt5, "order_check"):
            mt5.order_check = (
                prohibited_execution_call
            )

        observation = (
            LiveMarketObserver.observe(
                symbol=SYMBOL,
            )
        )

        safety = observation["safety"]

        if not safety[
            "shadow_observation_allowed"
        ]:
            raise RuntimeError(
                "LIVE_OBSERVATION_NOT_SAFE"
            )

        authority_status = (
            observation[
                "time_authority"
            ][
                "time_authority"
            ][
                "status"
            ]
        )

        sync_status = (
            observation[
                "time_synchronization"
            ][
                "status"
            ]
        )

        if (
            authority_status
            != "BROKER_TIME_DOMAIN_CONFIRMED"
        ):
            raise RuntimeError(
                "TIME_AUTHORITY_NOT_CONFIRMED"
            )

        if (
            sync_status
            != "MT5_BAR_SYNCHRONIZED"
        ):
            raise RuntimeError(
                "BAR_NOT_SYNCHRONIZED"
            )

        if not mt5.initialize():
            raise RuntimeError(
                "MT5_INITIALIZE_FAILED: "
                f"{mt5.last_error()}"
            )

        initialized = True

        info = mt5.symbol_info(
            SYMBOL
        )

        if info is None:
            raise RuntimeError(
                "SYMBOL_INFO_UNAVAILABLE"
            )

        if not mt5.symbol_select(
            SYMBOL,
            True,
        ):
            raise RuntimeError(
                "SYMBOL_SELECT_FAILED"
            )

        rates = mt5.copy_rates_from_pos(
            SYMBOL,
            TIMEFRAME,
            0,
            520,
        )

        if rates is None:
            raise RuntimeError(
                "MT5_RATES_UNAVAILABLE"
            )

        if len(rates) < 501:
            raise RuntimeError(
                "INSUFFICIENT_RAW_M15_RATES"
            )

        current_bar_epoch = max(
            int(
                rate_value(
                    rate,
                    "time",
                )
            )
            for rate in rates
        )

        engine = (
            LiveCompletedCandleSignalEngine()
        )

        decision = engine.evaluate(
            symbol=SYMBOL,
            rates=rates,
            current_bar_epoch=(
                current_bar_epoch
            ),
        )

        if not decision.valid:
            raise RuntimeError(
                "LIVE_MSS_DECISION_BLOCKED: "
                f"{decision.reason}"
            )

        pipeline = (
            decision.pipeline_result
        )

        frozen = (
            decision.frozen_signal
        )

        report = {
            "sprint": "92H.14.3.2",
            "mode": (
                "LIVE_COMPLETED_CANDLE_MSS_DECISION"
            ),

            "symbol": SYMBOL,
            "timeframe": "M15",

            "causal_input": {
                "raw_rate_count": len(rates),
                "completed_candle_count": (
                    decision.completed_candle_count
                ),
                "forming_candle_excluded": (
                    decision.forming_candle_excluded
                ),
                "completed_candles_only": (
                    decision.completed_candles_only
                ),
                "current_bar_epoch": (
                    decision.current_bar_epoch
                ),
                "signal_bar_epoch": (
                    decision.signal_bar_epoch
                ),
            },

            "pipeline": {
                "valid": pipeline.valid,
                "bos_detected": (
                    pipeline.bos_detected
                ),
                "bos_direction": (
                    pipeline.bos_direction
                ),
                "last_low": (
                    pipeline.last_low
                ),
                "last_high": (
                    pipeline.last_high
                ),
                "structure_state": (
                    pipeline.structure_state
                ),
                "recommendation": (
                    pipeline.recommendation
                ),
                "score": (
                    pipeline.score
                ),
                "confidence": (
                    pipeline.confidence
                ),
                "confluence_valid": (
                    pipeline.confluence_valid
                ),
                "confluence_signal": (
                    pipeline.confluence_signal
                ),
                "confluence_reason": (
                    pipeline.confluence_reason
                ),
            },

            "frozen_strategy_decision": {
                "action": (
                    decision.action
                ),
                "reason": (
                    decision.reason
                ),
                "entry_window_status": (
                    decision.entry_window_status
                ),
                "signal_valid": (
                    bool(
                        frozen
                        and frozen.valid
                    )
                ),
                "direction": (
                    frozen.direction
                    if frozen
                    else ""
                ),
                "stop_loss": (
                    frozen.stop_loss
                    if frozen
                    else 0.0
                ),
                "expected_entry_bar_epoch": (
                    frozen
                    .expected_entry_bar_epoch
                    if frozen
                    else 0
                ),
                "risk_percent": (
                    frozen.risk_percent
                    if frozen
                    else 1.0
                ),
                "reward_risk_ratio": (
                    frozen.reward_risk_ratio
                    if frozen
                    else 2.0
                ),
                "entry_rule": (
                    frozen.entry_rule
                    if frozen
                    else "NEXT_CANDLE_OPEN"
                ),
                "confluence_used_as_gate": (
                    frozen
                    .confluence_used_as_gate
                    if frozen
                    else False
                ),
                "direction_filtering": (
                    frozen.direction_filtering
                    if frozen
                    else False
                ),
                "retuning": (
                    frozen.retuning
                    if frozen
                    else False
                ),
            },

            "execution_safety": {
                "shadow_trade_opened": False,
                "real_order_send_allowed": False,
                "order_send_called": False,
                "order_check_called": False,
                "order_send_guard_installed": True,
                "order_check_guard_installed": (
                    original_order_check
                    is not None
                ),
            },

            "research_segregation": {
                "true_oos_data_accessed": False,
                "true_oos_artifacts_modified": False,
                "strategy_contract_changed": False,
                "performance_evidence": False,
            },

            "time_authority": {
                "status": authority_status,
                "bar_sync_status": sync_status,
            },
        }

        REPORT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        REPORT_PATH.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            "STATUS",
            "LIVE_MSS_DECISION_PASS",
        )

        print(
            "SYMBOL",
            SYMBOL,
        )

        print(
            "TIMEFRAME",
            "M15",
        )

        print(
            "COMPLETED_CANDLES",
            decision.completed_candle_count,
        )

        print(
            "FORMING_CANDLE_EXCLUDED",
            decision.forming_candle_excluded,
        )

        print(
            "SIGNAL_BAR_EPOCH",
            decision.signal_bar_epoch,
        )

        print(
            "CURRENT_BAR_EPOCH",
            decision.current_bar_epoch,
        )

        print(
            "PIPELINE_VALID",
            pipeline.valid,
        )

        print(
            "BOS_DETECTED",
            pipeline.bos_detected,
        )

        print(
            "BOS_DIRECTION",
            pipeline.bos_direction,
        )

        print(
            "STRUCTURE",
            pipeline.structure_state,
        )

        print(
            "RECOMMENDATION",
            pipeline.recommendation,
        )

        print(
            "DECISION_ACTION",
            decision.action,
        )

        print(
            "DECISION_REASON",
            decision.reason,
        )

        print(
            "ENTRY_WINDOW_STATUS",
            decision.entry_window_status,
        )

        print(
            "SHADOW_TRADE_OPENED",
            False,
        )

        print(
            "REAL_ORDER_SEND_ALLOWED",
            False,
        )

        print(
            "ORDER_SEND_CALLED",
            False,
        )

        print(
            "ORDER_CHECK_CALLED",
            False,
        )

        print(
            "TRUE_OOS_ACCESSED",
            False,
        )

        print(
            "PERFORMANCE_EVIDENCE",
            False,
        )

        print(
            "REPORT",
            str(REPORT_PATH),
        )

    finally:
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
