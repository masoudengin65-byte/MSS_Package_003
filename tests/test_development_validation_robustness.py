import json
from pathlib import Path

from mss.analysis.development_validation_robustness import DevelopmentValidationRobustness


def result(point, lower, upper):
    metric = {"ci_95": {"lower": lower, "upper": upper}}
    return {"available": True, "point_estimates": {"expectancy_account_currency": point},
            "bootstrap_metrics": {"expectancy": metric, "mean_r": metric}}


def test_robust_positive_requires_both_methods_and_both_segments():
    positive = result(1, .1, 2)
    crossing = result(1, -.1, 2)
    classify = DevelopmentValidationRobustness.classify
    assert classify(positive, positive, positive, positive) == "ROBUST_POSITIVE"
    assert classify(positive, positive, positive, crossing) == "PROMISING_NOT_CONFIRMED"


def test_positive_points_without_positive_intervals_are_not_confirmed():
    crossing = result(1, -1, 2)
    assert DevelopmentValidationRobustness.classify(crossing, crossing, crossing, crossing) == "PROMISING_NOT_CONFIRMED"


def test_mixed_sign_segments_are_not_reliable():
    positive = result(1, .1, 2)
    negative = result(-1, -2, -.1)
    assert DevelopmentValidationRobustness.classify(positive, negative, positive, negative) == "NOT_RELIABLE"


def test_robust_negative_requires_all_four_checks():
    negative = result(-1, -2, -.1)
    assert DevelopmentValidationRobustness.classify(negative, negative, negative, negative) == "ROBUST_NEGATIVE"


def test_completed_artifact_reconciles_and_preserves_oos_quarantine():
    path = Path(__file__).resolve().parents[1] / "reports" / "MSS_Sprint92C4_Development_Validation_Robustness.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == DevelopmentValidationRobustness.VERSION
    assert data["source"]["development_closed_trades"] == 2747
    assert data["source"]["validation_closed_trades"] == 868
    assert data["source"]["strategy_replay_run"] is False
    assert data["source"]["true_oos_candles_used"] == 0
    assert data["source"]["research_exposed_candles_used"] == 0
    assert data["validation"] == {
        "all_trade_counts_and_pnl_reconcile": True,
        "deterministic_rebuild": True,
        "research_exposed_used": False,
        "strategy_replay_run": False,
        "true_oos_used": False,
    }
    assert data["final_classifications"]["USDJPY"] == "PROMISING_NOT_CONFIRMED"
    assert not any(value == "ROBUST_POSITIVE" for value in data["final_classifications"].values())
