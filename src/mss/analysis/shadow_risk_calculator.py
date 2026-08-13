"""Broker-aware shadow risk sizing for MSS."""

from __future__ import annotations

import math
from dataclasses import dataclass

import MetaTrader5 as mt5


@dataclass(frozen=True)
class ShadowRiskResult:
    valid: bool = False
    reason: str = ""

    symbol: str = ""
    direction: str = ""

    balance: float = 0.0
    risk_percent: float = 0.0
    risk_amount: float = 0.0

    entry_price: float = 0.0
    stop_loss: float = 0.0

    loss_per_one_lot: float = 0.0

    raw_volume: float = 0.0
    normalized_volume: float = 0.0

    volume_min: float = 0.0
    volume_max: float = 0.0
    volume_step: float = 0.0

    order_calc_profit_used: bool = False
    real_order_send_allowed: bool = False


class ShadowRiskCalculator:
    """
    Sprint 92H.14.2

    Broker-aware virtual position sizing.

    Uses MT5 valuation only.
    Never sends or checks an order.
    """

    VERSION = (
        "MSS_SPRINT92H14_2_SHADOW_RISK_CALCULATOR_V1"
    )

    @staticmethod
    def _direction_to_order_type(direction: str):
        direction = str(direction).upper()

        if direction == "BUY":
            return mt5.ORDER_TYPE_BUY

        if direction == "SELL":
            return mt5.ORDER_TYPE_SELL

        return None

    @staticmethod
    def _normalize_volume_down(
        raw_volume: float,
        volume_min: float,
        volume_max: float,
        volume_step: float,
    ) -> float:

        if (
            raw_volume <= 0
            or volume_min <= 0
            or volume_max <= 0
            or volume_step <= 0
        ):
            return 0.0

        # Never round upward: that could exceed requested risk.
        steps = math.floor(
            (raw_volume / volume_step)
            + 1e-12
        )

        normalized = (
            steps * volume_step
        )

        if normalized < volume_min:
            return 0.0

        normalized = min(
            normalized,
            volume_max,
        )

        # Stable decimal representation for broker volume steps.
        return round(
            normalized,
            8,
        )

    @classmethod
    def calculate(
        cls,
        *,
        symbol: str,
        direction: str,
        balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
    ) -> ShadowRiskResult:

        if not symbol:
            return ShadowRiskResult(
                reason="SYMBOL_REQUIRED"
            )

        order_type = (
            cls._direction_to_order_type(
                direction
            )
        )

        if order_type is None:
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                reason="INVALID_DIRECTION",
            )

        if balance <= 0:
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                reason="INVALID_BALANCE",
            )

        if risk_percent <= 0:
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                reason="INVALID_RISK_PERCENT",
            )

        if (
            entry_price <= 0
            or stop_loss <= 0
            or entry_price == stop_loss
        ):
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                entry_price=entry_price,
                stop_loss=stop_loss,
                reason="INVALID_PRICE_OR_STOP",
            )

        if (
            direction.upper() == "BUY"
            and stop_loss >= entry_price
        ):
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                entry_price=entry_price,
                stop_loss=stop_loss,
                reason="BUY_STOP_MUST_BE_BELOW_ENTRY",
            )

        if (
            direction.upper() == "SELL"
            and stop_loss <= entry_price
        ):
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                entry_price=entry_price,
                stop_loss=stop_loss,
                reason="SELL_STOP_MUST_BE_ABOVE_ENTRY",
            )

        info = mt5.symbol_info(
            symbol
        )

        if info is None:
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                entry_price=entry_price,
                stop_loss=stop_loss,
                reason="SYMBOL_INFO_UNAVAILABLE",
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

        one_lot_profit = (
            mt5.order_calc_profit(
                order_type,
                symbol,
                1.0,
                float(entry_price),
                float(stop_loss),
            )
        )

        if one_lot_profit is None:
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                entry_price=entry_price,
                stop_loss=stop_loss,
                volume_min=volume_min,
                volume_max=volume_max,
                volume_step=volume_step,
                reason="ORDER_CALC_PROFIT_UNAVAILABLE",
            )

        loss_per_one_lot = abs(
            float(one_lot_profit)
        )

        if loss_per_one_lot <= 0:
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                entry_price=entry_price,
                stop_loss=stop_loss,
                volume_min=volume_min,
                volume_max=volume_max,
                volume_step=volume_step,
                order_calc_profit_used=True,
                reason="NONPOSITIVE_ONE_LOT_LOSS",
            )

        risk_amount = (
            float(balance)
            * float(risk_percent)
            / 100.0
        )

        raw_volume = (
            risk_amount
            / loss_per_one_lot
        )

        normalized_volume = (
            cls._normalize_volume_down(
                raw_volume,
                volume_min,
                volume_max,
                volume_step,
            )
        )

        if normalized_volume <= 0:
            return ShadowRiskResult(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                risk_amount=risk_amount,
                entry_price=entry_price,
                stop_loss=stop_loss,
                loss_per_one_lot=loss_per_one_lot,
                raw_volume=raw_volume,
                normalized_volume=0.0,
                volume_min=volume_min,
                volume_max=volume_max,
                volume_step=volume_step,
                order_calc_profit_used=True,
                reason=(
                    "RISK_VOLUME_BELOW_BROKER_MINIMUM"
                ),
            )

        return ShadowRiskResult(
            valid=True,
            reason="SHADOW_RISK_SIZE_VALID",
            symbol=symbol,
            direction=direction.upper(),
            balance=float(balance),
            risk_percent=float(risk_percent),
            risk_amount=risk_amount,
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            loss_per_one_lot=loss_per_one_lot,
            raw_volume=raw_volume,
            normalized_volume=normalized_volume,
            volume_min=volume_min,
            volume_max=volume_max,
            volume_step=volume_step,
            order_calc_profit_used=True,
            real_order_send_allowed=False,
        )
