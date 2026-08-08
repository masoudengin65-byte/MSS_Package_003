import pytest

from mss.analysis.historical_valuation import HistoricalValuation
from mss.domain.historical_backtest import BacktestSymbolMetadata


CASES = (
    ("EURUSD", 1.10000, 0.00100, 0.00001, 1.0, 100000.0, 1.0),
    ("USDJPY", 158.000, 0.100, 0.001, 0.6312334301224594, 100000.0, 1.58),
    ("USDCAD", 1.40000, 0.00100, 0.00001, 0.7135161361674194, 100000.0, 1.40),
    ("XAUUSD", 2400.00, 10.00, 0.01, 0.1, 100.0, 1.0),
    ("BTCUSD", 60000.00, 1000.00, 0.01, 0.01, 1.0, 0.10),
    ("ETHUSD", 3000.00, 100.00, 0.01, 0.05, 5.0, 0.20),
)


def metadata(tick_size=0.01, tick_value=1.0, contract_size=100.0, **overrides):
    values = dict(
        point=tick_size,
        digits=max(0, len(str(tick_size).split(".")[-1])),
        tick_size=tick_size,
        tick_value=tick_value,
        contract_size=contract_size,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        spread_points=0.0,
    )
    values.update(overrides)
    return BacktestSymbolMetadata(**values)


@pytest.mark.parametrize(
    "symbol,entry,stop_distance,tick_size,tick_value,contract_size,expected_volume",
    CASES,
)
def test_cross_asset_tick_valuation_and_risk_sizing(
    symbol, entry, stop_distance, tick_size, tick_value, contract_size,
    expected_volume,
):
    broker = metadata(tick_size, tick_value, contract_size)
    sizing = HistoricalValuation.size_for_risk(100.0, stop_distance, broker)
    expected_ticks = stop_distance / tick_size
    expected_risk_per_lot = expected_ticks * tick_value

    assert sizing.valid, (symbol, sizing.reason)
    assert sizing.risk_amount == 100.0
    assert sizing.stop_tick_count == pytest.approx(expected_ticks)
    assert sizing.risk_per_lot == pytest.approx(expected_risk_per_lot)
    assert sizing.raw_volume == pytest.approx(100.0 / expected_risk_per_lot)
    assert sizing.rounded_volume == expected_volume
    assert sizing.rounded_risk_amount <= 100.0 + 1e-9

    buy_loss = HistoricalValuation.signed_pnl(
        entry, entry - stop_distance, "BUY", sizing.rounded_volume, broker,
    )
    buy_gain = HistoricalValuation.signed_pnl(
        entry, entry + 2 * stop_distance, "BUY", sizing.rounded_volume, broker,
    )
    sell_loss = HistoricalValuation.signed_pnl(
        entry, entry + stop_distance, "SELL", sizing.rounded_volume, broker,
    )
    sell_gain = HistoricalValuation.signed_pnl(
        entry, entry - 2 * stop_distance, "SELL", sizing.rounded_volume, broker,
    )
    assert buy_loss == pytest.approx(-sizing.rounded_risk_amount)
    assert sell_loss == pytest.approx(-sizing.rounded_risk_amount)
    assert buy_gain == pytest.approx(2 * sizing.rounded_risk_amount)
    assert sell_gain == pytest.approx(2 * sizing.rounded_risk_amount)


@pytest.mark.parametrize(
    "symbol,tick_size,tick_value,contract_size,old_ratio",
    (
        ("USDJPY", 0.001, 0.6312334301224594, 100000.0, 158.42),
        ("USDCAD", 0.00001, 0.7135161361674194, 100000.0, 1.40151),
        ("XAUUSD", 0.01, 0.1, 100.0, 10.0),
    ),
)
def test_regression_old_contract_size_tick_mismatch_is_eliminated(
    symbol, tick_size, tick_value, contract_size, old_ratio,
):
    broker = metadata(tick_size, tick_value, contract_size)
    old_value_for_one_tick_per_lot = tick_size * contract_size
    corrected = HistoricalValuation.monetary_value(tick_size, 1.0, broker)

    assert old_value_for_one_tick_per_lot / tick_value == pytest.approx(old_ratio, rel=1e-5)
    assert corrected == pytest.approx(tick_value), symbol
    assert corrected != pytest.approx(old_value_for_one_tick_per_lot)


def test_raw_volume_below_minimum_is_rejected_not_forced_up():
    broker = metadata(tick_size=1.0, tick_value=1000.0)
    sizing = HistoricalValuation.size_for_risk(100.0, 20.0, broker)

    assert sizing.raw_volume == pytest.approx(0.005)
    assert sizing.valid is False
    assert sizing.reason == "MIN_VOLUME_EXCEEDS_RISK"
    assert sizing.rounded_volume == 0.0


def test_raw_volume_exactly_at_minimum_is_allowed():
    broker = metadata(tick_size=1.0, tick_value=1000.0)
    sizing = HistoricalValuation.size_for_risk(100.0, 10.0, broker)

    assert sizing.raw_volume == pytest.approx(0.01)
    assert sizing.rounded_volume == 0.01
    assert sizing.rounded_risk_amount == pytest.approx(100.0)


def test_raw_volume_between_steps_floors_without_exceeding_risk():
    broker = metadata(tick_size=1.0, tick_value=100.0, volume_step=0.01)
    sizing = HistoricalValuation.size_for_risk(105.0, 10.0, broker)

    assert sizing.raw_volume == pytest.approx(0.105)
    assert sizing.rounded_volume == 0.10
    assert sizing.rounded_risk_amount == pytest.approx(100.0)


def test_raw_volume_above_maximum_is_capped_down():
    broker = metadata(tick_size=1.0, tick_value=1.0, volume_max=2.0)
    sizing = HistoricalValuation.size_for_risk(100.0, 1.0, broker)

    assert sizing.raw_volume == pytest.approx(100.0)
    assert sizing.rounded_volume == 2.0
    assert sizing.rounded_risk_amount == pytest.approx(2.0)


@pytest.mark.parametrize("field", HistoricalValuation.REQUIRED_FIELDS)
def test_missing_required_metadata_fails_safely(field):
    broker = metadata()
    setattr(broker, field, None)

    sizing = HistoricalValuation.size_for_risk(100.0, 1.0, broker)
    assert sizing.valid is False
    assert sizing.reason == f"MISSING_{field.upper()}"
