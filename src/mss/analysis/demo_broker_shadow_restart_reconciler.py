"""Pure fail-safe reconciliation for Demo broker/Shadow restart."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mss.analysis.virtual_position_engine import VirtualPosition


@dataclass(frozen=True)
class DemoBrokerPositionSnapshot:
    ticket: int = 0
    identifier: int = 0
    magic: int = 0
    symbol: str = ""
    direction: str = ""
    volume: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    open_broker_epoch: int = 0
    point: float = 0.0
    volume_step: float = 0.0


@dataclass(frozen=True)
class DemoBrokerShadowRestartResult:
    valid: bool = False
    resume_allowed: bool = False
    reason: str = ""
    broker_ticket: int = 0
    broker_identifier: int = 0
    broker_symbol: str = ""
    broker_open_broker_epoch: int = 0
    shadow_position_id: str = ""
    shadow_symbol: str = ""
    real_order_send_allowed: bool = False


class DemoBrokerShadowRestartReconciler:
    """Compare previously-read broker state with recovered Shadow state."""

    MAGIC = 920146

    @classmethod
    def reconcile(
        cls,
        *,
        broker_positions: Iterable[DemoBrokerPositionSnapshot],
        pending_order_count: int,
        shadow_positions: Iterable[VirtualPosition],
    ) -> DemoBrokerShadowRestartResult:
        brokers = tuple(broker_positions)
        shadows = tuple(shadow_positions)

        def result(
            reason: str,
            valid: bool = False,
            resume_allowed: bool = False,
        ):
            broker = brokers[0] if len(brokers) == 1 else None
            shadow = shadows[0] if len(shadows) == 1 else None
            return DemoBrokerShadowRestartResult(
                valid=valid,
                resume_allowed=resume_allowed,
                reason=reason,
                broker_ticket=broker.ticket if broker else 0,
                broker_identifier=broker.identifier if broker else 0,
                broker_symbol=broker.symbol if broker else "",
                broker_open_broker_epoch=(
                    broker.open_broker_epoch if broker else 0
                ),
                shadow_position_id=(shadow.position_id if shadow else ""),
                shadow_symbol=shadow.symbol if shadow else "",
                real_order_send_allowed=False,
            )

        if pending_order_count < 0:
            return result("INVALID_PENDING_ORDER_COUNT")
        if pending_order_count:
            return result("MSS_PENDING_ORDER_PRESENT")
        if len(brokers) > 1:
            return result("MULTIPLE_MSS_BROKER_POSITIONS")
        if len(shadows) > 1:
            return result("MULTIPLE_OPEN_SHADOW_POSITIONS")
        if not brokers and not shadows:
            return result("NO_BROKER_OR_SHADOW_EXPOSURE", True, False)
        if not brokers:
            return result("SHADOW_OPEN_POSITION_WITHOUT_BROKER_EXPOSURE")
        if not shadows:
            return result("BROKER_OPEN_POSITION_WITHOUT_SHADOW_EXPOSURE")

        broker = brokers[0]
        shadow = shadows[0]
        if broker.magic != cls.MAGIC:
            return result("BROKER_MAGIC_MISMATCH")
        if (
            broker.ticket <= 0
            or broker.identifier <= 0
            or not broker.symbol.strip()
            or broker.direction.upper() not in ("BUY", "SELL")
            or broker.volume <= 0
            or broker.entry_price <= 0
            or broker.stop_loss <= 0
            or broker.take_profit <= 0
            or broker.open_broker_epoch <= 0
            or broker.point <= 0
            or broker.volume_step <= 0
        ):
            return result("INVALID_BROKER_POSITION_METADATA")
        if (
            not shadow.valid
            or shadow.status != "OPEN"
            or not shadow.position_id
            or shadow.open_broker_epoch <= 0
        ):
            return result("INVALID_OPEN_SHADOW_POSITION")
        if broker.symbol != shadow.symbol:
            return result("BROKER_SHADOW_SYMBOL_MISMATCH")
        if broker.direction.upper() != shadow.direction.upper():
            return result("BROKER_SHADOW_DIRECTION_MISMATCH")
        if abs(broker.volume - shadow.volume) > broker.volume_step / 2.0:
            return result("BROKER_SHADOW_VOLUME_MISMATCH")
        price_tolerance = broker.point
        if abs(broker.entry_price - shadow.entry_price) > price_tolerance:
            return result("BROKER_SHADOW_ENTRY_MISMATCH")
        if abs(broker.stop_loss - shadow.stop_loss) > price_tolerance:
            return result("BROKER_SHADOW_SL_MISMATCH")
        if abs(broker.take_profit - shadow.take_profit) > price_tolerance:
            return result("BROKER_SHADOW_TP_MISMATCH")
        if broker.open_broker_epoch != shadow.open_broker_epoch:
            return result("BROKER_SHADOW_OPEN_EPOCH_MISMATCH")
        return result(
            "BROKER_SHADOW_RESTART_MATCH_CONFIRMED", True, True
        )
