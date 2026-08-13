import pytest

from mss.analysis.causal_next_candle_entry_watcher import (
    CausalNextCandleEntryWatcher,
)
from mss.analysis.frozen_shadow_strategy_adapter import (
    FrozenShadowStrategyAdapter,
)
from mss.domain.pipeline_result import (
    PipelineResult,
)


def bullish_signal(
    signal_bar_epoch=9000,
):
    pipeline = PipelineResult(
        symbol="USDJPY",
        timeframe="M15",
        valid=True,
        bos_detected=True,
        bos_direction="BULLISH",
        last_low=158.500,
        last_high=159.500,
    )

    return (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=pipeline,
            signal_bar_epoch=(
                signal_bar_epoch
            ),
        )
    )


def bearish_signal(
    signal_bar_epoch=9000,
):
    pipeline = PipelineResult(
        symbol="USDJPY",
        timeframe="M15",
        valid=True,
        bos_detected=True,
        bos_direction="BEARISH",
        last_low=158.500,
        last_high=159.500,
    )

    return (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=pipeline,
            signal_bar_epoch=(
                signal_bar_epoch
            ),
        )
    )


def test_same_bar_waits():
    result = (
        CausalNextCandleEntryWatcher
        .evaluate(
            signal=None,
            previous_current_bar_epoch=9000,
            current_bar_epoch=9000,
            next_candle_sequence_confirmed=False,
            next_candle_open=159.0,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert result.valid is True

    assert (
        result.action
        == "WAIT_FOR_NEXT_BAR"
    )

    assert (
        result.shadow_entry_allowed
        is False
    )


def test_confirmed_next_sequence_without_signal():
    result = (
        CausalNextCandleEntryWatcher
        .evaluate(
            signal=None,
            previous_current_bar_epoch=9000,
            current_bar_epoch=9900,
            next_candle_sequence_confirmed=True,
            next_candle_open=159.0,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert result.valid is True
    assert result.action == "NO_SIGNAL"

    assert (
        result.next_candle_sequence_confirmed
        is True
    )


def test_unconfirmed_sequence_blocks_entry():
    result = (
        CausalNextCandleEntryWatcher
        .evaluate(
            signal=bullish_signal(),
            previous_current_bar_epoch=9000,
            current_bar_epoch=10800,
            next_candle_sequence_confirmed=False,
            next_candle_open=159.0,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert result.valid is False

    assert (
        result.action
        == "ENTRY_WINDOW_MISSED"
    )

    assert (
        result.reason
        == "NEXT_CANDLE_SEQUENCE_NOT_CONFIRMED"
    )

    assert (
        result.bar_transition_missed
        is True
    )


def test_buy_confirmed_next_sequence_is_ready():
    result = (
        CausalNextCandleEntryWatcher
        .evaluate(
            signal=bullish_signal(),
            previous_current_bar_epoch=9000,
            current_bar_epoch=9900,
            next_candle_sequence_confirmed=True,
            next_candle_open=159.000,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert result.valid is True

    assert (
        result.action
        == "SHADOW_ENTRY_READY"
    )

    assert (
        result.shadow_entry_allowed
        is True
    )

    assert result.entry.valid is True
    assert result.entry.direction == "BUY"

    assert result.entry.entry_price == pytest.approx(
        159.003,
        abs=1e-12,
    )

    assert (
        result.entry.stop_loss
        == 158.500
    )

    assert (
        result.entry.take_profit
        > result.entry.entry_price
    )

    assert (
        result.real_order_send_allowed
        is False
    )

    assert (
        result.order_send_called
        is False
    )


def test_sell_confirmed_next_sequence_is_ready():
    result = (
        CausalNextCandleEntryWatcher
        .evaluate(
            signal=bearish_signal(),
            previous_current_bar_epoch=9000,
            current_bar_epoch=9900,
            next_candle_sequence_confirmed=True,
            next_candle_open=159.000,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert result.valid is True

    assert (
        result.action
        == "SHADOW_ENTRY_READY"
    )

    assert result.entry.direction == "SELL"

    assert result.entry.entry_price == pytest.approx(
        158.997,
        abs=1e-12,
    )

    assert (
        result.entry.stop_loss
        == 159.500
    )

    assert (
        result.entry.take_profit
        < result.entry.entry_price
    )


def test_weekend_or_session_gap_can_be_next_candle():
    result = (
        CausalNextCandleEntryWatcher
        .evaluate(
            signal=bullish_signal(),
            previous_current_bar_epoch=9000,
            current_bar_epoch=181800,
            next_candle_sequence_confirmed=True,
            next_candle_open=159.000,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert result.valid is True

    assert (
        result.action
        == "SHADOW_ENTRY_READY"
    )

    assert (
        result.entry.entry_bar_epoch
        == 181800
    )


def test_signal_bar_mismatch_blocks():
    signal = bullish_signal(
        signal_bar_epoch=8100
    )

    result = (
        CausalNextCandleEntryWatcher
        .evaluate(
            signal=signal,
            previous_current_bar_epoch=9000,
            current_bar_epoch=9900,
            next_candle_sequence_confirmed=True,
            next_candle_open=159.0,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert result.valid is False

    assert (
        result.reason
        == (
            "SIGNAL_BAR_DOES_NOT_MATCH_"
            "OBSERVED_PREVIOUS_BAR"
        )
    )


def test_time_regression_blocks():
    result = (
        CausalNextCandleEntryWatcher
        .evaluate(
            signal=None,
            previous_current_bar_epoch=9900,
            current_bar_epoch=9000,
            next_candle_sequence_confirmed=False,
            next_candle_open=159.0,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert result.valid is False

    assert (
        result.reason
        == "BAR_TIME_REGRESSION"
    )
