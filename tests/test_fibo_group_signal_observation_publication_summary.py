from mss.analysis.fibo_group_signal_observation_publication_summary import build_summary


def test_summary_excludes_sensitive_observation_details():
    result = build_summary(
        {"summary": {"observation_count": 8}},
        {
            "summary": {"observation_count": 8, "rejected_count": 6},
            "outcome_boundary": {"net_profit_metric_emitted": False},
            "safety": {"order_send_called": False},
        },
    )
    assert result["aggregate_counts"]["not_rejected_by_this_screen_count"] == 2
    assert result["publication_boundary"]["candidate_rows_included"] is False
    assert result["publication_boundary"]["timestamps_included"] is False
    assert (
        result["interpretation_boundary"]["historical_profitability_claim_allowed"]
        is False
    )
