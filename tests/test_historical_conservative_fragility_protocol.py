import json
from pathlib import Path

from mss.analysis.historical_conservative_fragility_protocol import build_protocol


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "MSS_Sprint93_3C_Conservative_Fragility_Protocol_V1.json"


def test_protocol_is_deterministic_and_not_a_live_approval_route():
    protocol = build_protocol(ROOT)
    assert protocol == build_protocol(ROOT)
    assert protocol["research_boundary"]["broker_accurate_net_profit_claim_allowed"] is False
    assert protocol["research_boundary"]["production_readiness_claim_allowed"] is False
    assert protocol["scenario_rules"]["acceptance_rule"].startswith("No acceptance")


def test_published_protocol_preserves_prereplay_and_order_safety():
    protocol = json.loads(REPORT.read_text(encoding="utf-8"))
    assert len(protocol["prereplay_requirements"]) == 5
    assert protocol["scenario_rules"]["minimum_scenarios"] == 3
    assert protocol["audit"]["strategy_or_replay_run"] is False
    assert protocol["audit"]["order_check_called"] is False
    assert protocol["audit"]["order_send_called"] is False
