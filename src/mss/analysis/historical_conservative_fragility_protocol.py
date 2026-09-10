"""Preregister a conservative research screen without claiming broker accuracy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_protocol(root: Path) -> dict[str, object]:
    reports = root / "reports"
    gate_path = reports / "MSS_Sprint93_3B_Historical_Execution_Evidence_Gate_V1.json"
    quality_path = reports / "MSS_Sprint93_3A_Data_Quality_V1.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if gate["net_profit_replay"]["eligible"]:
        raise ValueError("This protocol is only valid while broker-accurate replay is gated")
    if not quality["all_integrity_checks_pass"]:
        raise ValueError("Frozen raw data did not pass integrity checks")
    return {
        "schema_version": "MSS_SPRINT93_3C_CONSERVATIVE_FRAGILITY_PROTOCOL_V1",
        "purpose": "Reject strategy candidates that cannot survive preregistered conservative assumptions",
        "source_provenance": {
            "execution_evidence_gate_sha256": file_sha256(gate_path),
            "data_quality_report_sha256": file_sha256(quality_path),
            "window": quality["window"],
            "symbols": [item["symbol"] for item in quality["symbols"]],
        },
        "research_boundary": {
            "broker_accurate_net_profit_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "allowed_conclusion": "Candidate rejected as cost-fragile under declared hypothetical scenarios",
            "forbidden_conclusion": "Candidate approved for broker-accurate profitability or live execution",
        },
        "prereplay_requirements": [
            "Independent price source comparison protocol is frozen before outcome access",
            "Every zero-spread row receives a documented conservative substitution rule",
            "Unadjudicated gaps receive a documented no-trade or exclusion rule",
            "Each scenario states spread, commission, swap and slippage assumptions with source or hypothetical label",
            "Scenario parameters and evaluation metrics are frozen before strategy outcome access",
        ],
        "scenario_rules": {
            "minimum_scenarios": 3,
            "ordering": "baseline_less_conservative_to_most_conservative",
            "cost_components": ["spread", "commission", "swap", "slippage"],
            "prohibition": "No scenario parameter may be described as historical Alpari fact without documentary evidence",
            "acceptance_rule": "No acceptance decision is permitted; only a documented rejection for fragility is permitted",
        },
        "audit": {
            "raw_data_modified": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
        "next_actions": [
            "Send the broker clarification follow-up draft",
            "Preregister independent-price comparison and conservative scenario values",
            "Run a future rejection-only fragility screen after prereplay requirements are met",
        ],
    }
