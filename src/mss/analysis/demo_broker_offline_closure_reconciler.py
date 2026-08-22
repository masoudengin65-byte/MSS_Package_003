"""Authoritative offline broker closure reconciliation and application."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from mss.analysis.virtual_position_engine import VirtualPosition


@dataclass(frozen=True)
class DemoBrokerDealSnapshot:
    ticket: int = 0
    position_identifier: int = 0
    order_ticket: int = 0
    magic: int = 0
    comment: str = ""
    symbol: str = ""
    direction: str = ""
    entry_kind: str = ""
    reason: str = ""
    volume: float = 0.0
    price: float = 0.0
    broker_epoch: int = 0
    profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    fee: float = 0.0


@dataclass(frozen=True)
class DemoBrokerOfflineClosureResult:
    valid: bool = False
    closure_confirmed: bool = False
    reason: str = ""
    symbol: str = ""
    broker_position_identifier: int = 0
    shadow_position_id: str = ""
    exit_deal_ticket: int = 0
    exit_price: float = 0.0
    exit_broker_epoch: int = 0
    exit_reason: str = ""
    gross_profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    fee: float = 0.0
    net_result: float = 0.0
    real_order_send_allowed: bool = False


class DemoBrokerOfflineClosureReconciler:
    """Pure reconciliation over normalized broker deal-history facts."""

    MAGIC = 920146

    @classmethod
    def reconcile(
        cls,
        *,
        shadow_position: VirtualPosition | None,
        current_mss_position_count: int,
        pending_mss_order_count: int,
        deals: Iterable[DemoBrokerDealSnapshot],
    ) -> DemoBrokerOfflineClosureResult:
        history = tuple(deals)
        shadow = shadow_position

        def blocked(reason: str):
            return DemoBrokerOfflineClosureResult(
                reason=reason,
                symbol=shadow.symbol if shadow else "",
                broker_position_identifier=(
                    shadow.broker_position_identifier if shadow else 0
                ),
                shadow_position_id=shadow.position_id if shadow else "",
            )

        if current_mss_position_count != 0:
            return blocked("BROKER_EXPOSURE_STILL_PRESENT")
        if pending_mss_order_count != 0:
            return blocked("MSS_PENDING_ORDER_PRESENT")
        if (
            shadow is None
            or not shadow.valid
            or shadow.status != "OPEN"
            or not shadow.position_id
            or shadow.open_broker_epoch <= 0
            or not all(isfinite(value) for value in (
                shadow.volume,
                shadow.entry_price,
                shadow.stop_loss,
                shadow.take_profit,
            ))
            or shadow.volume <= 0
            or shadow.entry_price <= 0
        ):
            return blocked("INVALID_OPEN_SHADOW_POSITION")
        identifier = int(shadow.broker_position_identifier)
        if identifier <= 0:
            return blocked("SHADOW_BROKER_POSITION_IDENTITY_MISSING")
        if not history:
            return blocked("BROKER_DEAL_HISTORY_MISSING")

        if any(deal.position_identifier != identifier for deal in history):
            return blocked("BROKER_POSITION_IDENTIFIER_MISMATCH")
        lifecycle = history
        if any(deal.symbol != shadow.symbol for deal in lifecycle):
            return blocked("BROKER_SHADOW_SYMBOL_MISMATCH")
        if any(
            deal.ticket <= 0
            or deal.broker_epoch <= 0
            or not all(isfinite(value) for value in (
                deal.volume,
                deal.price,
                deal.profit,
                deal.commission,
                deal.swap,
                deal.fee,
            ))
            for deal in lifecycle
        ):
            return blocked("INVALID_BROKER_DEAL_METADATA")

        entries = tuple(deal for deal in lifecycle if deal.entry_kind == "IN")
        exits = tuple(deal for deal in lifecycle if deal.entry_kind in ("OUT", "OUT_BY"))
        other_kinds = tuple(
            deal for deal in lifecycle
            if deal.entry_kind not in ("IN", "OUT", "OUT_BY")
        )
        if other_kinds:
            return blocked("AMBIGUOUS_BROKER_POSITION_LIFECYCLE")
        if not entries:
            return blocked("BROKER_ENTRY_DEAL_MISSING")
        if len(entries) != 1:
            return blocked("AMBIGUOUS_BROKER_ENTRY_LIFECYCLE")
        if not exits:
            return blocked("BROKER_EXIT_DEAL_MISSING")
        if len(exits) != 1:
            return blocked("AMBIGUOUS_MULTIPLE_EXIT_DEALS")

        entry = entries[0]
        exit_deal = exits[0]
        if entry.magic != cls.MAGIC:
            return blocked("BROKER_ENTRY_MAGIC_MISMATCH")
        if entry.direction.upper() != shadow.direction.upper():
            return blocked("BROKER_SHADOW_DIRECTION_MISMATCH")
        if abs(entry.price - shadow.entry_price) > 1e-12:
            return blocked("BROKER_SHADOW_ENTRY_PRICE_MISMATCH")
        expected_exit_direction = "SELL" if shadow.direction.upper() == "BUY" else "BUY"
        if exit_deal.direction.upper() != expected_exit_direction:
            return blocked("BROKER_EXIT_DIRECTION_MISMATCH")
        volume_tolerance = 1e-9
        if (
            abs(entry.volume - shadow.volume) > volume_tolerance
            or abs(exit_deal.volume - entry.volume) > volume_tolerance
        ):
            return blocked("PARTIAL_OR_INCONSISTENT_CLOSE_VOLUME")
        if exit_deal.price <= 0:
            return blocked("INVALID_BROKER_EXIT_PRICE")
        if exit_deal.broker_epoch <= shadow.open_broker_epoch:
            return blocked("BROKER_EXIT_EPOCH_NOT_AFTER_OPEN")
        if entry.broker_epoch != shadow.open_broker_epoch:
            return blocked("BROKER_ENTRY_EPOCH_MISMATCH")

        reason = exit_deal.reason.upper()
        if reason == "SL":
            exit_reason = "STOP_LOSS"
        elif reason == "TP":
            exit_reason = "TAKE_PROFIT"
        elif reason:
            exit_reason = "BROKER_MANUAL_OR_OTHER_EXIT"
        else:
            return blocked("BROKER_EXIT_REASON_UNDETERMINED")

        gross_profit = sum(float(deal.profit) for deal in lifecycle)
        commission = sum(float(deal.commission) for deal in lifecycle)
        swap = sum(float(deal.swap) for deal in lifecycle)
        fee = sum(float(deal.fee) for deal in lifecycle)
        net_result = gross_profit + commission + swap + fee

        return DemoBrokerOfflineClosureResult(
            valid=True,
            closure_confirmed=True,
            reason="BROKER_OFFLINE_CLOSURE_CONFIRMED",
            symbol=shadow.symbol,
            broker_position_identifier=identifier,
            shadow_position_id=shadow.position_id,
            exit_deal_ticket=exit_deal.ticket,
            exit_price=exit_deal.price,
            exit_broker_epoch=exit_deal.broker_epoch,
            exit_reason=exit_reason,
            gross_profit=gross_profit,
            commission=commission,
            swap=swap,
            fee=fee,
            net_result=net_result,
            real_order_send_allowed=False,
        )
