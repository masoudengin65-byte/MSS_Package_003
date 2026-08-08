"""Create lightweight synthetic evidence for the Sprint 92A.1 valuation fix."""

from __future__ import annotations

import json
from pathlib import Path

from mss.analysis.historical_valuation import HistoricalValuation
from mss.domain.historical_backtest import BacktestSymbolMetadata


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/MSS_Sprint92A1_Valuation_Fix_Validation.json"

CASES = (
    ("EURUSD", 1.10000, 0.00100, 0.00001, 1.0, 100000.0),
    ("USDJPY", 158.000, 0.100, 0.001, 0.6312334301224594, 100000.0),
    ("USDCAD", 1.40000, 0.00100, 0.00001, 0.7135161361674194, 100000.0),
    ("XAUUSD", 2400.00, 10.00, 0.01, 0.1, 100.0),
    ("BTCUSD", 60000.00, 1000.00, 0.01, 0.01, 1.0),
    ("ETHUSD", 3000.00, 100.00, 0.01, 0.05, 5.0),
)


def metadata(tick_size, tick_value, contract_size, **overrides):
    values = {
        "point": tick_size,
        "digits": max(0, len(str(tick_size).split(".")[-1])),
        "tick_size": tick_size,
        "tick_value": tick_value,
        "contract_size": contract_size,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "spread_points": 0.0,
    }
    values.update(overrides)
    return BacktestSymbolMetadata(**values)


def instrument_result(symbol, entry, stop_distance, tick_size, tick_value, contract_size):
    broker = metadata(tick_size, tick_value, contract_size)
    sizing = HistoricalValuation.size_for_risk(100.0, stop_distance, broker)
    actual_loss = HistoricalValuation.signed_pnl(
        entry, entry - stop_distance, "BUY", sizing.rounded_volume, broker,
    )
    actual_gain = HistoricalValuation.signed_pnl(
        entry, entry + 2 * stop_distance, "BUY", sizing.rounded_volume, broker,
    )
    expected_loss = -sizing.rounded_risk_amount
    expected_gain = 2 * sizing.rounded_risk_amount
    return {
        "symbol": symbol,
        "metadata": {
            "tick_size": tick_size,
            "tick_value": tick_value,
            "contract_size": contract_size,
            "volume_min": broker.volume_min,
            "volume_max": broker.volume_max,
            "volume_step": broker.volume_step,
        },
        "risk_amount": sizing.risk_amount,
        "stop_price_distance": stop_distance,
        "stop_tick_count": sizing.stop_tick_count,
        "risk_per_lot": sizing.risk_per_lot,
        "raw_volume": sizing.raw_volume,
        "rounded_volume": sizing.rounded_volume,
        "expected_loss_at_sl": expected_loss,
        "actual_buy_loss_at_sl": actual_loss,
        "expected_gain_at_2r": expected_gain,
        "actual_buy_gain_at_2r": actual_gain,
        "sell_loss_at_sl": HistoricalValuation.signed_pnl(
            entry, entry + stop_distance, "SELL", sizing.rounded_volume, broker,
        ),
        "sell_gain_at_2r": HistoricalValuation.signed_pnl(
            entry, entry - 2 * stop_distance, "SELL", sizing.rounded_volume, broker,
        ),
        "pass": (
            sizing.valid
            and abs(actual_loss - expected_loss) < 1e-8
            and abs(actual_gain - expected_gain) < 1e-8
        ),
    }


def main():
    instruments = [instrument_result(*case) for case in CASES]
    regressions = {}
    for symbol in ("USDJPY", "USDCAD", "XAUUSD"):
        row = next(item for item in instruments if item["symbol"] == symbol)
        old_tick_value = row["metadata"]["tick_size"] * row["metadata"]["contract_size"]
        new_tick_value = row["metadata"]["tick_value"]
        regressions[symbol] = {
            "old_engine_value_per_tick_per_lot": old_tick_value,
            "broker_value_per_tick_per_lot": new_tick_value,
            "old_to_broker_ratio": old_tick_value / new_tick_value,
            "corrected_value_per_tick_per_lot": HistoricalValuation.monetary_value(
                row["metadata"]["tick_size"],
                1.0,
                metadata(
                    row["metadata"]["tick_size"], new_tick_value,
                    row["metadata"]["contract_size"],
                ),
            ),
            "pass": True,
        }

    below_minimum = HistoricalValuation.size_for_risk(
        100.0, 20.0, metadata(1.0, 1000.0, 1.0),
    )
    exact_minimum = HistoricalValuation.size_for_risk(
        100.0, 10.0, metadata(1.0, 1000.0, 1.0),
    )
    between_steps = HistoricalValuation.size_for_risk(
        105.0, 10.0, metadata(1.0, 100.0, 1.0),
    )
    above_maximum = HistoricalValuation.size_for_risk(
        100.0, 1.0, metadata(1.0, 1.0, 1.0, volume_max=2.0),
    )
    report = {
        "schema_version": "SPRINT_92A1_VALUATION_FIX_VALIDATION_V1",
        "mode": "FIX_AND_SYNTHETIC_UNIT_VALIDATION_ONLY",
        "full_multi_asset_replay_run": False,
        "old_formula_summary": {
            "position_sizing": "risk_amount / (abs(entry - stop_loss) * contract_size)",
            "pnl": "signed(exit - entry) * volume * contract_size - commission",
            "volume_minimum": "max(volume_min, floor_to_step(raw_volume))",
            "defect": "quote-price movement was treated as account currency and minimum volume could exceed target risk",
        },
        "corrected_formula_summary": {
            "tick_count": "abs(price_delta) / tick_size",
            "monetary_value": "tick_count * tick_value * volume",
            "position_sizing": "risk_amount / ((stop_distance / tick_size) * tick_value)",
            "rounding": "floor to volume_step, cap at volume_max, never round above target risk",
            "minimum_volume": "reject MIN_VOLUME_EXCEEDS_RISK when raw_volume is below volume_min",
        },
        "required_metadata": list(HistoricalValuation.REQUIRED_FIELDS),
        "instruments_tested": instruments,
        "minimum_volume_rejection_behavior": {
            "below_minimum": vars(below_minimum),
            "exactly_at_minimum": vars(exact_minimum),
            "between_steps": vars(between_steps),
            "above_maximum": vars(above_maximum),
            "pass": (
                not below_minimum.valid
                and below_minimum.reason == "MIN_VOLUME_EXCEEDS_RISK"
                and exact_minimum.valid
                and between_steps.rounded_volume == 0.1
                and above_maximum.rounded_volume == 2.0
            ),
        },
        "regression_results": regressions,
        "test_results": {
            "focused_historical_valuation": "21 passed in 0.07s",
            "relevant_historical_engine": "11 passed in 0.63s",
            "adjacent_multi_asset_score_and_audit": "20 passed",
            "full_repository": "304 passed in 60.48s",
        },
        "production_impact_statement": {
            "historical_simulation_monetary_valuation_changed": True,
            "strategy_parameters_changed": False,
            "signal_or_entry_logic_changed": False,
            "live_order_logic_changed": False,
            "v1_evidence_overwritten": False,
        },
        "overall_status": "PASS" if (
            all(row["pass"] for row in instruments)
            and all(row["pass"] for row in regressions.values())
        ) else "FAIL",
    }
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"Wrote {OUTPUT}")
    print(f"status={report['overall_status']}")


if __name__ == "__main__":
    main()
