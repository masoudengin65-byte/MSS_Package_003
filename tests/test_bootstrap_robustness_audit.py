from datetime import datetime, timedelta

import pytest

from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit


def trade(index, profit, r=None, direction="BUY"):
    timestamp = datetime(2026, 1, 1) + timedelta(hours=index)
    return {
        "symbol": "TEST", "asset_class": "TEST", "trade_id": index + 1,
        "direction": direction, "entry_time": timestamp.isoformat(),
        "exit_time": (timestamp + timedelta(minutes=15)).isoformat(),
        "realized_pnl": float(profit), "r_multiple": float(r if r is not None else profit / 100),
        "outcome": "WIN" if profit > 0 else "LOSS",
    }


def test_bootstrap_is_deterministic():
    audit = BootstrapRobustnessAudit()
    trades = [trade(i, 20 if i % 3 == 0 else -5) for i in range(30)]
    first = audit.bootstrap(trades, seed=17, resamples=200, label="same")
    second = audit.bootstrap(list(reversed(trades)), seed=17, resamples=200, label="same")
    assert first == second


def test_percentile_ci_uses_deterministic_linear_interpolation():
    audit = BootstrapRobustnessAudit()
    assert audit.percentile([0, 10, 20, 30, 40], 0.25) == 10
    assert audit.percentile([0, 10], 0.25) == pytest.approx(2.5)
    assert audit.interval([], 0.95) == {"level_percent": 95, "lower": None, "upper": None}


def test_profit_factor_zero_loss_samples_are_counted_not_silently_dropped():
    result = BootstrapRobustnessAudit().bootstrap(
        [trade(i, 10) for i in range(20)], seed=3, resamples=50, label="all-wins",
    )
    pf = result["bootstrap_metrics"]["profit_factor"]
    assert pf["valid_samples"] == 0
    assert pf["invalid_zero_gross_loss_samples"] == 50
    assert pf["probability_above_threshold"] is None


def test_moving_block_bootstrap_is_deterministic_and_records_block_length():
    audit = BootstrapRobustnessAudit()
    trades = [trade(i, 10 if i % 2 else -8) for i in range(25)]
    kwargs = dict(seed=9, resamples=100, label="block", method="moving_block_circular", block_length=5)
    assert audit.bootstrap(trades, **kwargs) == audit.bootstrap(trades, **kwargs)
    assert audit.bootstrap(trades, **kwargs)["block_length"] == 5


def test_directional_grouping_is_stable():
    audit = BootstrapRobustnessAudit()
    trades = [trade(i, i + 1, direction="BUY" if i < 3 else "SELL") for i in range(5)]
    grouped = audit.group_directions(list(reversed(trades)))
    assert [row["trade_id"] for row in grouped["BUY"]] == [1, 2, 3]
    assert [row["trade_id"] for row in grouped["SELL"]] == [4, 5]


def test_half_period_grouping_is_stable_and_odd_extra_goes_second():
    audit = BootstrapRobustnessAudit()
    trades = [trade(i, i + 1, direction="BUY" if i < 3 else "SELL") for i in range(5)]
    first, second = audit.split_halves(list(reversed(trades)))
    assert [row["trade_id"] for row in first] == [1, 2]
    assert [row["trade_id"] for row in second] == [3, 4, 5]


def test_classification_rules_are_mechanical():
    def result(point, low, high, probability):
        metric = {"point_estimate": point, "ci_95": {"lower": low, "upper": high},
                  "ci_90": {"lower": low, "upper": high}, "probability_above_threshold": probability}
        return {"available": True, "bootstrap_metrics": {
            "expectancy": metric, "mean_r": metric,
            "profit_factor": {**metric, "probability_above_threshold": probability},
        }}
    audit = BootstrapRobustnessAudit()
    assert audit.classify(result(1, .1, 2, .99), "STABLE_POSITIVE") == "ROBUST_POSITIVE"
    assert audit.classify(result(-1, -2, -.1, .01), "STABLE_NEGATIVE") == "ROBUST_NEGATIVE"
    assert audit.classify(result(1, -1, 2, .85), "MIXED") == "PROMISING_NOT_CONFIRMED"
    assert audit.classify(result(-1, -2, 1, .2), "MIXED") == "NOT_RELIABLE"


def test_small_sample_returns_explicit_unavailable_result():
    result = BootstrapRobustnessAudit().bootstrap([trade(i, 1) for i in range(19)], resamples=10)
    assert result["available"] is False
    assert result["reason"] == "FEWER_THAN_20_TRADES"
    assert result["resamples"] == 0
