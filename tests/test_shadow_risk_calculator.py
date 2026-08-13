from types import SimpleNamespace

import MetaTrader5 as mt5

from mss.analysis.shadow_risk_calculator import (
    ShadowRiskCalculator,
)


def test_normalize_volume_never_rounds_risk_up():
    result = (
        ShadowRiskCalculator
        ._normalize_volume_down(
            raw_volume=0.237,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
    )

    assert result == 0.23


def test_volume_below_minimum_returns_zero():
    result = (
        ShadowRiskCalculator
        ._normalize_volume_down(
            raw_volume=0.009,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
    )

    assert result == 0.0


def test_buy_stop_must_be_below_entry():
    result = ShadowRiskCalculator.calculate(
        symbol="USDJPY",
        direction="BUY",
        balance=10000.0,
        risk_percent=1.0,
        entry_price=159.0,
        stop_loss=160.0,
    )

    assert result.valid is False
    assert (
        result.reason
        == "BUY_STOP_MUST_BE_BELOW_ENTRY"
    )


def test_sell_stop_must_be_above_entry():
    result = ShadowRiskCalculator.calculate(
        symbol="USDJPY",
        direction="SELL",
        balance=10000.0,
        risk_percent=1.0,
        entry_price=159.0,
        stop_loss=158.0,
    )

    assert result.valid is False
    assert (
        result.reason
        == "SELL_STOP_MUST_BE_ABOVE_ENTRY"
    )


def test_broker_aware_risk_uses_order_calc_profit(
    monkeypatch,
):
    info = SimpleNamespace(
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )

    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda symbol: info,
    )

    calls = []

    def fake_order_calc_profit(
        order_type,
        symbol,
        volume,
        entry,
        stop,
    ):
        calls.append(
            (
                order_type,
                symbol,
                volume,
                entry,
                stop,
            )
        )

        # One lot loses 500 account-currency units.
        return -500.0

    monkeypatch.setattr(
        mt5,
        "order_calc_profit",
        fake_order_calc_profit,
    )

    result = ShadowRiskCalculator.calculate(
        symbol="USDJPY",
        direction="BUY",
        balance=10000.0,
        risk_percent=1.0,
        entry_price=159.0,
        stop_loss=158.5,
    )

    assert result.valid is True
    assert result.risk_amount == 100.0
    assert result.loss_per_one_lot == 500.0
    assert result.raw_volume == 0.2
    assert result.normalized_volume == 0.2
    assert result.order_calc_profit_used is True
    assert result.real_order_send_allowed is False

    assert len(calls) == 1
    assert calls[0][1] == "USDJPY"
    assert calls[0][2] == 1.0


def test_tiny_risk_does_not_force_broker_minimum(
    monkeypatch,
):
    info = SimpleNamespace(
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )

    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda symbol: info,
    )

    monkeypatch.setattr(
        mt5,
        "order_calc_profit",
        lambda *args: -20000.0,
    )

    result = ShadowRiskCalculator.calculate(
        symbol="USDJPY",
        direction="BUY",
        balance=1000.0,
        risk_percent=0.1,
        entry_price=159.0,
        stop_loss=158.5,
    )

    assert result.valid is False
    assert result.normalized_volume == 0.0
    assert (
        result.reason
        == "RISK_VOLUME_BELOW_BROKER_MINIMUM"
    )
