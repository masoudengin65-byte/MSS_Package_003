import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/MSS_Sprint93_3A_Four_Year_Shared_Capital_Preregistration_V3.json"


def load():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_v3_locks_official_mt5_utc_contract_without_manual_shift():
    data = load()
    timezone = data["data_acquisition"]["timezone_contract"]
    assert timezone["request_datetime_timezone"] == "UTC_AWARE"
    assert timezone["returned_bar_epoch_domain"] == (
        "UTC_PER_OFFICIAL_METATRADER5_API"
    )
    assert timezone["manual_broker_offset_applied"] is False
    assert timezone["local_timezone_conversion_applied"] is False
    assert "timezone_normalization" not in data["data_acquisition"]


def test_v3_preserves_four_year_window_and_no_data_access():
    data = load()
    window = data["core_universe"]["historical_window"]
    assert window["start_utc_inclusive"] == "2021-09-01T00:00:00Z"
    assert window["end_utc_exclusive"] == "2025-09-01T00:00:00Z"
    assert data["supersedes"]["v2_history_downloaded"] is False
    assert data["audit"]["four_year_history_downloaded"] is False
    assert data["audit"]["four_year_replay_run"] is False
