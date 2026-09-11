from pathlib import Path

from mss.analysis.fibo_group_comparison_quality_gate import build_quality_gate


def test_quality_gate_keeps_historical_net_profit_replay_closed():
    root = Path(__file__).resolve().parents[1]
    result = build_quality_gate(root)
    assert result["price_pattern_analysis_eligible"] is True
    assert result["historical_net_profit_replay_eligible"] is False
    assert all(item["price_pattern_analysis_usable"] for item in result["symbols"])
    assert result["safety"]["order_send_called"] is False
