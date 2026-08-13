"""Broker-aware valuation for MSS Shadow Live virtual trades."""

from __future__ import annotations

from dataclasses import dataclass

import MetaTrader5 as mt5


@dataclass(frozen=True)
class ShadowValuationResult:
    valid: bool = False
    reason: str = ""

    symbol: str = ""
    direction: str = ""

    volume: float = 0.0

    entry_price: float = 0.0
    close_price: float = 0.0

    pnl_account_currency: float = 0.0

    order_calc_profit_used: bool = False

    order_send_called: bool = False
    order_check_called: bool = False
    real_order_send_allowed: bool = False


class ShadowTradeValuation:
    """
    Sprint 92H.14.2

    Broker-aware P/L calculation for virtual positions.

    Uses MT5 order_calc_profit only.
    Does not send, check, modify, or close broker orders.
    """

    VERSION = (
        "MSS_SPRINT92H14_2_SHADOW_TRADE_VALUATION_V1"
    )

    @staticmethod
    def _order_type(direction: str):
        direction = str(direction).upper()

        if direction == "BUY":
            return mt5.ORDER_TYPE_BUY

        if direction == "SELL":
            return mt5.ORDER_TYPE_SELL

        return None

    @classmethod
    def calculate(
        cls,
        *,
        symbol: str,
        direction: str,
        volume: float,
        entry_price: float,
        close_price: float,
    ) -> ShadowValuationResult:

        direction = str(direction).upper()

        order_type = cls._order_type(
            direction
        )

        if not symbol:
            return ShadowValuationResult(
                reason="SYMBOL_REQUIRED"
            )

        if order_type is None:
            return ShadowValuationResult(
                symbol=symbol,
                direction=direction,
                reason="INVALID_DIRECTION",
            )

        if volume <= 0:
            return ShadowValuationResult(
                symbol=symbol,
                direction=direction,
                reason="INVALID_VOLUME",
            )

        if (
            entry_price <= 0
            or close_price <= 0
        ):
            return ShadowValuationResult(
                symbol=symbol,
                direction=direction,
                volume=float(volume),
                reason="INVALID_PRICE",
            )

        pnl = mt5.order_calc_profit(
            order_type,
            symbol,
            float(volume),
            float(entry_price),
            float(close_price),
        )

        if pnl is None:
            return ShadowValuationResult(
                symbol=symbol,
                direction=direction,
                volume=float(volume),
                entry_price=float(entry_price),
                close_price=float(close_price),
                reason="ORDER_CALC_PROFIT_UNAVAILABLE",
            )

        return ShadowValuationResult(
            valid=True,
            reason="SHADOW_VALUATION_VALID",
            symbol=symbol,
            direction=direction,
            volume=float(volume),
            entry_price=float(entry_price),
            close_price=float(close_price),
            pnl_account_currency=float(pnl),
            order_calc_profit_used=True,
            order_send_called=False,
            order_check_called=False,
            real_order_send_allowed=False,
        )
