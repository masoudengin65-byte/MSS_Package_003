"""Freeze gap and zero-spread rules before any rejection-only fragility screen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

QUALITY_NAME = "MSS_Sprint93_3A_Data_Quality_V1.json"
SCENARIO_NAME = "MSS_Sprint93_3F_FIBO_Group_Cost_Scenario_Protocol_V2.json"
MAPPINGS = (
    ("EURUSD", "EURUSD"),
    ("XAUUSD", "XAUUSD"),
    ("BTCUSD", "BTC"),
    ("ETHUSD", "ETH"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_preregistration(root: Path) -> dict[str, object]:
    reports = root / "reports"
    quality_path = reports / QUALITY_NAME
    scenario_path = reports / SCENARIO_NAME
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    if not quality["all_integrity_checks_pass"]:
        raise ValueError("Fragility pre-registration requires intact frozen evidence")
    baseline = {row["symbol"]: row for row in scenario["scenarios"][0]["inputs"]}
    rules = []
    for frozen_symbol, fibo_symbol in MAPPINGS:
        source = next(
            row for row in quality["symbols"] if row["symbol"] == frozen_symbol
        )
        rules.append(
            {
                "frozen_broker_symbol": frozen_symbol,
                "fibo_group_symbol": fibo_symbol,
                "known_internal_gap_count": source["internal_gap_count"],
                "gap_rule": "NO_ENTRY_IF_LOOKBACK_CROSSES_GAP; NO_POSITION_MAY_BE_CARRIED_ACROSS_A_GAP",
                "zero_spread_rule": "REPLACE_ZERO_WITH_DECLARED_BASELINE_CURRENT_REFERENCE_SPREAD_POINTS",
                "baseline_replacement_spread_points": baseline[fibo_symbol][
                    "spread_points"
                ],
            }
        )
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_FRAGILITY_SCREEN_PREREGISTRATION_V1",
        "purpose": "Freeze gap and zero-spread treatment before a rejection-only hypothetical cost screen",
        "provenance": {
            "frozen_quality_sha256": _sha256(quality_path),
            "cost_scenario_v2_sha256": _sha256(scenario_path),
        },
        "rules": rules,
        "outcome_boundary": {
            "strategy_or_replay_run": False,
            "historical_net_profit_replay_eligible": False,
            "allowed": "Only reject a candidate shown fragile under declared hypothetical costs",
            "forbidden": [
                "acceptance",
                "broker-accurate profitability",
                "production readiness",
            ],
        },
        "safety": {
            "raw_data_modified": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
