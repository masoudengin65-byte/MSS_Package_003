"""Real MT5 demo-forward preflight. Never sends an order."""

from __future__ import annotations

import argparse
import sys

import MetaTrader5 as mt5

from mss.analysis.demo_broker_execution_adapter import (
    DemoBrokerExecutionAdapter,
)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbol",
        default="EURUSD",
    )

    parser.add_argument(
        "--direction",
        choices=("BUY", "SELL"),
        default="BUY",
    )

    args = parser.parse_args()

    symbol = args.symbol
    direction = args.direction

    print("MODE", "DEMO_FORWARD_PREFLIGHT")
    print("REAL_ORDER_SEND_ALLOWED", False)

    if not mt5.initialize():
        print(
            "PREFLIGHT_FAIL",
            "MT5_INITIALIZE_FAILED",
            mt5.last_error(),
        )
        return 10

    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()

        if terminal is None:
            print(
                "PREFLIGHT_FAIL",
                "TERMINAL_INFO_UNAVAILABLE",
            )
            return 11

        if account is None:
            print(
                "PREFLIGHT_FAIL",
                "ACCOUNT_INFO_UNAVAILABLE",
            )
            return 12

        print(
            "TERMINAL_CONNECTED",
            bool(
                getattr(
                    terminal,
                    "connected",
                    False,
                )
            ),
        )

        print(
            "ACCOUNT_LOGIN",
            getattr(
                account,
                "login",
                None,
            ),
        )

        print(
            "ACCOUNT_SERVER",
            getattr(
                account,
                "server",
                None,
            ),
        )

        print(
            "ACCOUNT_TRADE_MODE",
            getattr(
                account,
                "trade_mode",
                None,
            ),
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
                "PREFLIGHT_FAIL",
                "NON_DEMO_ACCOUNT_BLOCKED",
            )
            return 13

        selected = mt5.symbol_select(
            symbol,
            True,
        )

        print(
            "SYMBOL_SELECT",
            selected,
        )

        if not selected:
            print(
                "PREFLIGHT_FAIL",
                "SYMBOL_SELECT_FAILED",
            )
            return 14

        info = mt5.symbol_info(
            symbol
        )

        if info is None:
            print(
                "PREFLIGHT_FAIL",
                "SYMBOL_INFO_UNAVAILABLE",
            )
            return 15

        point = float(
            getattr(
                info,
                "point",
                0.0,
            )
            or 0.0
        )

        digits = int(
            getattr(
                info,
                "digits",
                0,
            )
            or 0
        )

        volume_min = float(
            getattr(
                info,
                "volume_min",
                0.0,
            )
            or 0.0
        )

        volume_max = float(
            getattr(
                info,
                "volume_max",
                0.0,
            )
            or 0.0
        )

        volume_step = float(
            getattr(
                info,
                "volume_step",
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

        filling_mode = (
            DemoBrokerExecutionAdapter
            ._select_filling_mode(
                info
            )
        )

        print(
            "SYMBOL",
            symbol,
        )

        print(
            "POINT",
            point,
        )

        print(
            "DIGITS",
            digits,
        )

        print(
            "VOLUME_MIN",
            volume_min,
        )

        print(
            "VOLUME_MAX",
            volume_max,
        )

        print(
            "VOLUME_STEP",
            volume_step,
        )

        print(
            "TRADE_STOPS_LEVEL",
            stops_level,
        )

        print(
            "FILLING_MODE_SELECTED",
            filling_mode,
        )

        if (
            point <= 0
            or volume_min <= 0
            or volume_step <= 0
            or filling_mode is None
        ):
            print(
                "PREFLIGHT_FAIL",
                "INVALID_BROKER_SYMBOL_METADATA",
            )
            return 16

        positions = mt5.positions_get(
            symbol=symbol
        )

        orders = mt5.orders_get(
            symbol=symbol
        )

        if positions is None:
            print(
                "PREFLIGHT_FAIL",
                "POSITIONS_GET_UNAVAILABLE",
            )
            return 17

        if orders is None:
            print(
                "PREFLIGHT_FAIL",
                "ORDERS_GET_UNAVAILABLE",
            )
            return 18

        print(
            "EXISTING_SYMBOL_POSITIONS",
            len(positions),
        )

        print(
            "EXISTING_SYMBOL_ORDERS",
            len(orders),
        )

        if len(positions) > 0:
            print(
                "PREFLIGHT_FAIL",
                "DUPLICATE_SYMBOL_POSITION_PRESENT",
            )
            return 19

        if len(orders) > 0:
            print(
                "PREFLIGHT_FAIL",
                "DUPLICATE_SYMBOL_ORDER_PRESENT",
            )
            return 20

        tick = mt5.symbol_info_tick(
            symbol
        )

        if tick is None:
            print(
                "PREFLIGHT_FAIL",
                "TICK_UNAVAILABLE",
            )
            return 21

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

        print(
            "BID",
            bid,
        )

        print(
            "ASK",
            ask,
        )

        if bid <= 0 or ask <= 0:
            print(
                "PREFLIGHT_FAIL",
                "INVALID_MARKET_QUOTE",
            )
            return 22

        distance_points = max(
            stops_level + 20,
            100,
        )

        distance = (
            distance_points
            * point
        )

        if direction == "BUY":
            order_type = mt5.ORDER_TYPE_BUY
            price = ask
            stop_loss = price - distance
            take_profit = (
                price
                + 2.0 * distance
            )

        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = bid
            stop_loss = price + distance
            take_profit = (
                price
                - 2.0 * distance
            )

        price = round(
            price,
            digits,
        )

        stop_loss = round(
            stop_loss,
            digits,
        )

        take_profit = round(
            take_profit,
            digits,
        )

        request = {
            "action": (
                mt5.TRADE_ACTION_DEAL
            ),
            "symbol": symbol,
            "volume": volume_min,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": (
                DemoBrokerExecutionAdapter
                .MAGIC
            ),
            "comment": (
                "MSS_PREFLIGHT_NO_SEND"
            ),
            "type_time": (
                mt5.ORDER_TIME_GTC
            ),
            "type_filling": (
                filling_mode
            ),
        }

        print(
            "CHECK_VOLUME",
            volume_min,
        )

        print(
            "CHECK_PRICE",
            price,
        )

        print(
            "CHECK_SL",
            stop_loss,
        )

        print(
            "CHECK_TP",
            take_profit,
        )

        print(
            "CALLING_ORDER_CHECK",
            True,
        )

        check = mt5.order_check(
            request
        )

        if check is None:
            print(
                "PREFLIGHT_FAIL",
                "ORDER_CHECK_UNAVAILABLE",
                mt5.last_error(),
            )
            return 23

        check_retcode = int(
            getattr(
                check,
                "retcode",
                -1,
            )
        )

        print(
            "ORDER_CHECK_RETCODE",
            check_retcode,
        )

        print(
            "ORDER_CHECK_COMMENT",
            getattr(
                check,
                "comment",
                "",
            ),
        )

        print(
            "ORDER_SEND_CALLED",
            False,
        )

        if check_retcode != 0:
            print(
                "PREFLIGHT_BLOCKED",
                "ORDER_CHECK_REJECTED",
            )
            return 24

        print(
            "PREFLIGHT_PASS",
            "MT5_DEMO_EXECUTION_PATH_READY",
        )

        return 0

    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
