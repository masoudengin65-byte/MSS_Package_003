import json
from pathlib import Path

from mss.analysis.fibo_group_price_comparison_acquisition_manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Price_Comparison_Acquisition_Manifest_V1.json"


def test_manifest_is_deterministic_and_maps_fibo_crypto_symbols():
    result = build_manifest(ROOT)
    assert result == build_manifest(ROOT)
    assert result["source"]["mt5_server"] == "FIBOGroup-MT5 Server"
    assert result["symbol_mappings"][-2:] == [
        {"frozen_broker_symbol": "BTCUSD", "fibo_group_symbol": "BTC"},
        {"frozen_broker_symbol": "ETHUSD", "fibo_group_symbol": "ETH"},
    ]


def test_published_manifest_allows_only_read_only_acquisition_and_blocks_order_paths():
    result = json.loads(REPORT.read_text(encoding="utf-8"))
    assert result["pre_acquisition_gates"]["all_required_gates_pass"] is True
    assert result["source"]["terms_of_use_verified"] is True
    assert "MetaTrader5 Python package" in result["source"]["terms_evidence"]["scope_limit"]
    assert result["safety"]["candidate_data_acquired"] is False
    assert result["safety"]["order_check_called"] is False
    assert result["safety"]["order_send_called"] is False
