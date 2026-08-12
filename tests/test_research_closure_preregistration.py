import json
from pathlib import Path

from mss.analysis.research_closure_preregistration import ResearchClosurePreregistration


def sources():
    combined = {"closed_trades": 1, "net_profit": -1, "return_percent": -1, "profit_factor": .9}
    return {
        "c1": {"schema_version": "c1"}, "c2": {"schema_version": "c2"},
        "c3": {"schema_version": "c3", "segments": {
            "DEVELOPMENT": {"combined_independent_results": combined},
            "VALIDATION": {"combined_independent_results": combined},
        }},
        "c4": {"schema_version": "c4", "final_classifications": {
            symbol: "PROMISING_NOT_CONFIRMED" if symbol == "USDJPY" else "NOT_RELIABLE"
            for symbol in ResearchClosurePreregistration.SYMBOLS
        }},
        "c5": {"schema_version": "c5", "final_assessment": "FAILS_ONE_OR_MORE_STABILITY_CHECKS"},
    }


def test_preregistration_is_deterministic_and_oos_uninspected():
    builder = ResearchClosurePreregistration()
    first, second = builder.build(sources()), builder.build(sources())
    assert first == second
    assert first["audit"]["true_oos_eligibility_checked"] is False
    assert first["audit"]["true_oos_outcomes_analyzed"] is False


def test_gate_requires_all_eight_symbols_and_10000_candles():
    result = ResearchClosurePreregistration().build(sources())
    gate = result["true_oos_preregistration"]["accrual_gate"]
    assert gate["minimum_completed_m15_candles_per_symbol"] == 10_000
    assert gate["required_symbols"] == list(ResearchClosurePreregistration.SYMBOLS)
    assert gate["interim_peeking"] == "PROHIBITED"


def test_usdjpy_is_only_confirmatory_hypothesis_and_failure_means_no_change():
    protocol = ResearchClosurePreregistration().build(sources())["true_oos_preregistration"]
    assert protocol["primary_hypothesis"]["symbol"] == "USDJPY"
    assert protocol["primary_hypothesis"]["minimum_closed_trades"] == 100
    assert protocol["primary_hypothesis"]["decision_if_any_fail"] == "NOT_CONFIRMED_NO_PRODUCTION_CHANGE"
    assert "USDJPY" not in protocol["secondary_symbols"]["symbols"]
    assert protocol["secondary_symbols"]["production_claims_allowed"] is False


def test_completed_artifact_closes_research_without_oos_inspection():
    path = Path(__file__).resolve().parents[1] / "reports" / "MSS_Sprint92C6_Research_Closure_True_OOS_Preregistration.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == ResearchClosurePreregistration.VERSION
    assert data["sprint_92c_closure"]["scientific_conclusion"] == "NO_SYMBOL_HAS_CONFIRMED_ROBUST_POSITIVE_EVIDENCE"
    assert data["sprint_92c_closure"]["production_decision"] == "NO_STRATEGY_OR_SYMBOL_FILTER_CHANGE"
    assert data["audit"]["deterministic_rebuild"] is True
    assert data["audit"]["true_oos_eligibility_checked"] is False
    assert data["audit"]["true_oos_outcomes_analyzed"] is False
    assert all(value is True or key == "production_change_justified" and value is False
               for key, value in data["acceptance"].items())
