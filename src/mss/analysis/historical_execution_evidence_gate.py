"""Gate historical net-profit replay on broker-specific execution evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REQUIRED_EVIDENCE = {
    "exact_server_and_account_type": "UNAVAILABLE",
    "historical_trading_sessions_and_exceptions": "UNAVAILABLE",
    "historical_zero_spread_semantics_or_bid_ask_history": "UNAVAILABLE",
    "dated_contract_size_and_volume_schedule": "UNAVAILABLE",
    "dated_commission_schedule": "UNAVAILABLE",
    "dated_swap_and_rollover_schedule": "UNAVAILABLE",
    "historical_margin_and_leverage_rules": "UNAVAILABLE",
    "slippage_assumption_with_documented_authority": "UNAVAILABLE",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_gate(root: Path) -> dict[str, object]:
    reports = root / "reports"
    dataset_manifest = reports / "MSS_Sprint93_3A_Four_Year_MT5_Dataset_Freeze_V2.json"
    quality_report = reports / "MSS_Sprint93_3A_Data_Quality_V1.json"
    manifest = json.loads(dataset_manifest.read_text(encoding="utf-8"))
    quality = json.loads(quality_report.read_text(encoding="utf-8"))
    if not quality["all_integrity_checks_pass"]:
        raise ValueError("Historical raw-data integrity is not established")
    if quality["replay_eligible"]:
        raise ValueError("Quality report must not pre-clear a net-profit replay")
    return {
        "schema_version": "MSS_SPRINT93_3B_HISTORICAL_EXECUTION_EVIDENCE_GATE_V1",
        "purpose": "Prevent unsupported historical net-profit or execution claims",
        "scope": {
            "dataset_manifest_sha256": sha256(dataset_manifest),
            "quality_report_sha256": sha256(quality_report),
            "window": manifest["window"],
            "symbols": [item["canonical_symbol"] for item in manifest["symbols"]],
        },
        "evidence_status": REQUIRED_EVIDENCE.copy(),
        "net_profit_replay": {
            "eligible": False,
            "release_condition": "Every required evidence item is VERIFIED and retained with provenance",
            "prohibited_claims": [
                "broker-accurate net profit",
                "broker-accurate drawdown after costs",
                "historical execution quality",
                "production readiness",
            ],
        },
        "independent_price_source": {
            "allowed_purpose": "Cross-validate timestamp and OHLC patterns only",
            "cannot_clear": [
                "historical commission",
                "historical swap",
                "broker-specific sessions",
                "broker-specific execution costs",
                "net_profit_replay",
            ],
            "tradingview_role": "Manual visual comparison only; not an execution authority",
        },
        "safety": {
            "raw_data_modified": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
        "next_authorized_action": {
            "action": "Obtain documentary broker evidence using the local unsent request draft",
            "draft_path": "reports/MSS_Sprint93_3A_Broker_Evidence_Request_DRAFT.md",
            "external_message_sent": False,
        },
    }
