"""Virtual shadow position lifecycle for MSS."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class VirtualPosition:
    position_id: str = ""

    symbol: str = ""
    direction: str = ""

    volume: float = 0.0

    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    initial_risk_price: float = 0.0

    open_broker_epoch: int = 0
    close_broker_epoch: int = 0

    broker_position_ticket: int = 0
    broker_position_identifier: int = 0

    status: str = "NEW"
    exit_reason: str = ""

    close_price: float = 0.0

    pnl_account_currency: float = 0.0
    r_multiple: float = 0.0

    valid: bool = False

    real_order_send_allowed: bool = False


@dataclass(frozen=True)
class VirtualPositionUpdate:
    position: VirtualPosition

    closed: bool = False
    reason: str = ""

    valuation_available: bool = False


class VirtualPositionEngine:
    """
    Sprint 92H.14.2

    Pure virtual lifecycle engine.

    No MT5 order_send.
    No broker position modification.
    """

    VERSION = (
        "MSS_SPRINT92H14_2_VIRTUAL_POSITION_ENGINE_V1"
    )

    @staticmethod
    def open_position(
        *,
        position_id: str,
        symbol: str,
        direction: str,
        volume: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        broker_epoch: int,
        broker_position_ticket: int = 0,
        broker_position_identifier: int = 0,
    ) -> VirtualPosition:

        direction = str(direction).upper()

        if not position_id:
            return VirtualPosition()

        if not symbol:
            return VirtualPosition()

        if direction not in (
            "BUY",
            "SELL",
        ):
            return VirtualPosition()

        if volume <= 0:
            return VirtualPosition()

        if (
            entry_price <= 0
            or stop_loss <= 0
            or take_profit <= 0
        ):
            return VirtualPosition()

        if direction == "BUY":
            if not (
                stop_loss
                < entry_price
                < take_profit
            ):
                return VirtualPosition()

        if direction == "SELL":
            if not (
                take_profit
                < entry_price
                < stop_loss
            ):
                return VirtualPosition()

        initial_risk_price = abs(
            entry_price
            - stop_loss
        )

        if initial_risk_price <= 0:
            return VirtualPosition()

        return VirtualPosition(
            position_id=position_id,
            symbol=symbol,
            direction=direction,
            volume=float(volume),
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
            initial_risk_price=(
                float(initial_risk_price)
            ),
            open_broker_epoch=int(
                broker_epoch
            ),
            broker_position_ticket=int(
                broker_position_ticket
            ),
            broker_position_identifier=int(
                broker_position_identifier
            ),
            status="OPEN",
            valid=True,
            real_order_send_allowed=False,
        )

    @staticmethod
    def market_close_price(
        *,
        direction: str,
        bid: float,
        ask: float,
    ) -> float:

        direction = str(direction).upper()

        if direction == "BUY":
            return float(bid)

        if direction == "SELL":
            return float(ask)

        return 0.0

    @staticmethod
    def exit_trigger(
        *,
        position: VirtualPosition,
        bid: float,
        ask: float,
    ) -> Optional[str]:

        if not position.valid:
            return None

        if position.status != "OPEN":
            return None

        close_price = (
            VirtualPositionEngine
            .market_close_price(
                direction=position.direction,
                bid=bid,
                ask=ask,
            )
        )

        if close_price <= 0:
            return None

        if position.direction == "BUY":
            if close_price <= position.stop_loss:
                return "STOP_LOSS"

            if close_price >= position.take_profit:
                return "TAKE_PROFIT"

        if position.direction == "SELL":
            if close_price >= position.stop_loss:
                return "STOP_LOSS"

            if close_price <= position.take_profit:
                return "TAKE_PROFIT"

        return None

    @staticmethod
    def price_r_multiple(
        *,
        position: VirtualPosition,
        close_price: float,
    ) -> float:

        if (
            not position.valid
            or position.initial_risk_price <= 0
        ):
            return 0.0

        if position.direction == "BUY":
            reward_price = (
                close_price
                - position.entry_price
            )

        elif position.direction == "SELL":
            reward_price = (
                position.entry_price
                - close_price
            )

        else:
            return 0.0

        return (
            reward_price
            / position.initial_risk_price
        )

    @classmethod
    def close_position(
        cls,
        *,
        position: VirtualPosition,
        close_price: float,
        broker_epoch: int,
        reason: str,
        pnl_account_currency: float = 0.0,
    ) -> VirtualPosition:

        if not position.valid:
            return position

        if position.status != "OPEN":
            return position

        if close_price <= 0:
            return position

        r_multiple = (
            cls.price_r_multiple(
                position=position,
                close_price=close_price,
            )
        )

        return replace(
            position,
            close_broker_epoch=int(
                broker_epoch
            ),
            status="CLOSED",
            exit_reason=str(reason),
            close_price=float(
                close_price
            ),
            pnl_account_currency=float(
                pnl_account_currency
            ),
            r_multiple=float(
                r_multiple
            ),
        )

    @classmethod
    def update_from_tick(
        cls,
        *,
        position: VirtualPosition,
        bid: float,
        ask: float,
        broker_epoch: int,
    ) -> VirtualPositionUpdate:

        trigger = cls.exit_trigger(
            position=position,
            bid=bid,
            ask=ask,
        )

        if trigger is None:
            return VirtualPositionUpdate(
                position=position,
                closed=False,
                reason="POSITION_REMAINS_OPEN",
                valuation_available=False,
            )

        close_price = (
            cls.market_close_price(
                direction=position.direction,
                bid=bid,
                ask=ask,
            )
        )

        closed_position = (
            cls.close_position(
                position=position,
                close_price=close_price,
                broker_epoch=broker_epoch,
                reason=trigger,
                pnl_account_currency=0.0,
            )
        )

        return VirtualPositionUpdate(
            position=closed_position,
            closed=True,
            reason=trigger,
            valuation_available=False,
        )
