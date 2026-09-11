from pathlib import Path

from mss.analysis.fibo_group_rejection_only_fragility_screen import screen_observations

ROOT = Path(__file__).resolve().parents[1]


def test_screen_rejects_gap_and_substitutes_zero_spread_without_outcome_metrics():
    result = screen_observations(
        ROOT,
        [
            {
                "candidate_id": "gap-event",
                "symbol": "EURUSD",
                "observed_spread_points": 0,
                "lookback_crosses_unadjudicated_gap": True,
                "position_carries_across_unadjudicated_gap": False,
            },
            {
                "candidate_id": "ordinary-event",
                "symbol": "BTCUSD",
                "observed_spread_points": 10,
                "lookback_crosses_unadjudicated_gap": False,
                "position_carries_across_unadjudicated_gap": False,
            },
        ],
    )
    gap, ordinary = result["screen_results"]
    assert gap["screen_status"] == "REJECTED"
    assert gap["effective_spread_points"] == 1.0
    assert ordinary["screen_status"] == "NOT_REJECTED_BY_THIS_SCREEN"
    assert result["summary"]["not_rejected_is_not_accepted"] is True
    assert result["outcome_boundary"]["net_profit_metric_emitted"] is False
    assert result["safety"]["order_send_called"] is False
