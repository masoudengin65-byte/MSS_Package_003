"""Preregister a cross-source price comparison without replacing broker evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_preregistration(root: Path) -> dict[str, object]:
    reports = root / "reports"
    gate_path = reports / "MSS_Sprint93_3B_Historical_Execution_Evidence_Gate_V1.json"
    quality_path = reports / "MSS_Sprint93_3A_Data_Quality_V1.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if gate["net_profit_replay"]["eligible"]:
        raise ValueError("Independent comparison must not start from a cleared execution gate")
    return {
        "schema_version": "MSS_SPRINT93_3D_INDEPENDENT_PRICE_COMPARISON_PREREGISTRATION_V1",
        "purpose": "Cross-validate frozen MT5 price and timestamp patterns with a separate source",
        "source_provenance": {
            "execution_evidence_gate_sha256": sha256(gate_path),
            "data_quality_report_sha256": sha256(quality_path),
            "timeframe": quality["window"]["timeframe"],
            "frozen_broker_symbols": [item["symbol"] for item in quality["symbols"]],
        },
        "candidate_source": {
            "name": "WINDSOR_MT5_DEMO_CANDIDATE",
            "selected": False,
            "selection_requirements": [
                "Exact Windsor MT5 server and demo account type recorded before acquisition",
                "Symbol mapping is recorded without silently substituting instruments",
                "Source terms permit the intended local research use",
                "No order_check, order_send or live-account login is used",
            ],
        },
        "comparison_contract": {
            "timezone": "UTC",
            "bar_interval": "M15",
            "fields": ["time", "open", "high", "low", "close"],
            "metrics": [
                "matched_timestamp_coverage",
                "open_and_close_return_difference_quantiles",
                "high_low_range_difference_quantiles",
                "gap_start_and_gap_end_agreement",
                "unmatched_timestamp_count",
            ],
            "no_interpolation": True,
            "no_resampling_across_market_closures": True,
        },
        "interpretation_boundary": {
            "expected_differences": [
                "CFD versus spot or exchange price",
                "broker session and timezone conventions",
                "bid ask construction",
                "instrument contract differences",
            ],
            "allowed_conclusion": "A stated price-pattern consistency or discrepancy finding",
            "cannot_establish": [
                "historical Alpari trading sessions",
                "historical Alpari commission or swap",
                "historical Alpari execution quality",
                "broker-accurate net profit",
                "production readiness",
            ],
        },
        "safety": {
            "raw_data_modified": False,
            "candidate_data_acquired": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
        "next_action": "Record the Windsor server and exact symbol mapping, then publish a source-specific acquisition manifest before collecting bars",
    }
