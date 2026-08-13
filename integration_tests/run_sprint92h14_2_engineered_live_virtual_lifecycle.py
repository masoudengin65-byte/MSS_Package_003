"""Sprint 92H.14.2 engineered live virtual trade lifecycle validation."""

from __future__ import annotations

import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.live_market_observer import (
    LiveMarketObserver,
)
from mss.analysis.shadow_trade_engine import (
    ShadowTradeEngine,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


ROOT = Path(__file__).resolve().parents[1]

SYMBOL = "USDJPY"
RISK_PERCENT = 1.0

JOURNAL_PATH = (
    ROOT
    / "shadow_data"
    / "validation"
    / "sprint92h14_2"
    / SYMBOL
    / "engineered_lifecycle_000001.jsonl"
)

REPORT_PATH = (
    ROOT
    / "reports"
    / "MSS_Sprint92H14_2_Engineered_Live_Lifecycle_000001.json"
)


def prohibited_execution_call(*args, **kwargs):
    raise RuntimeError(
        "SHADOW_LIVE_EXECUTION_GUARD_TRIGGERED"
    )


def main() -> None:
    if JOURNAL_PATH.exists():
        raise RuntimeError(
            "H14_2_VALIDATION_JOURNAL_ALREADY_EXISTS"
        )

    if REPORT_PATH.exists():
        raise RuntimeError(
            "H14_2_VALIDATION_REPORT_ALREADY_EXISTS"
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

    mt5_initialized = False

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
                "MT5_REINITIALIZE_FAILED: "
                f"{mt5.last_error()}"
            )

        mt5_initialized = True

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

        info = mt5.symbol_info(
            SYMBOL
        )

        if info is None:
            raise RuntimeError(
                "SYMBOL_INFO_UNAVAILABLE"
            )

        point = float(
            getattr(
                info,
                "point",
                0.0,
            )
            or 0.0
        )

        stops_level = int(
            getattr(
                info,
                "trade_stops_level",
                0,
            )
            or 0
        )

        if point <= 0:
            raise RuntimeError(
                "INVALID_SYMBOL_POINT"
            )

        bid = float(
            observation[
                "tick"
            ]["bid"]
        )

        ask = float(
            observation[
                "tick"
            ]["ask"]
        )

        broker_epoch = int(
            observation[
                "tick"
            ]["time"]
        )

        #
        # Engineered validation geometry.
        #
        # Uses a real live Ask as entry.
        # Distance adapts to broker stop constraints.
        # This is NOT a strategy signal.
        #

        minimum_distance_points = max(
            stops_level + 10,
            100,
        )

        stop_distance = (
            minimum_distance_points
            * point
        )

        entry_price = ask

        stop_loss = (
            entry_price
            - stop_distance
        )

        take_profit = (
            entry_price
            + (2.0 * stop_distance)
        )

        opened = (
            ShadowTradeEngine.open_trade(
                journal_path=JOURNAL_PATH,
                position_id=(
                    "H14_2_ENGINEERED_000001"
                ),
                symbol=SYMBOL,
                direction="BUY",
                balance=balance,
                risk_percent=RISK_PERCENT,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                broker_epoch=broker_epoch,
            )
        )

        if not opened.valid:
            raise RuntimeError(
                "SHADOW_OPEN_BLOCKED: "
                f"{opened.reason}"
            )

        if (
            opened.action
            != "POSITION_OPENED"
        ):
            raise RuntimeError(
                "SHADOW_POSITION_NOT_OPENED"
            )

        #
        # ENGINEERED EXIT:
        #
        # We intentionally feed a synthetic validation
        # Bid at TP so the complete virtual lifecycle can
        # be proven in one run.
        #
        # This must never be interpreted as live strategy
        # performance evidence.
        #

        engineered_exit_bid = (
            take_profit
        )

        engineered_exit_ask = (
            take_profit
            + max(
                ask - bid,
                point,
            )
        )

        closed = (
            ShadowTradeEngine.update_trade(
                journal_path=JOURNAL_PATH,
                position=opened.position,
                bid=engineered_exit_bid,
                ask=engineered_exit_ask,
                broker_epoch=(
                    broker_epoch + 1
                ),
            )
        )

        if not closed.valid:
            raise RuntimeError(
                "SHADOW_CLOSE_BLOCKED: "
                f"{closed.reason}"
            )

        if (
            closed.action
            != "POSITION_CLOSED"
        ):
            raise RuntimeError(
                "SHADOW_POSITION_NOT_CLOSED"
            )

        verification = (
            ShadowTradeJournal.verify(
                JOURNAL_PATH
            )
        )

        if not verification["valid"]:
            raise RuntimeError(
                "SHADOW_JOURNAL_VERIFY_FAILED"
            )

        if verification["event_count"] != 2:
            raise RuntimeError(
                "UNEXPECTED_SHADOW_EVENT_COUNT"
            )

        report = {
            "sprint": "92H.14.2",
            "validation_mode": (
                "ENGINEERED_LIVE_VIRTUAL_LIFECYCLE"
            ),
            "performance_evidence": False,
            "strategy_signal_used": False,
            "true_oos_evidence": False,

            "live_market_input": {
                "symbol": SYMBOL,
                "bid": bid,
                "ask": ask,
                "spread_price": (
                    ask - bid
                ),
                "point": point,
                "trade_stops_level": (
                    stops_level
                ),
                "broker_epoch": (
                    broker_epoch
                ),
                "time_authority_status": (
                    authority_status
                ),
                "bar_sync_status": (
                    sync_status
                ),
            },

            "risk_input": {
                "risk_percent": (
                    RISK_PERCENT
                ),
                "account_balance_used": True,
                "balance_value_redacted": True,
            },

            "engineered_setup": {
                "direction": "BUY",
                "entry_price": (
                    entry_price
                ),
                "stop_loss": (
                    stop_loss
                ),
                "take_profit": (
                    take_profit
                ),
                "stop_distance_points": (
                    minimum_distance_points
                ),
                "setup_source": (
                    "ENGINEERED_VALIDATION_NOT_STRATEGY"
                ),
            },

            "opened": {
                "action": opened.action,
                "reason": opened.reason,
                "volume": (
                    opened.position.volume
                ),
                "risk_amount": (
                    opened.risk.risk_amount
                ),
                "loss_per_one_lot": (
                    opened.risk.loss_per_one_lot
                ),
            },

            "closed": {
                "action": closed.action,
                "reason": closed.reason,
                "exit_reason": (
                    closed.position.exit_reason
                ),
                "close_price": (
                    closed.position.close_price
                ),
                "pnl_account_currency": (
                    closed.position
                    .pnl_account_currency
                ),
                "r_multiple": (
                    closed.position.r_multiple
                ),
                "exit_price_source": (
                    "ENGINEERED_VALIDATION_PRICE"
                ),
            },

            "journal": verification,

            "execution_safety": {
                "real_order_send_allowed": False,
                "order_send_guard_installed": True,
                "order_check_guard_installed": (
                    original_order_check
                    is not None
                ),
                "order_send_called": False,
                "order_check_called": False,
                "real_position_modified": False,
                "real_order_modified": False,
            },

            "research_segregation": {
                "true_oos_data_accessed": False,
                "true_oos_artifacts_modified": False,
                "shadow_namespace": True,
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
            "ENGINEERED_SHADOW_LIFECYCLE_PASS",
        )
        print(
            "SYMBOL",
            SYMBOL,
        )
        print(
            "TIME_AUTHORITY",
            authority_status,
        )
        print(
            "BAR_SYNC",
            sync_status,
        )
        print(
            "LIVE_BID",
            bid,
        )
        print(
            "LIVE_ASK",
            ask,
        )
        print(
            "VIRTUAL_DIRECTION",
            "BUY",
        )
        print(
            "VIRTUAL_ENTRY",
            entry_price,
        )
        print(
            "VIRTUAL_STOP",
            stop_loss,
        )
        print(
            "VIRTUAL_TP",
            take_profit,
        )
        print(
            "VIRTUAL_VOLUME",
            opened.position.volume,
        )
        print(
            "OPEN_ACTION",
            opened.action,
        )
        print(
            "CLOSE_ACTION",
            closed.action,
        )
        print(
            "EXIT_REASON",
            closed.position.exit_reason,
        )
        print(
            "R_MULTIPLE",
            closed.position.r_multiple,
        )
        print(
            "P_AND_L_VALUED",
            True,
        )
        print(
            "JOURNAL_EVENTS",
            verification["event_count"],
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
        print(
            "JOURNAL",
            str(JOURNAL_PATH),
        )

    finally:
        if mt5_initialized:
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
