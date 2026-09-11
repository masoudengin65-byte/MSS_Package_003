"""Record FIBO MT5 NDD's current public commission reference without historical claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SPECIFICATIONS_URL = (
    "https://www.fibogroup.com/products/account-types/mt5/specifications/"
)
SNAPSHOT_NAME = "MSS_Sprint93_3F_FIBO_Group_Current_Cost_Snapshot_V1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_evidence(root: Path) -> dict[str, object]:
    snapshot_path = root / "reports" / SNAPSHOT_NAME
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot["source"]["mt5_server"] != "FIBOGroup-MT5 Server":
        raise ValueError(
            "Current public commission reference requires the verified FIBO MT5 snapshot"
        )
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_CURRENT_PUBLIC_COMMISSION_EVIDENCE_V1",
        "purpose": "Current MT5 NDD commission reference for hypothetical research scenarios only",
        "source": {
            "provider": "FIBO Group",
            "url": SPECIFICATIONS_URL,
            "account_type": "MT5 NDD",
            "account_type_match_confirmed_by_user": True,
            "current_snapshot_sha256": _sha256(snapshot_path),
        },
        "current_public_commission_reference": [
            {"symbol": "EURUSD", "model": "PER_LOT", "amount": 3.0, "currency": "EUR"},
            {"symbol": "XAUUSD", "model": "PERCENT_NOTIONAL", "rate_percent": 0.003},
            {
                "symbol": "BTC",
                "model": "PERCENT_NOTIONAL_MINIMUM",
                "rate_percent": 0.15,
                "minimum_amount": 1.0,
                "minimum_currency": "USD",
            },
            {
                "symbol": "ETH",
                "model": "PERCENT_NOTIONAL_MINIMUM",
                "rate_percent": 0.15,
                "minimum_amount": 1.0,
                "minimum_currency": "USD",
            },
        ],
        "interpretation_boundary": {
            "current_public_terms_are_historical_terms": False,
            "allowed": "Use as a labelled current-reference input for hypothetical conservative scenarios",
            "cannot_establish": [
                "historical FIBO fees",
                "historical Alpari fees",
                "broker-accurate historical net profit",
                "production readiness",
            ],
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
