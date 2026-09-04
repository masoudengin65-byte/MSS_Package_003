import json
from pathlib import Path

from mss.analysis.shared_capital_portfolio_preregistration import (
    SharedCapitalPortfolioPreregistration as P,
)


ROOT = Path(__file__).resolve().parents[1]


def test_protocol_locks_primary_account_risk_and_core_universe():
    data = json.loads(
        (ROOT / "reports/MSS_Sprint93_3A_Shared_Capital_Portfolio_Preregistration.json")
        .read_text(encoding="utf-8")
    )
    assert data["core_universe"]["symbols"] == list(P.CORE_SYMBOLS)
    assert data["account_model"]["primary_starting_balance"] == 100.0
    assert data["account_model"]["primary_risk_percent"] == 0.5
    assert data["sensitivity_scenarios"]["risk_percent"] == [0.25, 1.0]
    assert data["account_model"]["independent_symbol_accounts"] is False


def test_protocol_fails_closed_on_minimum_volume_and_extensions():
    data = json.loads(
        (ROOT / "reports/MSS_Sprint93_3A_Shared_Capital_Portfolio_Preregistration.json")
        .read_text(encoding="utf-8")
    )
    contract = data["execution_contract"]
    assert contract["minimum_volume_policy"].startswith("REJECT_IF")
    assert contract["missing_or_invalid_contract_metadata"] == "FAIL_CLOSED"
    assert data["extension_universe"]["status"].startswith("CONDITIONAL")
    assert data["audit"]["shared_capital_replay_run"] is False
    assert data["audit"]["live_mt5_accessed"] is False
    assert data["audit"]["active_sprint93_2b_forward_modified"] is False
