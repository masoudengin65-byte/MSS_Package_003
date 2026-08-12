import json
from pathlib import Path

from mss.analysis.immutable_development_outcome_analysis import (
    ImmutableDevelopmentOutcomeAnalysis,
)


ROOT = Path(__file__).resolve().parents[1]

SOURCE = ROOT / "reports/MSS_Sprint92H4_Immutable_Development_Replay.json"


def source():
    return json.loads(
        SOURCE.read_text(encoding="utf-8")
    )


def test_h5_deterministic():
    analyzer = ImmutableDevelopmentOutcomeAnalysis()
    payload = source()

    first = analyzer.build(payload)
    second = analyzer.build(payload)

    assert first == second


def test_h5_reconciles_h4_exactly():
    result = ImmutableDevelopmentOutcomeAnalysis().build(
        source()
    )

    assert result["source"]["closed_trade_count"] == 2766
    assert result["reconciliation"]["closed_trade_count_matches"] is True
    assert result["reconciliation"]["all_symbols_reconciled"] is True

    for row in result["reconciliation"]["per_symbol"].values():
        assert row["closed_trade_count_difference"] == 0
        assert row["net_pnl_difference"] == 0


def test_h5_governance_remains_development_only():
    result = ImmutableDevelopmentOutcomeAnalysis().build(
        source()
    )

    assert result["source"]["strategy_replay_run"] is False
    assert result["source"]["mt5_accessed"] is False
    assert result["source"]["candles_loaded"] is False
    assert result["source"]["validation_accessed"] is False
    assert result["source"]["external_history_accessed"] is False
    assert result["source"]["true_future_oos_used"] is False

    assert result["production_governance"]["strategy_change_authorized"] is False
    assert result["production_governance"]["symbol_filter_change_authorized"] is False
    assert result["production_governance"]["direction_filter_change_authorized"] is False


def test_h5_all_eight_symbols_have_required_analysis():
    result = ImmutableDevelopmentOutcomeAnalysis().build(
        source()
    )

    expected = {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "XAUUSD",
        "BTCUSD",
        "ETHUSD",
    }

    assert set(result["per_symbol_results"]) == expected

    for row in result["per_symbol_results"].values():
        assert row["ordinary_bootstrap"]["available"] is True
        assert row["moving_block_bootstrap"]["available"] is True
        assert row["temporal_classification"]["classification"] in {
            "STABLE_POSITIVE",
            "STABLE_NEGATIVE",
            "MIXED",
            "INSUFFICIENT",
        }
