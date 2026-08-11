from datetime import datetime, timedelta

import pytest

from mss.analysis.historical_valuation import (
    HistoricalConversionPoint, HistoricalFxResolver, HistoricalValuation,
)
from mss.domain.historical_backtest import BacktestSymbolMetadata


T0 = datetime(2026, 1, 1)


def meta(symbol="EURUSD"):
    values = {
        "EURUSD": ("EUR", "USD", "USD", 0.00001, 100000.0, 0),
        "USDJPY": ("USD", "JPY", "JPY", 0.001, 100000.0, 0),
        "USDCAD": ("USD", "CAD", "CAD", 0.00001, 100000.0, 0),
        "XAUUSD": ("USD", "USD", "USD", 0.01, 100.0, 4),
    }
    base, quote, profit, tick_size, contract, mode = values[symbol]
    return BacktestSymbolMetadata(
        account_currency="USD", currency_base=base, currency_profit=profit,
        currency_margin="USD", trade_calc_mode=mode, point=tick_size,
        digits=3 if symbol == "USDJPY" else 5, tick_size=tick_size,
        tick_value=1.0, contract_size=contract, volume_min=0.01,
        volume_max=100.0, volume_step=0.01, spread_points=0,
    )


def resolver():
    return HistoricalFxResolver({
        "EURUSD": ("EUR", "USD", [HistoricalConversionPoint(T0, 1.2)]),
        "USDJPY": ("USD", "JPY", [
            HistoricalConversionPoint(T0, 150.0),
            HistoricalConversionPoint(T0 + timedelta(minutes=15), 160.0),
        ]),
        "USDCAD": ("USD", "CAD", [HistoricalConversionPoint(T0, 1.4)]),
    })


def test_same_currency_conversion_is_exactly_one():
    result = resolver().resolve("USD", "USD", T0)
    assert result.available and result.factor == 1.0
    assert result.path == "USD->USD:IDENTITY"


def test_direct_historical_fx_conversion():
    result = resolver().resolve("EUR", "USD", T0)
    assert result.factor == pytest.approx(1.2)
    assert result.path.endswith("EURUSD:DIRECT")


def test_inverse_usdjpy_conversion_and_no_lookahead():
    result = resolver().resolve("JPY", "USD", T0 + timedelta(minutes=14))
    assert result.factor == pytest.approx(1 / 150.0)
    assert result.rate_time == T0
    assert result.path.endswith("USDJPY:INVERSE")


def test_entry_and_exit_time_resolve_independently():
    entry = resolver().resolve("JPY", "USD", T0)
    exit_ = resolver().resolve("JPY", "USD", T0 + timedelta(minutes=15))
    assert entry.factor == pytest.approx(1 / 150.0)
    assert exit_.factor == pytest.approx(1 / 160.0)
    assert entry.rate_time < exit_.rate_time


def test_missing_conversion_data_is_structured_unavailable():
    result = resolver().resolve("CAD", "CHF", T0)
    assert not result.available
    assert result.reason == "HISTORICAL_CONVERSION_UNAVAILABLE"
    assert result.factor == 0.0


@pytest.mark.parametrize(
    "symbol,delta,factor,expected",
    (("USDJPY", 0.1, 1 / 150.0, 66.6666666667),
     ("USDCAD", 0.001, 1 / 1.4, 71.4285714286),
     ("XAUUSD", 10.0, 1.0, 1000.0)),
)
def test_verified_symbol_native_to_account_examples(symbol, delta, factor, expected):
    value = HistoricalValuation.monetary_value(delta, 1.0, meta(symbol), factor)
    assert value == pytest.approx(expected)


def test_volume_step_floor_and_minimum_protection():
    broker = meta("XAUUSD")
    floored = HistoricalValuation.size_for_risk(105.0, 10.0, broker, 1.0)
    rejected = HistoricalValuation.size_for_risk(5.0, 10.0, broker, 1.0)
    assert floored.rounded_volume == 0.10
    assert floored.rounded_risk_amount == pytest.approx(100.0)
    assert not rejected.valid and rejected.reason == "MIN_VOLUME_EXCEEDS_RISK"


def test_repeated_calculation_is_deterministic_and_ignores_tick_value():
    first = meta("USDJPY")
    second = meta("USDJPY")
    first.tick_value = 0.63
    second.tick_value = 999.0
    args = (100.0, 0.1)
    a = HistoricalValuation.size_for_risk(*args, first, 1 / 150.0)
    b = HistoricalValuation.size_for_risk(*args, second, 1 / 150.0)
    assert a == b


def test_unsupported_calc_mode_fails_safely():
    broker = meta()
    broker.trade_calc_mode = 2
    result = HistoricalValuation.size_for_risk(100.0, 0.01, broker)
    assert not result.valid
    assert result.reason == "UNSUPPORTED_TRADE_CALC_MODE:2"
