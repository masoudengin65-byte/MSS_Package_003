"""Unified Shadow Live virtual trade engine for MSS."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from mss.analysis.shadow_risk_calculator import (
    ShadowRiskCalculator,
    ShadowRiskResult,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)
from mss.analysis.shadow_trade_valuation import (
    ShadowTradeValuation,
)
from mss.analysis.virtual_position_engine import (
    VirtualPosition,
    VirtualPositionEngine,
)


@dataclass(frozen=True)
class ShadowTradeEngineResult:
    valid: bool = False
    action: str = "NONE"
    reason: str = ""

    position: VirtualPosition | None = None
    risk: ShadowRiskResult | None = None

    journal_event: dict[str, Any] | None = None

    real_order_send_allowed: bool = False
    order_send_called: bool = False
    order_check_called: bool = False

    true_oos_data_accessed: bool = False
    true_oos_artifacts_modified: bool = False


class ShadowTradeEngine:
    """
from dataclasses import replace
    Sprint 92H.14.2

    Unified virtual trading lifecycle.

    Strict guarantees:
    - no MT5 order_send
    - no MT5 order_check
    - no real order modification
    - no real position modification
    - no True-OOS artifact access
    """

    VERSION = (
        "MSS_SPRINT92H14_2_UNIFIED_SHADOW_TRADE_ENGINE_V1"
    )

    @staticmethod
    def _validate_journal_path(
        journal_path,
    ) -> Path:

        path = Path(
            journal_path
        )

        normalized = (
            str(path)
            .replace("\\", "/")
            .lower()
        )

        prohibited_fragments = (
            "sprint92h_true_oos",
            "true_oos_v2",
            "/true_oos/",
        )

        for fragment in prohibited_fragments:
            if fragment in normalized:
                raise RuntimeError(
                    "SHADOW_TRUE_OOS_NAMESPACE_COLLISION"
                )

        return path

    @classmethod
    def open_trade(
        cls,
        *,
        journal_path,
        position_id: str,
        symbol: str,
        direction: str,
        balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        broker_epoch: int,
        volume_override: float | None = None,
    ) -> ShadowTradeEngineResult:

        journal_path = (
            cls._validate_journal_path(
                journal_path
            )
        )

        risk = (
            ShadowRiskCalculator.calculate(
                symbol=symbol,
                direction=direction,
                balance=balance,
                risk_percent=risk_percent,
                entry_price=entry_price,
                stop_loss=stop_loss,
            )
        )

        if not risk.valid:
            return ShadowTradeEngineResult(
                valid=False,
                action="OPEN_BLOCKED",
                reason=risk.reason,
                risk=risk,
            )

        position_volume = float(
            risk.normalized_volume
        )

        if volume_override is not None:
            override = float(
                volume_override
            )

            tolerance = max(
                1e-12,
                float(risk.volume_step) * 1e-9,
            )

            if override <= 0:
                return ShadowTradeEngineResult(
                    valid=False,
                    action="OPEN_BLOCKED",
                    reason="INVALID_VOLUME_OVERRIDE",
                    risk=risk,
                )

            if (
                override
                >
                float(risk.normalized_volume)
                + tolerance
            ):
                return ShadowTradeEngineResult(
                    valid=False,
                    action="OPEN_BLOCKED",
                    reason=(
                        "VOLUME_OVERRIDE_EXCEEDS_"
                        "RISK_NORMALIZED_VOLUME"
                    ),
                    risk=risk,
                )

            if (
                override
                <
                float(risk.volume_min)
                - tolerance
                or
                override
                >
                float(risk.volume_max)
                + tolerance
            ):
                return ShadowTradeEngineResult(
                    valid=False,
                    action="OPEN_BLOCKED",
                    reason=(
                        "VOLUME_OVERRIDE_OUTSIDE_"
                        "BROKER_LIMITS"
                    ),
                    risk=risk,
                )

            step = float(
                risk.volume_step
            )

            if step <= 0:
                return ShadowTradeEngineResult(
                    valid=False,
                    action="OPEN_BLOCKED",
                    reason=(
                        "INVALID_BROKER_"
                        "VOLUME_STEP"
                    ),
                    risk=risk,
                )

            steps = round(
                override / step
            )

            if (
                abs(
                    override
                    - steps * step
                )
                >
                tolerance
            ):
                return ShadowTradeEngineResult(
                    valid=False,
                    action="OPEN_BLOCKED",
                    reason=(
                        "VOLUME_OVERRIDE_"
                        "NOT_ON_BROKER_STEP"
                    ),
                    risk=risk,
                )

            actual_risk_amount = (
                float(
                    risk.loss_per_one_lot
                )
                * override
            )

            actual_risk_percent = (
                actual_risk_amount
                / float(balance)
                * 100.0
            )

            risk = replace(
                risk,
                risk_amount=(
                    actual_risk_amount
                ),
                risk_percent=(
                    actual_risk_percent
                ),
                normalized_volume=override,
            )

            position_volume = override

        position = (
            VirtualPositionEngine.open_position(
                position_id=position_id,
                symbol=symbol,
                direction=direction,
                volume=position_volume,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                broker_epoch=broker_epoch,
            )
        )

        if not position.valid:
            return ShadowTradeEngineResult(
                valid=False,
                action="OPEN_BLOCKED",
                reason="VIRTUAL_POSITION_INVALID",
                position=position,
                risk=risk,
            )

        event = (
            ShadowTradeJournal.append_event(
                path=journal_path,
                event_type="POSITION_OPENED",
                position_id=position.position_id,
                broker_epoch=broker_epoch,
                payload={
                    "symbol": position.symbol,
                    "direction": position.direction,
                    "volume": position.volume,
                    "entry_price": position.entry_price,
                    "stop_loss": position.stop_loss,
                    "take_profit": position.take_profit,
                    "initial_risk_price": (
                        position.initial_risk_price
                    ),
                    "risk_percent": (
                        risk.risk_percent
                    ),
                    "risk_amount": (
                        risk.risk_amount
                    ),
                    "loss_per_one_lot": (
                        risk.loss_per_one_lot
                    ),
                    "raw_volume": (
                        risk.raw_volume
                    ),
                    "normalized_volume": (
                        risk.normalized_volume
                    ),
                    "broker_volume_min": (
                        risk.volume_min
                    ),
                    "broker_volume_max": (
                        risk.volume_max
                    ),
                    "broker_volume_step": (
                        risk.volume_step
                    ),
                },
            )
        )

        return ShadowTradeEngineResult(
            valid=True,
            action="POSITION_OPENED",
            reason="SHADOW_POSITION_OPENED",
            position=position,
            risk=risk,
            journal_event=event,
        )

    @classmethod
    def update_trade(
        cls,
        *,
        journal_path,
        position: VirtualPosition,
        bid: float,
        ask: float,
        broker_epoch: int,
    ) -> ShadowTradeEngineResult:

        journal_path = (
            cls._validate_journal_path(
                journal_path
            )
        )

        if position is None:
            return ShadowTradeEngineResult(
                valid=False,
                action="UPDATE_BLOCKED",
                reason="POSITION_REQUIRED",
            )

        if not position.valid:
            return ShadowTradeEngineResult(
                valid=False,
                action="UPDATE_BLOCKED",
                reason="POSITION_INVALID",
                position=position,
            )

        if position.status != "OPEN":
            return ShadowTradeEngineResult(
                valid=True,
                action="ALREADY_CLOSED",
                reason="POSITION_NOT_OPEN",
                position=position,
            )

        trigger = (
            VirtualPositionEngine.exit_trigger(
                position=position,
                bid=bid,
                ask=ask,
            )
        )

        if trigger is None:
            return ShadowTradeEngineResult(
                valid=True,
                action="POSITION_HELD",
                reason="NO_EXIT_TRIGGER",
                position=position,
            )

        close_price = (
            VirtualPositionEngine
            .market_close_price(
                direction=position.direction,
                bid=bid,
                ask=ask,
            )
        )

        valuation = (
            ShadowTradeValuation.calculate(
                symbol=position.symbol,
                direction=position.direction,
                volume=position.volume,
                entry_price=position.entry_price,
                close_price=close_price,
            )
        )

        if not valuation.valid:
            return ShadowTradeEngineResult(
                valid=False,
                action="EXIT_VALUATION_BLOCKED",
                reason=valuation.reason,
                position=position,
            )

        closed_position = (
            VirtualPositionEngine.close_position(
                position=position,
                close_price=close_price,
                broker_epoch=broker_epoch,
                reason=trigger,
                pnl_account_currency=(
                    valuation.pnl_account_currency
                ),
            )
        )

        if closed_position.status != "CLOSED":
            return ShadowTradeEngineResult(
                valid=False,
                action="EXIT_BLOCKED",
                reason="VIRTUAL_CLOSE_FAILED",
                position=position,
            )

        event = (
            ShadowTradeJournal.append_event(
                path=journal_path,
                event_type="POSITION_CLOSED",
                position_id=(
                    closed_position.position_id
                ),
                broker_epoch=broker_epoch,
                payload={
                    "symbol": (
                        closed_position.symbol
                    ),
                    "direction": (
                        closed_position.direction
                    ),
                    "volume": (
                        closed_position.volume
                    ),
                    "entry_price": (
                        closed_position.entry_price
                    ),
                    "close_price": (
                        closed_position.close_price
                    ),
                    "stop_loss": (
                        closed_position.stop_loss
                    ),
                    "take_profit": (
                        closed_position.take_profit
                    ),
                    "exit_reason": (
                        closed_position.exit_reason
                    ),
                    "pnl_account_currency": (
                        closed_position
                        .pnl_account_currency
                    ),
                    "r_multiple": (
                        closed_position.r_multiple
                    ),
                    "valuation_method": (
                        "MT5_ORDER_CALC_PROFIT"
                    ),
                },
            )
        )

        return ShadowTradeEngineResult(
            valid=True,
            action="POSITION_CLOSED",
            reason=trigger,
            position=closed_position,
            journal_event=event,
        )
