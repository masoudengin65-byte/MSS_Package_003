import json
from pathlib import Path

from mss.analysis.extended_development_validation_replay import ExtendedDevelopmentValidationReplay


def row(symbol, net):
    return {"canonical_symbol": symbol, "closed_trades": 10, "net_profit": net,
            "profit_factor": 1.2 if net > 0 else .8, "expectancy": net / 10, "average_r": net / 1000}


def test_comparison_keeps_segments_separate_and_reports_consistency():
    development = {"per_symbol_results": [row("EURUSD", 100), row("XAUUSD", -50)]}
    validation = {"per_symbol_results": [row("EURUSD", 25), row("XAUUSD", 20)]}
    result = ExtendedDevelopmentValidationReplay.comparison(development, validation)
    assert result[0]["positive_in_both"] is True
    assert result[0]["directionally_consistent"] is True
    assert result[1]["positive_in_both"] is False
    assert result[1]["directionally_consistent"] is False


def test_segment_constants_exclude_quarantine_and_oos():
    assert ExtendedDevelopmentValidationReplay.SEGMENTS == ("DEVELOPMENT", "VALIDATION")


def test_completed_artifact_enforces_frozen_boundaries_and_reconciles():
    path = Path(__file__).resolve().parents[1] / "reports" / "MSS_Sprint92C3_Extended_Development_Validation_Replay.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == ExtendedDevelopmentValidationReplay.VERSION
    assert data["source"]["research_exposed_candles_used"] == 0
    assert data["source"]["true_oos_candles_used"] == 0
    assert data["audit"]["deterministic_artifact_rebuild"] is True
    assert data["acceptance"] == {
        "all_eight_development_segments_replayed": True,
        "all_eight_validation_segments_replayed": True,
        "full_50000_hashes_match_manifest": True,
        "real_orders_sent": False,
        "research_exposed_candles_used": False,
        "strategy_behavior_unchanged": True,
        "true_oos_candles_used": False,
    }
    for segment, expected in (("DEVELOPMENT", 30_000), ("VALIDATION", 10_000)):
        summary = data["segments"][segment]
        assert len(summary["per_symbol_results"]) == 8
        assert all(row["source_candles"] == expected for row in summary["per_symbol_results"])
        combined = summary["combined_independent_results"]
        assert combined["starting_balance"] == 80_000.0
        assert sum(row["closed_trades"] for row in summary["per_symbol_results"]) == combined["closed_trades"]
