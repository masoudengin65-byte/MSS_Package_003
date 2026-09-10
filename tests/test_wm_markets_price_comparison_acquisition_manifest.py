import json
from pathlib import Path

from mss.analysis.wm_markets_price_comparison_acquisition_manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "MSS_Sprint93_3E_WM_Markets_Price_Comparison_Acquisition_Manifest_V1.json"


def test_manifest_is_deterministic_and_maps_only_observed_symbols():
    result = build_manifest(ROOT)
    assert result == build_manifest(ROOT)
    assert result["source"]["mt5_server"] == "WMMMarkets-Demo"
    assert [(item["frozen_broker_symbol"], item["wm_markets_symbol"]) for item in result["symbol_mappings"]] == [
        ("EURUSD", "EURUSD"),
        ("XAUUSD", "XAUUSD"),
        ("BTCUSD", "BTCUSD"),
        ("ETHUSD", "ETHUSD"),
    ]


def test_manifest_blocks_acquisition_until_terms_are_recorded_and_forbids_orders():
    result = json.loads(REPORT.read_text(encoding="utf-8"))
    assert result["pre_acquisition_gates"]["all_required_gates_pass"] is False
    assert result["source"]["live_account_login_allowed"] is False
    assert result["acquisition_contract"]["forbidden_mt5_calls"] == ["order_check", "order_send"]
    assert result["safety"]["order_check_called"] is False
    assert result["safety"]["order_send_called"] is False
