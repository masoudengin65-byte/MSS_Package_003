"""Create a publishable aggregate without exporting strategy observations."""

from __future__ import annotations

from collections.abc import Mapping


def build_summary(
    observation_stream: Mapping[str, object], rejection_screen: Mapping[str, object]
) -> dict[str, object]:
    observation_count = observation_stream["summary"]["observation_count"]
    screen_summary = rejection_screen["summary"]
    if observation_count != screen_summary["observation_count"]:
        raise ValueError("screen summary does not match the local observation count")
    if rejection_screen["outcome_boundary"]["net_profit_metric_emitted"]:
        raise ValueError(
            "financial outcome metrics are not publishable in this summary"
        )
    if rejection_screen["safety"]["order_send_called"]:
        raise ValueError("a publishable summary requires no order sending")
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_SIGNAL_SCREEN_PUBLICATION_SUMMARY_V1",
        "purpose": "Publish aggregate rejection-screen evidence without strategy observation rows",
        "scope": "IMMUTABLE_DEVELOPMENT_ONLY_NOT_TRUE_FUTURE_OOS",
        "aggregate_counts": {
            "observation_count": observation_count,
            "rejected_count": screen_summary["rejected_count"],
            "not_rejected_by_this_screen_count": observation_count
            - screen_summary["rejected_count"],
        },
        "interpretation_boundary": {
            "not_rejected_by_this_screen_is_strategy_acceptance": False,
            "historical_profitability_claim_allowed": False,
            "production_readiness_claim_allowed": False,
        },
        "publication_boundary": {
            "candidate_rows_included": False,
            "candidate_identifiers_included": False,
            "timestamps_included": False,
            "directions_included": False,
            "spreads_included": False,
            "source_hashes_included": False,
        },
        "safety": {
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
