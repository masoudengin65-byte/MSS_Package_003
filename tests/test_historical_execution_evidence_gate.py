import json
from pathlib import Path

from mss.analysis.historical_execution_evidence_gate import REQUIRED_EVIDENCE, build_gate


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "MSS_Sprint93_3B_Historical_Execution_Evidence_Gate_V1.json"


def test_gate_is_deterministic_and_net_replay_is_blocked():
    gate = build_gate(ROOT)
    assert gate == build_gate(ROOT)
    assert gate["net_profit_replay"]["eligible"] is False
    assert gate["evidence_status"] == REQUIRED_EVIDENCE


def test_published_gate_preserves_safety_and_independent_source_boundary():
    gate = json.loads(REPORT.read_text(encoding="utf-8"))
    assert gate["safety"]["order_send_called"] is False
    assert gate["safety"]["real_order_send_allowed"] is False
    assert "net_profit_replay" in gate["independent_price_source"]["cannot_clear"]
    assert gate["next_authorized_action"]["external_message_sent"] is False
