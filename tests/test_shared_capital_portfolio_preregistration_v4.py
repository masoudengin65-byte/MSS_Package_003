import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/MSS_Sprint93_3A_Availability_Preregistration_V4.json"


def test_v4_uses_first_full_common_day_after_crypto_availability_limit():
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    window = data["core_universe"]["historical_window"]
    assert data["schema_version"] == "MSS_SPRINT93_3A_SHARED_CAPITAL_PORTFOLIO_PREREGISTRATION_V4"
    assert window["start_utc_inclusive"] == "2021-09-17T00:00:00Z"
    assert window["availability_basis"]["crypto_first_available_m15_utc"] == "2021-09-16T13:30:00Z"
    assert data["supersedes"]["authoritative_raw_dataset_written"] is False
    assert data["audit"]["outcomes_or_strategy_metrics_inspected"] is False
