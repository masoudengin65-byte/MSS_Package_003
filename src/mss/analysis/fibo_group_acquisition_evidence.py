"""Summarise immutable FIBO candidate bars without comparing or replaying them."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


MANIFEST_NAME = "MSS_Sprint93_3F_FIBO_Group_Price_Comparison_Acquisition_Manifest_V1.json"
MAPPINGS = (("EURUSD", "EURUSD"), ("XAUUSD", "XAUUSD"), ("BTCUSD", "BTC"), ("ETHUSD", "ETH"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bounds(path: Path) -> tuple[int, int, int]:
    first = last = None
    rows = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            timestamp = int(item["time"])
            if first is None:
                first = timestamp
            if last is not None and timestamp <= last:
                raise ValueError(f"Non-increasing timestamp in {path.name}")
            last = timestamp
            rows += 1
    if first is None or last is None:
        raise ValueError(f"Empty candidate evidence: {path.name}")
    return rows, first, last


def build_evidence(root: Path, evidence_root: Path | None = None) -> dict[str, object]:
    manifest_path = root / "reports" / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest["pre_acquisition_gates"]["all_required_gates_pass"]:
        raise ValueError("Cannot certify evidence from a closed acquisition manifest")
    evidence_root = evidence_root or root / "historical_data" / "sprint93_3f_fibo_candidate"
    symbols = []
    for frozen_symbol, fibo_symbol in MAPPINGS:
        path = evidence_root / f"{fibo_symbol}_M15.jsonl"
        rows, first, last = _bounds(path)
        symbols.append(
            {
                "frozen_broker_symbol": frozen_symbol,
                "fibo_group_symbol": fibo_symbol,
                "filename": path.name,
                "row_count": rows,
                "first_utc_epoch": first,
                "last_utc_epoch": last,
                "sha256": _sha256(path),
            }
        )
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_ACQUISITION_EVIDENCE_V1",
        "purpose": "Evidence inventory only; no cross-source comparison, strategy, replay, or performance result",
        "provenance": {
            "acquisition_manifest_sha256": _sha256(manifest_path),
            "raw_evidence_committed": False,
            "raw_evidence_root": "historical_data/sprint93_3f_fibo_candidate",
        },
        "source": {"provider": "FIBO Group", "mt5_server": "FIBOGroup-MT5 Server", "account_class": "demo"},
        "symbols": symbols,
        "interpretation_boundary": {
            "allowed": "Verify the immutable candidate evidence inventory and later evaluate price-pattern consistency only",
            "cannot_establish": [
                "historical Alpari trading sessions",
                "historical Alpari commission or swap",
                "historical Alpari execution quality",
                "broker-accurate net profit",
                "production readiness",
            ],
        },
        "safety": {
            "candidate_data_acquired": True,
            "raw_frozen_data_modified": False,
            "comparison_run": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
        "next_action": "Run a separately preregistered price-pattern comparison; do not infer execution quality or profitability",
    }
