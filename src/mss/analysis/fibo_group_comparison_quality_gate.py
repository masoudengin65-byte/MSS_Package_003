"""Classify FIBO comparison evidence without clearing the execution-evidence gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

COMPARISON_NAME = "MSS_Sprint93_3F_FIBO_Group_Price_Pattern_Comparison_V1.json"
EXECUTION_GATE_NAME = "MSS_Sprint93_3B_Historical_Execution_Evidence_Gate_V1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_quality_gate(root: Path) -> dict[str, object]:
    reports = root / "reports"
    comparison_path = reports / COMPARISON_NAME
    execution_gate_path = reports / EXECUTION_GATE_NAME
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    execution_gate = json.loads(execution_gate_path.read_text(encoding="utf-8"))
    if comparison["safety"]["strategy_or_replay_run"]:
        raise ValueError(
            "Price-pattern comparison must not contain a strategy or replay result"
        )
    if (
        comparison["safety"]["order_check_called"]
        or comparison["safety"]["order_send_called"]
    ):
        raise ValueError("Price-pattern comparison must remain order-free")
    if execution_gate["net_profit_replay"]["eligible"]:
        raise ValueError(
            "This gate is valid only while historical execution evidence remains unavailable"
        )
    symbols = []
    for row in comparison["symbols"]:
        coverage = float(row["matched_timestamp_coverage"])
        return_rows = int(row["return_comparison_timestamp_count"])
        symbols.append(
            {
                "frozen_broker_symbol": row["frozen_broker_symbol"],
                "fibo_group_symbol": row["fibo_group_symbol"],
                "matched_timestamp_coverage": coverage,
                "return_comparison_timestamp_count": return_rows,
                "unmatched_frozen_timestamp_count": row[
                    "unmatched_frozen_timestamp_count"
                ],
                "unmatched_fibo_timestamp_count": row["unmatched_fibo_timestamp_count"],
                "gap_boundary_agreement_coverage": row[
                    "gap_boundary_agreement_coverage"
                ],
                "price_pattern_analysis_usable": coverage >= 0.995 and return_rows > 0,
                "gap_interpretation": "SOURCE_SESSION_DIFFERENCES_NOT_EXECUTION_EVIDENCE",
            }
        )
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_COMPARISON_QUALITY_GATE_V1",
        "purpose": "Classify cross-source price-pattern evidence without inferring trading execution or profit",
        "provenance": {
            "price_pattern_comparison_sha256": _sha256(comparison_path),
            "historical_execution_evidence_gate_sha256": _sha256(execution_gate_path),
        },
        "acceptance_contract": {
            "minimum_matched_timestamp_coverage": 0.995,
            "minimum_return_comparison_timestamp_count": 1,
            "gap_boundary_agreement_is_not_an_acceptance_threshold": True,
            "reason": "Different broker session conventions cannot establish historical execution quality",
        },
        "symbols": symbols,
        "price_pattern_analysis_eligible": all(
            row["price_pattern_analysis_usable"] for row in symbols
        ),
        "historical_net_profit_replay_eligible": False,
        "blockers_retained": execution_gate["net_profit_replay"]["prohibited_claims"],
        "next_authorized_action": "Obtain documented historical broker execution evidence; do not run a net-profit replay",
        "safety": {
            "raw_data_modified": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
