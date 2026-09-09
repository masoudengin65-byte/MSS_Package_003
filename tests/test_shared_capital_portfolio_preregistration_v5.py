import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/MSS_Sprint93_3A_Availability_Preregistration_V5.json"


def test_v5_preserves_v4_partial_raw_files_and_moves_to_xauusd_common_start():
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    window = data["core_universe"]["historical_window"]
    assert data["schema_version"] == "MSS_SPRINT93_3A_SHARED_CAPITAL_PORTFOLIO_PREREGISTRATION_V5"
    assert window["start_utc_inclusive"] == "2021-09-23T18:30:00Z"
    assert data["supersedes"]["v4_partial_raw_files_preserved"] is True
    assert data["supersedes"]["v4_partial_raw_files_eligible_for_analysis"] is False
    assert data["audit"]["v4_authoritative_manifest_written"] is False


def test_published_protocol_matches_freezer_and_reporting_blocks():
    from datetime import datetime
    from mss.analysis.four_year_mt5_dataset_freeze import FourYearMT5DatasetFreeze as F
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    window = data["core_universe"]["historical_window"]
    assert int(datetime.fromisoformat(window["start_utc_inclusive"].replace("Z", "+00:00")).timestamp()) == F.WINDOW_START_EPOCH
    blocks = window["annual_reporting_blocks"]
    assert blocks[0]["start_utc_inclusive"] == window["start_utc_inclusive"]
    assert blocks[-1]["end_utc_exclusive"] == window["end_utc_exclusive"]
    assert all(a["end_utc_exclusive"] == b["start_utc_inclusive"] for a, b in zip(blocks, blocks[1:]))
    assert window["warmup_candles_before_window"] == F.WARMUP_CANDLES == 500
