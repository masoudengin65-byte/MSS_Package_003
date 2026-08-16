"""Fail-safe MT5 demo execution adapter for MSS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import MetaTrader5 as mt5


@dataclass(frozen=True)
class DemoExecutionResult:
    valid: bool = False
    reason: str = ""

    symbol: str = ""
    direction: str = ""
    volume: float = 0.0

    requested_price: float = 0.0
    fill_price: float = 0.0

    stop_loss: float = 0.0
    take_profit: float = 0.0

    order_ticket: int = 0
    deal_ticket: int = 0
    retcode: int = 0

    order_check_performed: bool = False
    order_send_performed: bool = False
    position_confirmed: bool = False


class DemoBrokerExecutionAdapter:
    """
    Opt-in MT5 DEMO execution only.

    Fail-safe rules:
    - disabled unless explicitly enabled by caller
    - rejects non-demo accounts
    - rejects duplicate symbol positions
    - rejects duplicate symbol pending orders
    - order_check always precedes order_send
    - broker-compatible filling mode
    - confirms broker position after send
    """

    MAGIC = 920146
    COMMENT = "MSS_DEMO_FORWARD"

    @staticmethod
    def _order_type(direction: str):
        direction = str(direction).upper()

        if direction == "BUY":
            return mt5.ORDER_TYPE_BUY

        if direction == "SELL":
            return mt5.ORDER_TYPE_SELL

        return None

    @staticmethod
    def _account_is_demo(account: Any) -> bool:
        if account is None:
            return False

        trade_mode = getattr(
            account,
            "trade_mode",
            None,
        )

        demo_mode = getattr(
            mt5,
            "ACCOUNT_TRADE_MODE_DEMO",
            None,
        )

        return (
            demo_mode is not None
            and trade_mode == demo_mode
        )

    @staticmethod
    def _has_duplicate_position(
        symbol: str,
    ) -> bool:

        positions = mt5.positions_get(
            symbol=symbol
        )

        if positions is None:
            raise RuntimeError(
                "POSITIONS_GET_UNAVAILABLE"
            )

        return len(positions) > 0

    @staticmethod
    def _has_duplicate_order(
        symbol: str,
    ) -> bool:

        orders = mt5.orders_get(
            symbol=symbol
        )

        if orders is None:
            raise RuntimeError(
                "ORDERS_GET_UNAVAILABLE"
            )

        return len(orders) > 0

    @staticmethod
    def _select_filling_mode(
        symbol_info: Any,
    ) -> int | None:
        """
        Select a broker-supported filling mode.

        SYMBOL_FILLING_MODE is a bit-mask of supported
        policies. Prefer IOC, then FOK, then RETURN
        when appropriate.
        """

        if symbol_info is None:
            return None

        filling_flags = int(
            getattr(
                symbol_info,
                "filling_mode",
                0,
            )
            or 0
        )

        execution_mode = getattr(
            symbol_info,
            "trade_exemode",
            None,
        )

        symbol_fill_ioc = getattr(
            mt5,
            "SYMBOL_FILLING_IOC",
            2,
        )

        symbol_fill_fok = getattr(
            mt5,
            "SYMBOL_FILLING_FOK",
            1,
        )

        market_execution = getattr(
            mt5,
            "SYMBOL_TRADE_EXECUTION_MARKET",
            None,
        )

        if (
            filling_flags
            & int(symbol_fill_ioc)
        ):
            return mt5.ORDER_FILLING_IOC

        if (
            filling_flags
            & int(symbol_fill_fok)
        ):
            return mt5.ORDER_FILLING_FOK

        if (
            market_execution is None
            or execution_mode
            != market_execution
        ):
            return mt5.ORDER_FILLING_RETURN

        return None

    @classmethod
    def execute_market_order(
        cls,
        *,
        enabled: bool,
        symbol: str,
        direction: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        deviation_points: int = 20,
    ) -> DemoExecutionResult:

        if not enabled:
            return DemoExecutionResult(
                reason="DEMO_EXECUTION_NOT_ENABLED"
            )

        if not symbol:
            return DemoExecutionResult(
                reason="SYMBOL_REQUIRED"
            )

        order_type = cls._order_type(
            direction
        )

        if order_type is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                reason="INVALID_DIRECTION",
            )

        if volume <= 0:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                reason="INVALID_VOLUME",
            )

        account = mt5.account_info()

        if account is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                reason="ACCOUNT_INFO_UNAVAILABLE",
            )

        if not cls._account_is_demo(
            account
        ):
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                reason="NON_DEMO_ACCOUNT_BLOCKED",
            )

        terminal = mt5.terminal_info()

        if terminal is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                reason="TERMINAL_INFO_UNAVAILABLE",
            )

        symbol_info = mt5.symbol_info(
            symbol
        )

        if symbol_info is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                reason="SYMBOL_INFO_UNAVAILABLE",
            )

        filling_mode = (
            cls._select_filling_mode(
                symbol_info
            )
        )

        if filling_mode is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                reason=(
                    "SUPPORTED_FILLING_MODE_UNAVAILABLE"
                ),
            )

        try:
            if cls._has_duplicate_position(
                symbol
            ):
                return DemoExecutionResult(
                    symbol=symbol,
                    direction=direction,
                    volume=volume,
                    reason=(
                        "DUPLICATE_SYMBOL_POSITION_BLOCKED"
                    ),
                )

            if cls._has_duplicate_order(
                symbol
            ):
                return DemoExecutionResult(
                    symbol=symbol,
                    direction=direction,
                    volume=volume,
                    reason=(
                        "DUPLICATE_SYMBOL_ORDER_BLOCKED"
                    ),
                )

        except RuntimeError as exc:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                reason=str(exc),
            )

        tick = mt5.symbol_info_tick(
            symbol
        )

        if tick is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                reason="SYMBOL_TICK_UNAVAILABLE",
            )

        if direction.upper() == "BUY":
            requested_price = float(
                tick.ask
            )
        else:
            requested_price = float(
                tick.bid
            )

        if requested_price <= 0:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                reason="INVALID_MARKET_PRICE",
            )

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": requested_price,
            "sl": float(stop_loss),
            "tp": float(take_profit),
            "deviation": int(
                deviation_points
            ),
            "magic": cls.MAGIC,
            "comment": cls.COMMENT,
            "type_time": (
                mt5.ORDER_TIME_GTC
            ),
            "type_filling": (
                filling_mode
            ),
        }

        check = mt5.order_check(
            request
        )

        if check is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                requested_price=requested_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason="ORDER_CHECK_UNAVAILABLE",
                order_check_performed=True,
            )

        check_retcode = int(
            getattr(
                check,
                "retcode",
                -1,
            )
        )

        # MqlTradeCheckResult uses retcode == 0
        # for a successful trade-request check.
        if check_retcode != 0:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                requested_price=requested_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                retcode=check_retcode,
                reason="ORDER_CHECK_REJECTED",
                order_check_performed=True,
            )

        result = mt5.order_send(
            request
        )

        if result is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                requested_price=requested_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason="ORDER_SEND_UNAVAILABLE",
                order_check_performed=True,
                order_send_performed=True,
            )

        retcode = int(
            getattr(
                result,
                "retcode",
                -1,
            )
        )

        done_codes = {
            int(
                getattr(
                    mt5,
                    "TRADE_RETCODE_DONE",
                    10009,
                )
            ),
            int(
                getattr(
                    mt5,
                    "TRADE_RETCODE_DONE_PARTIAL",
                    10010,
                )
            ),
        }

        if retcode not in done_codes:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                requested_price=requested_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                retcode=retcode,
                reason="ORDER_SEND_REJECTED",
                order_check_performed=True,
                order_send_performed=True,
            )

        order_ticket = int(
            getattr(
                result,
                "order",
                0,
            )
            or 0
        )

        deal_ticket = int(
            getattr(
                result,
                "deal",
                0,
            )
            or 0
        )

        fill_price = float(
            getattr(
                result,
                "price",
                0.0,
            )
            or 0.0
        )

        confirmed_positions = (
            mt5.positions_get(
                symbol=symbol
            )
        )

        if confirmed_positions is None:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                requested_price=requested_price,
                fill_price=fill_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                order_ticket=order_ticket,
                deal_ticket=deal_ticket,
                retcode=retcode,
                reason=(
                    "POST_SEND_POSITION_VERIFICATION_UNAVAILABLE"
                ),
                order_check_performed=True,
                order_send_performed=True,
            )

        matching_positions = [
            position
            for position in confirmed_positions
            if int(
                getattr(
                    position,
                    "magic",
                    0,
                )
                or 0
            )
            == cls.MAGIC
        ]

        if not matching_positions:
            return DemoExecutionResult(
                symbol=symbol,
                direction=direction,
                volume=volume,
                requested_price=requested_price,
                fill_price=fill_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                order_ticket=order_ticket,
                deal_ticket=deal_ticket,
                retcode=retcode,
                reason=(
                    "POST_SEND_POSITION_NOT_CONFIRMED"
                ),
                order_check_performed=True,
                order_send_performed=True,
            )

        return DemoExecutionResult(
            valid=True,
            reason="DEMO_ORDER_EXECUTED",
            symbol=symbol,
            direction=direction.upper(),
            volume=float(volume),
            requested_price=requested_price,
            fill_price=fill_price,
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
            order_ticket=order_ticket,
            deal_ticket=deal_ticket,
            retcode=retcode,
            order_check_performed=True,
            order_send_performed=True,
            position_confirmed=True,
        )
