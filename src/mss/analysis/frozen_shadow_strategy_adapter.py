"""Frozen research-contract adapter for MSS Shadow Live."""

from __future__ import annotations

from dataclasses import dataclass

from mss.domain.pipeline_result import PipelineResult


@dataclass(frozen=True)
class FrozenShadowSignal:
    valid: bool = False

    action: str = "WAIT"
    reason: str = ""

    symbol: str = ""
    timeframe: str = ""

    direction: str = ""

    signal_bar_epoch: int = 0
    expected_entry_bar_epoch: int = 0

    stop_loss: float = 0.0

    risk_percent: float = 1.0
    reward_risk_ratio: float = 2.0
    slippage_points: float = 1.0

    entry_rule: str = "NEXT_CANDLE_OPEN"

    confluence_used_as_gate: bool = False
    direction_filtering: bool = False
    retuning: bool = False

    real_order_send_allowed: bool = False


@dataclass(frozen=True)
class FrozenShadowEntry:
    valid: bool = False
    reason: str = ""

    symbol: str = ""
    timeframe: str = ""
    direction: str = ""

    signal_bar_epoch: int = 0
    entry_bar_epoch: int = 0

    reference_bar_open: float = 0.0
    spread_points: float = 0.0
    point: float = 0.0
    slippage_points: float = 0.0

    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    risk_percent: float = 1.0
    reward_risk_ratio: float = 2.0

    entry_price_source: str = (
        "FROZEN_HISTORICAL_NEXT_CANDLE_FORMULA"
    )

    real_order_send_allowed: bool = False


