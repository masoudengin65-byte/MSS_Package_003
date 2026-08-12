import json
from pathlib import Path

from mss.analysis.usdjpy_stability_falsification import UsdJpyStabilityFalsification


def trade(index, month, profit, direction="BUY"):
    return {"trade_id": index, "direction": direction, "entry_time": f"{month}-01T00:00:00",
            "exit_time": f"{month}-01T00:15:00", "month": month,
            "profit": float(profit), "r_multiple": float(profit / 100)}


def test_monthly_and_direction_reconcile_to_overall():
    rows = [trade(1, "2026-01", 10, "BUY"), trade(2, "2026-01", -5, "SELL"), trade(3, "2026-02", 20, "SELL")]
    result = UsdJpyStabilityFalsification.segment_audit(rows)
    assert sum(row["net_pnl"] for row in result["monthly"]) == result["overall"]["net_pnl"] == 25
    assert sum(row["net_pnl"] for row in result["directions"].values()) == 25


def test_leave_one_month_out_is_deterministic_and_complete():
    rows = [trade(1, "2026-01", 10), trade(2, "2026-02", 20), trade(3, "2026-03", -5)]
    result = UsdJpyStabilityFalsification.leave_one_month_out(list(reversed(rows)))
    assert [row["excluded_month"] for row in result] == ["2026-01", "2026-02", "2026-03"]
    assert [row["net_pnl"] for row in result] == [15, 5, 30]


def test_concentration_detects_profit_dependency():
    rows = [trade(1, "2026-01", 100), trade(2, "2026-02", -40), trade(3, "2026-03", -30)]
    result = UsdJpyStabilityFalsification.segment_audit(rows)
    assert result["concentration"]["best_month_share_of_total_net"] > 1
    assert result["predefined_falsification_checks"]["best_month_not_more_than_total_net"] is False
    assert result["survives_all_predefined_checks"] is False


def test_completed_artifact_reconciles_and_keeps_oos_sealed():
    path = Path(__file__).resolve().parents[1] / "reports" / "MSS_Sprint92C5_USDJPY_Stability_Falsification.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == UsdJpyStabilityFalsification.VERSION
    assert data["validation"] == {
        "all_source_trades_reconciled": True, "deterministic_rebuild": True,
        "research_exposed_used": False, "strategy_replay_run": False, "true_oos_used": False,
    }
    assert data["segment_results"]["DEVELOPMENT"]["survives_all_predefined_checks"] is True
    assert data["segment_results"]["VALIDATION"]["survives_all_predefined_checks"] is False
    assert data["final_assessment"] == "FAILS_ONE_OR_MORE_STABILITY_CHECKS"
    assert data["production_change_justified"] is False
