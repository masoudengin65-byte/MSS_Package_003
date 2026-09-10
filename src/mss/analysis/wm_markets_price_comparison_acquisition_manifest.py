"""Freeze the WM Markets demo acquisition scope before reading comparison bars."""

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

    frozen_symbols = {item["symbol"]: item for item in quality["symbols"]}
    mappings = [
        {
            "frozen_broker_symbol": "EURUSD",
            "wm_markets_symbol": "EURUSD",
            "observed_description": "Euro vs US Dollar",
            "observed_contract_size_text": None,
        },
        {
            "frozen_broker_symbol": "XAUUSD",
            "wm_markets_symbol": "XAUUSD",
            "observed_description": "Spot Gold vs US Dollar",
            "observed_contract_size_text": "1 lot = 100 oz",
        },
        {
            "frozen_broker_symbol": "BTCUSD",
            "wm_markets_symbol": "BTCUSD",
            "observed_description": "CFD BITCOIN vs US Dollar",
            "observed_contract_size_text": "1 lot = 1 coin",
        },
        {
            "frozen_broker_symbol": "ETHUSD",
            "wm_markets_symbol": "ETHUSD",
            "observed_description": "CFD ETHEREUM vs US Dollar",
            "observed_contract_size_text": "1 lot = 10 coins",
        },
    ]
    if any(item["frozen_broker_symbol"] not in frozen_symbols for item in mappings):
        raise ValueError("Every mapped symbol must exist in the frozen data-quality report")

    return {
        "schema_version": "MSS_SPRINT93_3E_WM_MARKETS_PRICE_COMPARISON_ACQUISITION_MANIFEST_V1",
        "purpose": "Read-only four-instrument WM Markets demo price comparison against frozen MT5 bars",
        "provenance": {
            "independent_price_preregistration_sha256": sha256(preregistration_path),
            "frozen_data_quality_sha256": sha256(quality_path),
            "prior_candidate_source": preregistration["candidate_source"]["name"],
            "source_selection_change": "WM Markets replaces the unselected Windsor candidate; no Windsor data was acquired",
        },
        "source": {
            "provider": "WM Markets Ltd",
            "mt5_server": "WMMMarkets-Demo",
            "account_class": "demo",
            "account_mode": "hedge",
            "credentials_recorded": False,
            "live_account_login_allowed": False,
            "terms_of_use_verified": False,
            "terms_of_use_requirement": "Record permission for local research use before acquisition",
        },
        "symbol_mappings": mappings,
        "acquisition_contract": {
            "timezone": "UTC",
            "timeframe": quality["window"]["timeframe"],
            "fields": ["time", "open", "high", "low", "close"],
            "comparison_window_rule": "Use the exact overlap with each frozen broker symbol; do not extend or fabricate unavailable history",
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
            "blocker": "Terms of use for local research collection have not yet been recorded",
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
        "next_action": "Record WM Markets research-use terms, then run the separate read-only acquisition command only if every pre-acquisition gate passes",
    }
