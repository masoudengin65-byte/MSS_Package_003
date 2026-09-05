import json
from pathlib import Path

from mss.analysis.shared_capital_portfolio_preregistration_v2 import (
    SharedCapitalPortfolioPreregistrationV2 as P,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/MSS_Sprint93_3A_Four_Year_Shared_Capital_Preregistration_V2.json"


def load():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_v2_locks_exact_four_year_common_window_and_annual_blocks():
    data = load()
    window = data["core_universe"]["historical_window"]
    assert window["start_utc_inclusive"] == P.WINDOW_START_UTC
    assert window["end_utc_exclusive"] == P.WINDOW_END_EXCLUSIVE_UTC
    assert window["calendar_years"] == 4
    assert len(window["annual_reporting_blocks"]) == 4
    assert window["common_window_required_for_all_core_symbols"] is True
    assert window["warmup_candles_before_window"] == 500
    assert window["warmup_excluded_from_performance"] is True


def test_v2_preserves_account_risk_and_fail_closed_data_rules():
    data = load()
    assert data["account_model"]["primary_starting_balance"] == 100.0
    assert data["account_model"]["primary_risk_percent"] == 0.5
    assert data["sensitivity_scenarios"]["risk_percent"] == [0.25, 1.0]
    assert data["data_acquisition"]["insufficient_common_window_policy"].startswith("FAIL")
    assert data["execution_policy"]["window_shortening_after_data_access"] is False
    assert data["validation_design"]["classification"] == (
        "HISTORICAL_ROBUSTNESS_NOT_TRUE_FUTURE_OOS"
    )


def test_v2_was_created_without_history_or_forward_access():
    audit = load()["audit"]
    assert audit["four_year_history_downloaded"] is False
    assert audit["four_year_prices_inspected"] is False
    assert audit["four_year_replay_run"] is False
    assert audit["sprint93_2b_forward_accessed_or_modified"] is False
