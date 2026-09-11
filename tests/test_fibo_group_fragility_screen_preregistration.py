from pathlib import Path

from mss.analysis.fibo_group_fragility_screen_preregistration import (
    build_preregistration,
)


def test_preregistration_freezes_gap_and_zero_spread_rules():
    result = build_preregistration(Path(__file__).resolve().parents[1])
    assert len(result["rules"]) == 4
    assert all("NO_ENTRY" in row["gap_rule"] for row in result["rules"])
    assert all(row["baseline_replacement_spread_points"] > 0 for row in result["rules"])
    assert result["outcome_boundary"]["strategy_or_replay_run"] is False
    assert result["safety"]["order_send_called"] is False
