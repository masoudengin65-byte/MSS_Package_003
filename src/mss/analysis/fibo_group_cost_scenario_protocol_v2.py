"""Attach current public commission references to the research-only FIBO scenarios."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

V1_NAME = "MSS_Sprint93_3F_FIBO_Group_Cost_Scenario_Protocol_V1.json"
COMMISSION_NAME = (
    "MSS_Sprint93_3F_FIBO_Group_Current_Public_Commission_Evidence_V1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_protocol(root: Path) -> dict[str, object]:
    reports = root / "reports"
    v1_path = reports / V1_NAME
    commission_path = reports / COMMISSION_NAME
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    commission = json.loads(commission_path.read_text(encoding="utf-8"))
    if v1["research_boundary"]["historical_net_profit_replay_eligible"]:
        raise ValueError("V2 only extends research-only scenarios")
    references = {
        item["symbol"]: item
        for item in commission["current_public_commission_reference"]
    }
    scenarios = []
    for scenario, multiplier in zip(v1["scenarios"], (1.0, 1.5, 2.0), strict=True):
        inputs = []
        for item in scenario["inputs"]:
            reference = references[item["symbol"]]
            enriched = {
                **item,
                "commission_reference_model": reference["model"],
                "commission_stress_multiplier": multiplier,
            }
            if reference["model"] == "PER_LOT":
                enriched["commission_amount_per_lot"] = reference["amount"] * multiplier
                enriched["commission_currency"] = reference["currency"]
            else:
                enriched["commission_rate_percent_notional"] = (
                    reference["rate_percent"] * multiplier
                )
                if "minimum_amount" in reference:
                    enriched["commission_minimum_amount"] = (
                        reference["minimum_amount"] * multiplier
                    )
                    enriched["commission_minimum_currency"] = reference[
                        "minimum_currency"
                    ]
            inputs.append(enriched)
        scenarios.append({"name": scenario["name"], "inputs": inputs})
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_COST_SCENARIO_PROTOCOL_V2",
        "purpose": "Current-reference cost scenarios with labelled commission inputs for rejection-only research",
        "provenance": {
            "v1_protocol_sha256": _sha256(v1_path),
            "current_public_commission_sha256": _sha256(commission_path),
        },
        "scenarios": scenarios,
        "research_boundary": {
            "current_terms_are_historical_terms": False,
            "unit_conversion_or_aggregation_performed": False,
            "historical_net_profit_replay_eligible": False,
            "allowed_conclusion": "A candidate may be rejected under declared hypothetical costs only",
            "forbidden_conclusions": [
                "broker-accurate historical net profit",
                "historical execution quality",
                "production readiness",
            ],
        },
        "next_authorized_action": "Implement a rejection-only fragility screen that reports no net-profit metric",
        "safety": {
            "raw_data_modified": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
