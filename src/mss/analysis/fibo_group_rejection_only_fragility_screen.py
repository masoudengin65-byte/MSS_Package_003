"""Reject unsafe candidate observations without producing a trading outcome."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

PREREGISTRATION_NAME = (
    "MSS_Sprint93_3F_FIBO_Group_Fragility_Screen_Preregistration_V1.json"
)
ALLOWED_SYMBOLS = frozenset({"EURUSD", "XAUUSD", "BTCUSD", "ETHUSD"})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline_by_frozen_symbol(root: Path) -> tuple[dict[str, float], str]:
    path = root / "reports" / PREREGISTRATION_NAME
    preregistration = json.loads(path.read_text(encoding="utf-8"))
    if preregistration["outcome_boundary"]["historical_net_profit_replay_eligible"]:
        raise ValueError("A rejection-only screen cannot use replay-eligible evidence")
    return (
        {
            row["frozen_broker_symbol"]: row["baseline_replacement_spread_points"]
            for row in preregistration["rules"]
        },
        _sha256(path),
    )


def screen_observations(
    root: Path, observations: Iterable[Mapping[str, object]]
) -> dict[str, object]:
    """Classify observations as rejected or inconclusive, never accepted."""
    baselines, preregistration_sha256 = _baseline_by_frozen_symbol(root)
    results: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for observation in observations:
        candidate_id = observation.get("candidate_id")
        symbol = observation.get("symbol")
        spread = observation.get("observed_spread_points")
        crosses_gap = observation.get("lookback_crosses_unadjudicated_gap")
        carries_gap = observation.get("position_carries_across_unadjudicated_gap")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or candidate_id in seen_ids
        ):
            raise ValueError("candidate_id must be unique and non-empty")
        if symbol not in ALLOWED_SYMBOLS:
            raise ValueError("observation symbol is outside the frozen FIBO scope")
        if (
            not isinstance(spread, (int, float))
            or isinstance(spread, bool)
            or spread < 0
        ):
            raise ValueError("observed_spread_points must be a non-negative number")
        if not isinstance(crosses_gap, bool) or not isinstance(carries_gap, bool):
            raise ValueError("gap flags must be explicit booleans")
        seen_ids.add(candidate_id)
        effective_spread = baselines[symbol] if spread == 0 else spread
        reasons = []
        if crosses_gap:
            reasons.append("LOOKBACK_CROSSES_UNADJUDICATED_GAP")
        if carries_gap:
            reasons.append("POSITION_CARRIES_ACROSS_UNADJUDICATED_GAP")
        results.append(
            {
                "candidate_id": candidate_id,
                "symbol": symbol,
                "observed_spread_points": spread,
                "effective_spread_points": effective_spread,
                "zero_spread_substituted": spread == 0,
                "screen_status": (
                    "REJECTED" if reasons else "NOT_REJECTED_BY_THIS_SCREEN"
                ),
                "rejection_reasons": reasons,
            }
        )
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_REJECTION_ONLY_FRAGILITY_SCREEN_V1",
        "purpose": "Reject observations violating frozen gap treatment without calculating strategy outcomes",
        "provenance": {"preregistration_sha256": preregistration_sha256},
        "screen_results": results,
        "summary": {
            "observation_count": len(results),
            "rejected_count": sum(
                item["screen_status"] == "REJECTED" for item in results
            ),
            "not_rejected_is_not_accepted": True,
        },
        "outcome_boundary": {
            "net_profit_metric_emitted": False,
            "return_metric_emitted": False,
            "drawdown_metric_emitted": False,
            "acceptance_decision_emitted": False,
            "production_readiness_claim_allowed": False,
        },
        "safety": {
            "raw_data_modified": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
