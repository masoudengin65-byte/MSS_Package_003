from types import SimpleNamespace

import MetaTrader5 as mt5

from mss.analysis.shadow_risk_calculator import (
    ShadowRiskCalculator,
)
from mss.analysis.demo_broker_execution_adapter import (
    DemoBrokerExecutionAdapter,
)


SYMBOL = "EURUSD"
DIRECTION = "BUY"
RISK_PERCENT = 1.0


def main():

    if not mt5.initialize():
        print(
            "DRY_RUN_FAIL",
            "MT5_INITIALIZE_FAILED",
            mt5.last_error(),
        )
        raise SystemExit(1)

    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()

        print(
            "MODE",
            "H14_7_DEMO_TRANSACTION_DRY_RUN",
        )

        print(
            "REAL_ORDER_SEND_ALLOWED",
            False,
        )

        if terminal is None:
            print(
                "DRY_RUN_FAIL",
                "TERMINAL_INFO_UNAVAILABLE",
            )
            raise SystemExit(2)

        if account is None:
            print(
                "DRY_RUN_FAIL",
                "ACCOUNT_INFO_UNAVAILABLE",
            )
            raise SystemExit(3)

        print(
            "TERMINAL_CONNECTED",
            bool(terminal.connected),
        )

        print(
            "ACCOUNT_SERVER",
            account.server,
        )

        print(
            "ACCOUNT_TRADE_MODE",
            account.trade_mode,
        )

        is_demo = (
            DemoBrokerExecutionAdapter
            ._account_is_demo(
                account
            )
        )

        print(
            "ACCOUNT_IS_DEMO",
            is_demo,
        )

        if not is_demo:
            print(
                "DRY_RUN_FAIL",
                "NON_DEMO_ACCOUNT_BLOCKED",
            )
            raise SystemExit(4)

        if not mt5.symbol_select(
            SYMBOL,
            True,
        ):
            print(
                "DRY_RUN_FAIL",
                "SYMBOL_SELECT_FAILED",
            )
            raise SystemExit(5)

        info = mt5.symbol_info(
            SYMBOL
        )

        tick = mt5.symbol_info_tick(
            SYMBOL
        )

        if info is None or tick is None:
            print(
                "DRY_RUN_FAIL",
                "SYMBOL_MARKET_DATA_UNAVAILABLE",
            )
            raise SystemExit(6)

        point = float(
            info.point
        )

        entry = float(
            tick.ask
        )

        stop_loss = (
            entry
            -
            100.0 * point
        )

        take_profit = (
            entry
            +
            200.0 * point
        )

        print(
            "ENTRY_PRICE",
            entry,
        )

        print(
            "STOP_LOSS",
            stop_loss,
        )

        print(
            "TAKE_PROFIT",
            take_profit,
        )

        risk_result = (
            ShadowRiskCalculator
            .calculate(
                symbol=SYMBOL,
                direction=DIRECTION,
                balance=float(
                    account.balance
                ),
                risk_percent=(
                    RISK_PERCENT
                ),
                entry_price=entry,
                stop_loss=stop_loss,
            )
        )

        print(
            "RISK_VALID",
            risk_result.valid,
        )

        print(
            "RISK_REASON",
            risk_result.reason,
        )

        print(
            "NORMALIZED_VOLUME",
            risk_result.normalized_volume,
        )

        if not risk_result.valid:
            print(
                "DRY_RUN_FAIL",
                "RISK_CALCULATION_BLOCKED",
            )
            raise SystemExit(7)

        order_check_count = 0
        order_send_count = 0

        def rejecting_order_check(
            request
        ):
            nonlocal order_check_count

            order_check_count += 1

            print(
                "INJECTED_ORDER_CHECK_CALLED",
                True,
            )

            return SimpleNamespace(
                retcode=10030,
                comment=(
                    "H14_7_INTENTIONAL_"
                    "DRY_RUN_REJECTION"
                ),
            )

        def forbidden_order_send(
            request
        ):
            nonlocal order_send_count

            order_send_count += 1

            raise RuntimeError(
                "ORDER_SEND_MUST_NOT_BE_CALLED_"
                "IN_DRY_RUN"
            )

        result = (
            DemoBrokerExecutionAdapter
            .execute_market_order(
                enabled=True,
                symbol=SYMBOL,
                direction=DIRECTION,
                volume=(
                    risk_result
                    .normalized_volume
                ),
                stop_loss=stop_loss,
                take_profit=take_profit,
                order_check_callable=(
                    rejecting_order_check
                ),
                order_send_callable=(
                    forbidden_order_send
                ),
            )
        )

        print(
            "ADAPTER_VALID",
            result.valid,
        )

        print(
            "ADAPTER_REASON",
            result.reason,
        )

        print(
            "ORDER_CHECK_PERFORMED",
            result.order_check_performed,
        )

        print(
            "ORDER_SEND_PERFORMED",
            result.order_send_performed,
        )

        print(
            "ORDER_CHECK_CALL_COUNT",
            order_check_count,
        )

        print(
            "ORDER_SEND_CALL_COUNT",
            order_send_count,
        )

        print(
            "POSITION_CONFIRMED",
            result.position_confirmed,
        )

        if result.valid:
            print(
                "DRY_RUN_FAIL",
                "ADAPTER_UNEXPECTEDLY_VALID",
            )
            raise SystemExit(8)

        if order_check_count != 1:
            print(
                "DRY_RUN_FAIL",
                "ORDER_CHECK_COUNT_INVALID",
            )
            raise SystemExit(9)

        if order_send_count != 0:
            print(
                "DRY_RUN_FAIL",
                "ORDER_SEND_WAS_CALLED",
            )
            raise SystemExit(10)

        if result.order_send_performed:
            print(
                "DRY_RUN_FAIL",
                "ORDER_SEND_MARKED_PERFORMED",
            )
            raise SystemExit(11)

        print(
            "DRY_RUN_PASS",
            "BROKER_PATH_BLOCKED_BEFORE_SEND",
        )

        print(
            "REAL_ORDER_SENT",
            False,
        )

    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
