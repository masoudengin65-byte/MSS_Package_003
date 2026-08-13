from mss.analysis.live_completed_candle_signal_engine import (
    LiveCompletedCandleSignalEngine,
)
from mss.domain.pipeline_result import (
    PipelineResult,
)


class FakePipeline:

    def __init__(
        self,
        result,
    ):
        self.result = result
        self.received = None

    def run(
        self,
        symbol,
        timeframe,
        candles,
    ):
        self.received = {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles,
        }

        return self.result


def make_rates(
    count,
    *,
    start_epoch=100000,
):
    rates = []

    for index in range(count):
        epoch = (
            start_epoch
            + index * 900
        )

        rates.append(
            {
                "time": epoch,
                "open": 159.0,
                "high": 159.2,
                "low": 158.8,
                "close": 159.1,
                "tick_volume": 100,
                "spread": 2,
                "real_volume": 0,
            }
        )

    return rates


def test_forming_candle_is_excluded():
    rates = make_rates(501)

    current_epoch = (
        rates[-1]["time"]
    )

    pipeline = FakePipeline(
        PipelineResult(
            symbol="USDJPY",
            timeframe="M15",
            valid=True,
            bos_detected=False,
        )
    )

    engine = (
        LiveCompletedCandleSignalEngine(
            pipeline=pipeline
        )
    )

    decision = engine.evaluate(
        symbol="USDJPY",
        rates=rates,
        current_bar_epoch=current_epoch,
    )

    assert decision.valid is True
    assert (
        decision.completed_candle_count
        == 500
    )

    assert (
        decision.forming_candle_excluded
        is True
    )

    assert (
        decision.completed_candles_only
        is True
    )

    assert (
        len(
            pipeline.received["candles"]
        )
        == 500
    )

    assert (
        decision.signal_bar_epoch
        == current_epoch - 900
    )


def test_no_bos_returns_wait():
    rates = make_rates(501)

    pipeline = FakePipeline(
        PipelineResult(
            symbol="USDJPY",
            timeframe="M15",
            valid=True,
            bos_detected=False,
        )
    )

    decision = (
        LiveCompletedCandleSignalEngine(
            pipeline=pipeline
        ).evaluate(
            symbol="USDJPY",
            rates=rates,
            current_bar_epoch=(
                rates[-1]["time"]
            ),
        )
    )

    assert decision.valid is True
    assert decision.action == "WAIT"
    assert decision.reason == "NO_BOS"

    assert (
        decision.shadow_trade_opened
        is False
    )


def test_real_bos_is_armed_but_not_opened():
    rates = make_rates(501)

    current_epoch = (
        rates[-1]["time"]
    )

    pipeline = FakePipeline(
        PipelineResult(
            symbol="USDJPY",
            timeframe="M15",
            valid=True,
            bos_detected=True,
            bos_direction="BULLISH",
            last_low=158.5,
            last_high=159.5,
        )
    )

    decision = (
        LiveCompletedCandleSignalEngine(
            pipeline=pipeline
        ).evaluate(
            symbol="USDJPY",
            rates=rates,
            current_bar_epoch=current_epoch,
        )
    )

    assert decision.valid is True

    assert (
        decision.action
        == "PENDING_NEXT_CANDLE_ENTRY"
    )

    assert (
        decision.frozen_signal.valid
        is True
    )

    assert (
        decision.frozen_signal.direction
        == "BUY"
    )

    assert (
        decision.frozen_signal
        .expected_entry_bar_epoch
        == current_epoch
    )

    assert (
        decision.entry_window_status
        == (
            "CURRENT_ENTRY_BAR_ALREADY_OPEN_"
            "OBSERVATION_ONLY"
        )
    )

    assert (
        decision.shadow_trade_opened
        is False
    )

    assert (
        decision.real_order_send_allowed
        is False
    )


def test_insufficient_completed_history_blocks():
    rates = make_rates(100)

    decision = (
        LiveCompletedCandleSignalEngine(
            pipeline=FakePipeline(
                PipelineResult()
            )
        ).evaluate(
            symbol="USDJPY",
            rates=rates,
            current_bar_epoch=(
                rates[-1]["time"]
            ),
        )
    )

    assert decision.valid is False

    assert (
        decision.reason
        == "INSUFFICIENT_COMPLETED_CANDLES"
    )


def test_non_adjacent_latest_bar_blocks():
    rates = make_rates(501)

    current_epoch = (
        rates[-1]["time"]
        + 1800
    )

    decision = (
        LiveCompletedCandleSignalEngine(
            pipeline=FakePipeline(
                PipelineResult()
            )
        ).evaluate(
            symbol="USDJPY",
            rates=rates,
            current_bar_epoch=current_epoch,
        )
    )

    assert decision.valid is False

    assert (
        decision.reason
        == "LATEST_COMPLETED_BAR_NOT_ADJACENT"
    )


def test_duplicate_epochs_are_removed():
    rates = make_rates(501)

    duplicate = dict(
        rates[-2]
    )

    rates.insert(
        -1,
        duplicate,
    )

    current_epoch = (
        rates[-1]["time"]
    )

    pipeline = FakePipeline(
        PipelineResult(
            symbol="USDJPY",
            timeframe="M15",
            valid=True,
            bos_detected=False,
        )
    )

    decision = (
        LiveCompletedCandleSignalEngine(
            pipeline=pipeline
        ).evaluate(
            symbol="USDJPY",
            rates=rates,
            current_bar_epoch=current_epoch,
        )
    )

    assert decision.valid is True

    assert (
        decision.completed_candle_count
        == 500
    )

