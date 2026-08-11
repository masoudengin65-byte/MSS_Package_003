from datetime import datetime, timedelta

import pytest

from mss.analysis.temporal_stability_audit import TemporalStabilityAudit


def trade(index, profit, direction="BUY", month=1, r=None):
    timestamp = datetime(2026, month, 1) + timedelta(hours=index)
    return {
        "symbol": "TEST", "trade_id": index + 1, "direction": direction,
        "entry_time": timestamp.isoformat(), "exit_time": (timestamp + timedelta(minutes=15)).isoformat(),
        "profit": float(profit), "r_multiple": float(r if r is not None else profit / 100.0),
        "pre_trade_equity": 10000.0, "outcome": "WIN" if profit > 0 else "LOSS",
    }


def test_monthly_grouping_is_chronological_and_deterministic():
    audit = TemporalStabilityAudit()
    trades = [trade(0, 10, month=2), trade(1, -5, month=1), trade(2, 20, month=2)]
    first = audit.monthly(trades)
    second = audit.monthly(list(reversed(trades)))
    assert first == second
    assert [row["month"] for row in first] == ["2026-01", "2026-02"]
    assert first[1]["trades"] == 2
    assert first[1]["net_profit"] == 30.0
    assert first[1]["low_sample_size"] is True


def test_odd_half_split_puts_extra_trade_in_second_half():
    result = TemporalStabilityAudit().halves([trade(i, 10) for i in range(5)])
    assert result["first_half"]["trades"] == 2
    assert result["second_half"]["trades"] == 3
    assert result["odd_trade_assignment"] == "SECOND_HALF"


def test_rolling_window_calculations_and_small_sample_handling():
    audit = TemporalStabilityAudit()
    insufficient = audit.rolling([trade(i, 10) for i in range(39)])
    assert insufficient == {"available": False, "reason": "FEWER_THAN_40_CLOSED_TRADES", "window_size": 20, "windows": []}
    result = audit.rolling([trade(i, 10 if i % 2 == 0 else -5) for i in range(40)])
    assert result["available"] is True
    assert result["window_count"] == 21
    assert result["windows"][0]["expectancy"] == pytest.approx(2.5)
    assert result["windows"][0]["win_rate_percent"] == 50.0


def test_directional_grouping_reports_buy_and_sell_separately():
    result = TemporalStabilityAudit().directional([
        trade(0, 20, "BUY"), trade(1, -10, "BUY"), trade(2, -5, "SELL"),
    ])
    assert result["BUY"]["full_period"]["trades"] == 2
    assert result["BUY"]["full_period"]["net_profit"] == 10.0
    assert result["SELL"]["full_period"]["trades"] == 1
    assert result["SELL"]["full_period"]["net_profit"] == -5.0


def test_classification_rules_are_mechanical():
    audit = TemporalStabilityAudit()
    positive = [trade(i, 10, month=1 if i < 20 else 2) for i in range(40)]
    negative = [trade(i, -10, month=1 if i < 20 else 2) for i in range(40)]
    mixed = [trade(i, 10 if i < 20 else -20, month=1 if i < 20 else 2) for i in range(40)]
    for trades, expected in ((positive, "STABLE_POSITIVE"), (negative, "STABLE_NEGATIVE"), (mixed, "MIXED")):
        halves = audit.halves(trades)
        assert audit.classify(trades, halves, audit.monthly(trades))["classification"] == expected


def test_empty_and_small_samples_are_safe_and_insufficient():
    audit = TemporalStabilityAudit()
    assert audit.metrics([])["trades"] == 0
    assert audit.monthly([]) == []
    halves = audit.halves([])
    assert halves["first_half"]["expectancy"] == 0.0
    assert audit.classify([], halves, [])["classification"] == "INSUFFICIENT"
