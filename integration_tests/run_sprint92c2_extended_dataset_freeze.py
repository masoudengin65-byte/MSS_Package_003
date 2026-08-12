"""Create the Sprint 92C.2 manifest without strategy or replay execution."""

import json
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.extended_dataset_freeze import ExtendedDatasetFreeze
from mss.analysis.historical_depth_audit import HistoricalDepthAudit


ROOT = Path(__file__).resolve().parents[1]
TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")
V2_SOURCE = ROOT / "reports" / "MSS_Multi_Asset_Historical_Replay_v2.json"
C1_SOURCE = ROOT / "reports" / "MSS_Sprint92C1_Historical_Depth_Audit.json"
OUTPUT = ROOT / "reports" / "MSS_Sprint92C2_Extended_Dataset_Manifest.json"


def main():
    v2 = json.loads(V2_SOURCE.read_text(encoding="utf-8"))
    c1 = json.loads(C1_SOURCE.read_text(encoding="utf-8"))
    windows = {row["canonical_symbol"]: row for row in v2["source_windows"]}
    c1_m15 = {row["canonical_symbol"]: row for row in c1["depth_results"] if row["timeframe"] == "M15"}
    if not TERMINAL_PATH.is_file():
        raise RuntimeError(f"MT5 terminal missing: {TERMINAL_PATH}")
    mt5.shutdown()
    if not mt5.initialize(path=str(TERMINAL_PATH), timeout=120_000):
        raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
    manifests = []
    try:
        for canonical, broker, _asset_class in HistoricalDepthAudit.UNIVERSE:
            if not mt5.symbol_select(broker, True):
                raise RuntimeError(f"Broker symbol unavailable: {broker}: {mt5.last_error()}")
            c1_row = c1_m15[canonical]
            anchor = datetime.fromisoformat(
                c1_row["newest_completed_candle_open_timestamp"].replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            rates = mt5.copy_rates_from(broker, mt5.TIMEFRAME_M15, anchor, ExtendedDatasetFreeze.DATASET_CANDLES)
            if rates is None:
                raise RuntimeError(f"M15 retrieval failed for {broker}: {mt5.last_error()}")
            completed_boundary = ExtendedDatasetFreeze.parse_utc(c1_row["completed_candle_boundary_timestamp"])
            manifest = ExtendedDatasetFreeze.freeze_symbol(rates, windows[canonical], completed_boundary)
            manifest["freeze_anchor_timestamp"] = c1_row["newest_completed_candle_open_timestamp"]
            manifest["freeze_authority"] = "SPRINT_92C1_EXACT_50000_M15_WINDOW"
            manifest["c1_stability_status"] = c1["m15_stability"][canonical]["status"]
            manifest["c1_expected_50000_sha256"] = c1_m15[canonical]["ohlc_sha256"]
            manifest["matches_c1_50000_sha256"] = manifest["full_dataset_sha256"] == c1_m15[canonical]["ohlc_sha256"]
            manifests.append(manifest)
            print("FROZEN", canonical, manifest["full_dataset_sha256"], flush=True)
    finally:
        mt5.shutdown()

    payload = {
        "schema_version": "MSS_SPRINT92C2_EXTENDED_DATASET_MANIFEST_V1",
        "mode": "DATASET_FREEZE_AND_OOS_QUARANTINE_ONLY",
        "source_authorities": {
            "depth_audit": C1_SOURCE.name,
            "v2_exposure_boundaries": V2_SOURCE.name,
        },
        "methodology": {
            "timeframe": "M15", "completed_candles_only": True,
            "fixed_history_count_per_symbol": 50_000,
            "development_count": 30_000, "validation_count": 10_000,
            "remaining_partition": "V2_EXPOSURE_BOUNDARY",
            "freeze_anchor": "PER_SYMBOL_SPRINT_92C1_NEWEST_COMPLETED_M15_OPEN_TIMESTAMP",
            "true_oos_access": "FROZEN_NO_ANALYSIS",
            "raw_candle_payload_committed": False,
            "strategy_or_replay_run": False, "performance_metrics_computed": False,
            "trading_operations_performed": 0,
        },
        "symbols": manifests,
        "acceptance": {
            "symbol_count": len(manifests),
            "all_fixed_50000": len(manifests) == 8 and all(row["frozen_candle_count"] == 50_000 for row in manifests),
            "all_partitions_reconcile": all(row["partition_reconciliation"]["equals_frozen_dataset"] for row in manifests),
            "all_c1_stable": all(row["c1_stability_status"] == "STABLE" for row in manifests),
            "all_frozen_hashes_match_c1": all(row["matches_c1_50000_sha256"] for row in manifests),
            "true_oos_never_analyzed": all(
                next(s for s in row["slices"] if s["slice"] == "TRUE_OOS_ACCRUAL")["analysis_access"] == "FROZEN_NO_ANALYSIS"
                for row in manifests
            ),
            "strategy_or_replay_run": False,
            "performance_metrics_computed": False,
            "trading_operations_performed": 0,
        },
        "limitations": [
            "Hashes freeze broker-returned candle content; raw 50k payloads are intentionally not committed to Git.",
            "A later broker correction can change a repeated retrieval; any mismatch must be reported, never silently accepted.",
            "True OOS accrual is identified and hashed only; no outcome, signal, trade, or performance analysis is present.",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print("WROTE", OUTPUT)


if __name__ == "__main__":
    main()
