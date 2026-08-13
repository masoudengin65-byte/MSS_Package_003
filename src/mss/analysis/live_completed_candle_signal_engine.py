"""Completed-candle causal MSS signal engine for Shadow Live."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from mss.analysis.frozen_shadow_strategy_adapter import (
    FrozenShadowSignal,
    FrozenShadowStrategyAdapter,
)
from mss.analysis.smart_money_pipeline import (
    SmartMoneyPipeline,
)
from mss.domain.candle import Candle
from mss.domain.pipeline_result import (
    PipelineResult,
)


@dataclass(frozen=True)
class CompletedCandleDecision:
    valid: bool = False

    action: str = "BLOCKED"
    reason: str = ""

    symbol: str = ""
    timeframe: str = "M15"

    requested_completed_candles: int = 500
    completed_candle_count: int = 0

    current_bar_epoch: int = 0
    signal_bar_epoch: int = 0

    forming_candle_excluded: bool = False
    completed_candles_only: bool = False

    pipeline_result: PipelineResult | None = None
    frozen_signal: FrozenShadowSignal | None = None

    entry_window_status: str = "NOT_APPLICABLE"

    real_order_send_allowed: bool = False
    shadow_trade_opened: bool = False


class LiveCompletedCandleSignalEngine:
    """
    Sprint 92H.14.3.2

    Produces an MSS decision from completed M15 bars only.

    Raw MT5 broker epochs are the ordering domain.
    No trade is opened by this component.
    """

    VERSION = (
        "MSS_SPRINT92H14_3_2_COMPLETED_CANDLE_SIGNAL_ENGINE_V1"
    )

    TIMEFRAME = "M15"
    TIMEFRAME_SECONDS = 900
    REQUIRED_COMPLETED_CANDLES = 500

    def __init__(
        self,
        pipeline=None,
    ):
        self.pipeline = (
            pipeline
            if pipeline is not None
            else SmartMoneyPipeline()
        )

    @staticmethod
    def _rate_value(
        rate,
        name: str,
    ):
        try:
            return rate[name]
        except (TypeError, KeyError, IndexError):
            return getattr(
                rate,
                name,
            )

    @staticmethod
    def _epoch_domain_datetime(
        epoch: int,
    ) -> datetime:
        """
        Preserve raw broker-epoch ordering without using
        host-local timezone conversion.
        """
        return (
            datetime(1970, 1, 1)
            + timedelta(
                seconds=int(epoch)
            )
        )

    @classmethod
    def _to_candle(
        cls,
        rate,
    ) -> Candle:

        epoch = int(
            cls._rate_value(
                rate,
                "time",
            )
        )

        return Candle(
            time=cls._epoch_domain_datetime(
                epoch
            ),
            open=float(
                cls._rate_value(
                    rate,
                    "open",
                )
            ),
            high=float(
                cls._rate_value(
                    rate,
                    "high",
                )
            ),
            low=float(
                cls._rate_value(
                    rate,
                    "low",
                )
            ),
            close=float(
                cls._rate_value(
                    rate,
                    "close",
                )
            ),
            tick_volume=int(
                cls._rate_value(
                    rate,
                    "tick_volume",
                )
            ),
            spread=int(
                cls._rate_value(
                    rate,
                    "spread",
                )
            ),
            real_volume=int(
                cls._rate_value(
                    rate,
                    "real_volume",
                )
            ),
        )

    @classmethod
    def completed_rates(
        cls,
        *,
        rates,
        current_bar_epoch: int,
    ):
        if rates is None:
            return []

        selected = []

        for rate in rates:
            epoch = int(
                cls._rate_value(
                    rate,
                    "time",
                )
            )

            if epoch < int(
                current_bar_epoch
            ):
                selected.append(
                    rate
                )

        selected.sort(
            key=lambda item: int(
                cls._rate_value(
                    item,
                    "time",
                )
            )
        )

        deduplicated = []
        seen = set()

        for rate in selected:
            epoch = int(
                cls._rate_value(
                    rate,
                    "time",
                )
            )

            if epoch in seen:
                continue

            seen.add(epoch)
            deduplicated.append(
                rate
            )

        return deduplicated

    def evaluate(
        self,
        *,
        symbol: str,
        rates,
        current_bar_epoch: int,
    ) -> CompletedCandleDecision:

        if not symbol:
            return CompletedCandleDecision(
                reason="SYMBOL_REQUIRED"
            )

        if current_bar_epoch <= 0:
            return CompletedCandleDecision(
                symbol=symbol,
                reason="INVALID_CURRENT_BAR_EPOCH",
            )

        completed = (
            self.completed_rates(
                rates=rates,
                current_bar_epoch=(
                    current_bar_epoch
                ),
            )
        )

        if (
            len(completed)
            < self.REQUIRED_COMPLETED_CANDLES
        ):
            return CompletedCandleDecision(
                symbol=symbol,
                current_bar_epoch=int(
                    current_bar_epoch
                ),
                completed_candle_count=(
                    len(completed)
                ),
                forming_candle_excluded=True,
                completed_candles_only=True,
                reason=(
                    "INSUFFICIENT_COMPLETED_CANDLES"
                ),
            )

        completed = completed[
            -self.REQUIRED_COMPLETED_CANDLES:
        ]

        signal_bar_epoch = int(
            self._rate_value(
                completed[-1],
                "time",
            )
        )

        expected_signal_bar = (
            int(current_bar_epoch)
            - self.TIMEFRAME_SECONDS
        )

        if (
            signal_bar_epoch
            != expected_signal_bar
        ):
            return CompletedCandleDecision(
                symbol=symbol,
                current_bar_epoch=int(
                    current_bar_epoch
                ),
                signal_bar_epoch=(
                    signal_bar_epoch
                ),
                completed_candle_count=(
                    len(completed)
                ),
                forming_candle_excluded=True,
                completed_candles_only=True,
                reason=(
                    "LATEST_COMPLETED_BAR_NOT_ADJACENT"
                ),
            )

        candles = [
            self._to_candle(rate)
            for rate in completed
        ]

        pipeline_result = (
            self.pipeline.run(
                symbol,
                self.TIMEFRAME,
                candles,
            )
        )

        frozen_signal = (
            FrozenShadowStrategyAdapter
            .arm_signal(
                pipeline_result=(
                    pipeline_result
                ),
                signal_bar_epoch=(
                    signal_bar_epoch
                ),
            )
        )

        if frozen_signal.valid:
            action = (
                "PENDING_NEXT_CANDLE_ENTRY"
            )

            if (
                frozen_signal
                .expected_entry_bar_epoch
                == int(current_bar_epoch)
            ):
                entry_window_status = (
                    "CURRENT_ENTRY_BAR_ALREADY_OPEN_"
                    "OBSERVATION_ONLY"
                )
            else:
                entry_window_status = (
                    "ENTRY_BAR_NOT_CURRENT"
                )

            reason = frozen_signal.reason

        else:
            action = "WAIT"
            entry_window_status = (
                "NOT_APPLICABLE"
            )
            reason = frozen_signal.reason

        return CompletedCandleDecision(
            valid=True,
            action=action,
            reason=reason,
            symbol=symbol,
            timeframe=self.TIMEFRAME,
            requested_completed_candles=(
                self.REQUIRED_COMPLETED_CANDLES
            ),
            completed_candle_count=(
                len(candles)
            ),
            current_bar_epoch=int(
                current_bar_epoch
            ),
            signal_bar_epoch=(
                signal_bar_epoch
            ),
            forming_candle_excluded=True,
            completed_candles_only=True,
            pipeline_result=(
                pipeline_result
            ),
            frozen_signal=(
                frozen_signal
            ),
            entry_window_status=(
                entry_window_status
            ),
            real_order_send_allowed=False,
            shadow_trade_opened=False,
        )
