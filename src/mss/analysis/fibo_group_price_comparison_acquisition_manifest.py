"""Freeze a FIBO Group demo comparison scope before any candidate-bar access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(root: Path) -> dict[str, object]:
    reports = root / "reports"
    preregistration_path = reports / "MSS_Sprint93_3D_Independent_Price_Comparison_Preregistration_V1.json"
    quality_path = reports / "MSS_Sprint93_3A_Data_Quality_V1.json"
    preregistration = json.loads(preregistration_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if preregistration["safety"]["candidate_data_acquired"]:
        raise ValueError("Source-specific manifest must precede candidate data acquisition")
    if preregistration["safety"]["order_send_called"]:
        raise ValueError("Price comparison requires an order-send-free preregistration")

    frozen_symbols = {item["symbol"] for item in quality["symbols"]}
    mappings = [
        {"frozen_broker_symbol": "EURUSD", "fibo_group_symbol": "EURUSD"},
        {"frozen_broker_symbol": "XAUUSD", "fibo_group_symbol": "XAUUSD"},
        {"frozen_broker_symbol": "BTCUSD", "fibo_group_symbol": "BTC"},
        {"frozen_broker_symbol": "ETHUSD", "fibo_group_symbol": "ETH"},
    ]
    if any(item["frozen_broker_symbol"] not in frozen_symbols for item in mappings):
        raise ValueError("Every mapped symbol must exist in the frozen data-quality report")

    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_PRICE_COMPARISON_ACQUISITION_MANIFEST_V1",
        "purpose": "Read-only four-instrument FIBO Group demo price comparison against frozen MT5 bars",
        "provenance": {
            "independent_price_preregistration_sha256": sha256(preregistration_path),
            "frozen_data_quality_sha256": sha256(quality_path),
            "candidate_data_acquired_before_manifest": False,
            "symbol_mapping_evidence": "User-supplied MT5 Market Watch screenshots",
        },
        "source": {
            "provider": "FIBO Group",
            "mt5_server": "FIBOGroup-MT5 Server",
            "account_class": "demo",
            "credentials_recorded": False,
            "live_account_login_allowed": False,
            "terms_of_use_verified": False,
            "terms_of_use_requirement": "Record applicable research or automation terms before acquisition",
        },
        "symbol_mappings": mappings,
        "acquisition_contract": {
            "timezone": "UTC",
            "timeframe": quality["window"]["timeframe"],
            "fields": ["time", "open", "high", "low", "close"],
            "comparison_window_rule": "Use only the exact overlap with each frozen broker symbol; do not extend or fabricate unavailable history",
            "no_interpolation": True,
            "no_resampling_across_market_closures": True,
            "read_only_mt5_calls": ["initialize", "symbol_select", "copy_rates_range", "shutdown"],
            "forbidden_mt5_calls": ["order_check", "order_send"],
        },
        "pre_acquisition_gates": {
            "terms_of_use_verified": False,
            "exact_symbol_mapping_verified": True,
            "demo_server_verified": True,
            "all_required_gates_pass": False,
            "blocker": "Applicable FIBO Group research or automation terms have not yet been recorded",
        },
        "interpretation_boundary": {
            "allowed": "Price-pattern consistency or discrepancy finding only",
            "cannot_establish": [
                "historical Alpari trading sessions",
                "historical Alpari commission or swap",
                "historical Alpari execution quality",
                "broker-accurate net profit",
                "production readiness",
            ],
        },
        "safety": {
            "candidate_data_acquired": False,
            "raw_frozen_data_modified": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
        "next_action": "Record FIBO Group research-use terms, then run a separate read-only acquisition command only if every pre-acquisition gate passes",
    }
