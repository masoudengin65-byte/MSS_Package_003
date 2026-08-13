import pytest

from mss.analysis.frozen_shadow_strategy_adapter import (
    FrozenShadowStrategyAdapter,
)
from mss.domain.pipeline_result import (
    PipelineResult,
)


def make_result(
    *,
    bos=True,
    direction="BULLISH",
    last_low=158.0,
    last_high=160.0,
    confluence_valid=False,
    confluence_gate_rejected=False,
):
    return PipelineResult(
        symbol="USDJPY",
        timeframe="M15",
        valid=True,
        bos_detected=bos,
        bos_direction=direction,
        last_low=last_low,
        last_high=last_high,
        confluence_valid=confluence_valid,
        confluence_gate_rejected=(
            confluence_gate_rejected
        ),
    )


def test_no_bos_waits():
    result = make_result(
        bos=False
    )

    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=result,
            signal_bar_epoch=1000,
        )
    )

    assert signal.valid is False
    assert signal.action == "WAIT"
    assert signal.reason == "NO_BOS"


def test_bullish_bos_arms_buy():
    result = make_result(
        direction="BULLISH",
        last_low=158.0,
    )

    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=result,
            signal_bar_epoch=9000,
        )
    )

    assert signal.valid is True

    assert (
        signal.action
        == "PENDING_NEXT_CANDLE_ENTRY"
    )

    assert signal.direction == "BUY"
    assert signal.stop_loss == 158.0

    assert (
        signal.expected_entry_bar_epoch
        == 0
    )

    assert signal.risk_percent == 1.0
    assert (
        signal.reward_risk_ratio
        == 2.0
    )

    assert (
        signal.confluence_used_as_gate
        is False
    )

    assert (
        signal.direction_filtering
        is False
    )

    assert signal.retuning is False


def test_bearish_bos_arms_sell():
    result = make_result(
        direction="BEARISH",
        last_high=160.0,
    )

    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=result,
            signal_bar_epoch=9000,
        )
    )

    assert signal.valid is True
    assert signal.direction == "SELL"
    assert signal.stop_loss == 160.0


def test_confluence_is_not_a_gate():
    result = make_result(
        direction="BULLISH",
        confluence_valid=False,
        confluence_gate_rejected=True,
    )

    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=result,
            signal_bar_epoch=9000,
        )
    )

    assert signal.valid is True
    assert signal.direction == "BUY"

    assert (
        signal.confluence_used_as_gate
        is False
    )


def test_entry_without_sequence_confirmation_blocks():
    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=make_result(),
            signal_bar_epoch=9000,
        )
    )

    entry = (
        FrozenShadowStrategyAdapter
        .activate_entry(
            signal=signal,
            entry_bar_epoch=10800,
            next_candle_sequence_confirmed=False,
            next_candle_open=159.0,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert entry.valid is False

    assert (
        entry.reason
        == "NEXT_CANDLE_SEQUENCE_NOT_CONFIRMED"
    )


def test_buy_entry_matches_frozen_formula():
    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=make_result(
                direction="BULLISH",
                last_low=158.500,
            ),
            signal_bar_epoch=9000,
        )
    )

    entry = (
        FrozenShadowStrategyAdapter
        .activate_entry(
            signal=signal,
            entry_bar_epoch=9900,
            next_candle_sequence_confirmed=True,
            next_candle_open=159.000,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert entry.valid is True

    # Historical formula:
    # open + spread + one-point slippage
    assert entry.entry_price == pytest.approx(159.003, abs=1e-12)

    assert entry.stop_loss == 158.500

    expected_risk = (
        entry.entry_price
        - entry.stop_loss
    )

    assert (
        entry.take_profit
        == entry.entry_price
        + expected_risk * 2.0
    )

    assert (
        entry.entry_price_source
        == "FROZEN_HISTORICAL_NEXT_CANDLE_FORMULA"
    )

    assert (
        entry.real_order_send_allowed
        is False
    )


def test_sell_entry_matches_frozen_formula():
    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=make_result(
                direction="BEARISH",
                last_high=159.500,
            ),
            signal_bar_epoch=9000,
        )
    )

    entry = (
        FrozenShadowStrategyAdapter
        .activate_entry(
            signal=signal,
            entry_bar_epoch=9900,
            next_candle_sequence_confirmed=True,
            next_candle_open=159.000,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert entry.valid is True

    # Historical formula:
    # open - spread - one-point slippage
    assert entry.entry_price == pytest.approx(158.997, abs=1e-12)

    assert entry.stop_loss == 159.500

    expected_risk = (
        entry.stop_loss
        - entry.entry_price
    )

    assert (
        entry.take_profit
        == entry.entry_price
        - expected_risk * 2.0
    )


def test_invalid_buy_stop_is_blocked():
    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=make_result(
                direction="BULLISH",
                last_low=160.0,
            ),
            signal_bar_epoch=9000,
        )
    )

    entry = (
        FrozenShadowStrategyAdapter
        .activate_entry(
            signal=signal,
            entry_bar_epoch=9900,
            next_candle_sequence_confirmed=True,
            next_candle_open=159.000,
            spread_points=2.0,
            point=0.001,
        )
    )

    assert entry.valid is False
    assert entry.reason == "INVALID_BUY_STOP"


def test_non_m15_is_blocked():
    result = make_result()

    result.timeframe = "H1"

    signal = (
        FrozenShadowStrategyAdapter
        .arm_signal(
            pipeline_result=result,
            signal_bar_epoch=9000,
        )
    )

    assert signal.valid is False

    assert (
        signal.reason
        == "FROZEN_CONTRACT_REQUIRES_M15"
    )