class FrozenShadowStrategyAdapter:
    """
    Sprint 92H.14.3.1

    Adapter between the frozen MSS research strategy contract
    and the Shadow Live execution domain.

    Frozen contract:
    - M15
    - pipeline valid
    - BOS required
    - no direction filtering
    - confluence is diagnostic only
    - next-candle entry
    - BUY stop = signal-time last_low
    - SELL stop = signal-time last_high
    - risk = 1%
    - reward/risk = 2.0
    - slippage = 1 point
    """

    VERSION = (
        "MSS_SPRINT92H14_3_1_FROZEN_STRATEGY_ADAPTER_V1"
    )

    TIMEFRAME = "M15"
    TIMEFRAME_SECONDS = 15 * 60

    RISK_PERCENT = 1.0
    REWARD_RISK_RATIO = 2.0
    SLIPPAGE_POINTS = 1.0

    @staticmethod
    def _direction_from_bos(
        bos_direction: str,
    ) -> str:

        value = str(
            bos_direction
        ).upper()

        if value in (
            "BULLISH",
            "BUY",
        ):
            return "BUY"

        if value in (
            "BEARISH",
            "SELL",
        ):
            return "SELL"

        return ""

    @classmethod
    def arm_signal(
        cls,
        *,
        pipeline_result: PipelineResult,
        signal_bar_epoch: int,
    ) -> FrozenShadowSignal:

        if pipeline_result is None:
            return FrozenShadowSignal(
                reason="PIPELINE_RESULT_REQUIRED"
            )

        symbol = str(
            pipeline_result.symbol
            or ""
        )

        timeframe = str(
            pipeline_result.timeframe
            or ""
        ).upper()

        if not symbol:
            return FrozenShadowSignal(
                reason="SYMBOL_REQUIRED"
            )

        if timeframe != cls.TIMEFRAME:
            return FrozenShadowSignal(
                symbol=symbol,
                timeframe=timeframe,
                reason="FROZEN_CONTRACT_REQUIRES_M15",
            )

        if signal_bar_epoch <= 0:
            return FrozenShadowSignal(
                symbol=symbol,
                timeframe=timeframe,
                reason="INVALID_SIGNAL_BAR_EPOCH",
            )

        if not pipeline_result.valid:
            return FrozenShadowSignal(
                symbol=symbol,
                timeframe=timeframe,
                signal_bar_epoch=int(
                    signal_bar_epoch
                ),
                reason="PIPELINE_INVALID",
            )

        if not pipeline_result.bos_detected:
            return FrozenShadowSignal(
                symbol=symbol,
                timeframe=timeframe,
                signal_bar_epoch=int(
                    signal_bar_epoch
                ),
                reason="NO_BOS",
            )

        direction = (
            cls._direction_from_bos(
                pipeline_result.bos_direction
            )
        )

        if not direction:
            return FrozenShadowSignal(
                symbol=symbol,
                timeframe=timeframe,
                signal_bar_epoch=int(
                    signal_bar_epoch
                ),
                reason="INVALID_BOS_DIRECTION",
            )

        stop_loss = (
            pipeline_result.last_low
            if direction == "BUY"
            else pipeline_result.last_high
        )

        if stop_loss is None:
            return FrozenShadowSignal(
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                signal_bar_epoch=int(
                    signal_bar_epoch
                ),
                reason="MISSING_STOP_LEVEL",
            )

        stop_loss = float(
            stop_loss
        )

        if stop_loss <= 0:
            return FrozenShadowSignal(
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                signal_bar_epoch=int(
                    signal_bar_epoch
                ),
                reason="INVALID_STOP_LEVEL",
            )

        return FrozenShadowSignal(
            valid=True,
            action="PENDING_NEXT_CANDLE_ENTRY",
            reason="FROZEN_BOS_SIGNAL_ARMED",
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            signal_bar_epoch=int(
                signal_bar_epoch
            ),
            expected_entry_bar_epoch=0,
            stop_loss=stop_loss,
            risk_percent=cls.RISK_PERCENT,
            reward_risk_ratio=(
                cls.REWARD_RISK_RATIO
            ),
            slippage_points=(
                cls.SLIPPAGE_POINTS
            ),
            entry_rule="NEXT_CANDLE_OPEN",
            confluence_used_as_gate=False,
            direction_filtering=False,
            retuning=False,
            real_order_send_allowed=False,
        )

    @classmethod
    def activate_entry(
        cls,
        *,
        signal: FrozenShadowSignal,
        entry_bar_epoch: int,
        next_candle_sequence_confirmed: bool,
        next_candle_open: float,
        spread_points: float,
        point: float,
    ) -> FrozenShadowEntry:

        if signal is None:
            return FrozenShadowEntry(
                reason="SIGNAL_REQUIRED"
            )

        if not signal.valid:
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                reason="SIGNAL_NOT_ARMED",
            )

        if (
            signal.action
            != "PENDING_NEXT_CANDLE_ENTRY"
        ):
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                reason="SIGNAL_NOT_PENDING",
            )

        if not next_candle_sequence_confirmed:
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                signal_bar_epoch=(
                    signal.signal_bar_epoch
                ),
                entry_bar_epoch=int(
                    entry_bar_epoch
                ),
                reason=(
                    "NEXT_CANDLE_SEQUENCE_NOT_CONFIRMED"
                ),
            )

        if (
            int(entry_bar_epoch)
            <= signal.signal_bar_epoch
        ):
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                signal_bar_epoch=(
                    signal.signal_bar_epoch
                ),
                entry_bar_epoch=int(
                    entry_bar_epoch
                ),
                reason="ENTRY_BAR_NOT_AFTER_SIGNAL",
            )

        if next_candle_open <= 0:
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                reason="INVALID_NEXT_CANDLE_OPEN",
            )

        if point <= 0:
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                reason="INVALID_POINT",
            )

        if spread_points < 0:
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                reason="INVALID_SPREAD",
            )

        spread = (
            float(spread_points)
            * float(point)
        )

        slippage = (
            float(signal.slippage_points)
            * float(point)
        )

        if signal.direction == "BUY":
            entry_price = (
                float(next_candle_open)
                + spread
                + slippage
            )

        elif signal.direction == "SELL":
            entry_price = (
                float(next_candle_open)
                - spread
                - slippage
            )

        else:
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                reason="INVALID_DIRECTION",
            )

        stop_loss = float(
            signal.stop_loss
        )

        if (
            signal.direction == "BUY"
            and stop_loss >= entry_price
        ):
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                signal_bar_epoch=(
                    signal.signal_bar_epoch
                ),
                entry_bar_epoch=int(
                    entry_bar_epoch
                ),
                reference_bar_open=float(
                    next_candle_open
                ),
                entry_price=float(
                    entry_price
                ),
                stop_loss=stop_loss,
                reason="INVALID_BUY_STOP",
            )

        if (
            signal.direction == "SELL"
            and stop_loss <= entry_price
        ):
            return FrozenShadowEntry(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                signal_bar_epoch=(
                    signal.signal_bar_epoch
                ),
                entry_bar_epoch=int(
                    entry_bar_epoch
                ),
                reference_bar_open=float(
                    next_candle_open
                ),
                entry_price=float(
                    entry_price
                ),
                stop_loss=stop_loss,
                reason="INVALID_SELL_STOP",
            )

        stop_distance = abs(
            entry_price
            - stop_loss
        )

        take_profit = (
            entry_price
            + (
                stop_distance
                * signal.reward_risk_ratio
            )
            if signal.direction == "BUY"
            else entry_price
            - (
                stop_distance
                * signal.reward_risk_ratio
            )
        )

        return FrozenShadowEntry(
            valid=True,
            reason="FROZEN_NEXT_CANDLE_ENTRY_VALID",
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction,
            signal_bar_epoch=(
                signal.signal_bar_epoch
            ),
            entry_bar_epoch=int(
                entry_bar_epoch
            ),
            reference_bar_open=float(
                next_candle_open
            ),
            spread_points=float(
                spread_points
            ),
            point=float(point),
            slippage_points=float(
                signal.slippage_points
            ),
            entry_price=float(
                entry_price
            ),
            stop_loss=stop_loss,
            take_profit=float(
                take_profit
            ),
            risk_percent=float(
                signal.risk_percent
            ),
            reward_risk_ratio=float(
                signal.reward_risk_ratio
            ),
            real_order_send_allowed=False,
        )
