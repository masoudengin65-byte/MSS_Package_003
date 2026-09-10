import json
from pathlib import Path

from mss.analysis.independent_price_comparison_preregistration import build_preregistration


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "MSS_Sprint93_3D_Independent_Price_Comparison_Preregistration_V1.json"


def test_preregistration_is_deterministic_and_windsor_is_only_a_candidate():
    result = build_preregistration(ROOT)
    assert result == build_preregistration(ROOT)
    assert result["candidate_source"]["name"] == "WINDSOR_MT5_DEMO_CANDIDATE"
    assert result["candidate_source"]["selected"] is False


def test_published_boundary_cannot_clear_execution_evidence_or_send_orders():
    result = json.loads(REPORT.read_text(encoding="utf-8"))
    assert result["comparison_contract"]["no_interpolation"] is True
    assert "broker-accurate net profit" in result["interpretation_boundary"]["cannot_establish"]
    assert result["safety"]["candidate_data_acquired"] is False
    assert result["safety"]["order_check_called"] is False
    assert result["safety"]["order_send_called"] is False
