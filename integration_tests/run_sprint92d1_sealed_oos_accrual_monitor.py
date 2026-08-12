"""Capture timestamp-only True-OOS accrual health from MT5."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.sealed_oos_accrual_monitor import SealedOosAccrualMonitor


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports/MSS_Sprint92C6_Research_Closure_True_OOS_Preregistration.json"
C2 = ROOT / "reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json"
OUTPUT = ROOT / "reports/MSS_Sprint92D1_Sealed_OOS_Accrual_Monitor.json"


def main():
    protocol_bytes = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_bytes)
    c2 = json.loads(C2.read_text(encoding="utf-8"))
    if protocol["true_oos_preregistration"]["accrual_gate"]["minimum_completed_m15_candles_per_symbol"] != 10_000:
        raise RuntimeError("Preregistered gate mismatch")
    adapter = MT5Adapter()
    connected, message = adapter.connect()
    if not connected:
        raise RuntimeError(f"MT5 connection failed: {message}")
    rows = []
    try:
        for frozen in c2["symbols"]:
            canonical, broker = frozen["canonical_symbol"], frozen["broker_symbol"]
            boundary = frozen["v2_exposure_boundary"]["last_candle_close_time"]
            boundary_epoch = SealedOosAccrualMonitor.parse_utc(boundary)
            current = mt5.copy_rates_from_pos(broker, mt5.TIMEFRAME_M15, 0, 1)
            if current is None or len(current) != 1:
                raise RuntimeError(f"{broker}: current-bar boundary unavailable")
            current_epoch = int(current[0]["time"])
            raw = mt5.copy_rates_range(
                broker, mt5.TIMEFRAME_M15,
                datetime.fromtimestamp(boundary_epoch, timezone.utc),
                datetime.fromtimestamp(current_epoch, timezone.utc),
            )
            if raw is None:
                raise RuntimeError(f"{broker}: timestamp retrieval failed: {mt5.last_error()}")
            timestamps = [int(row["time"]) for row in raw]
            result = SealedOosAccrualMonitor.inspect_symbol(
                canonical, broker, frozen["asset_class"], boundary, timestamps, current_epoch,
            )
            rows.append(result)
            print("ACCRUAL", canonical, result["completed_timestamp_count"], result["remaining_timestamp_count"], flush=True)
    finally:
        adapter.shutdown()
    payload = SealedOosAccrualMonitor.build(rows, hashlib.sha256(protocol_bytes).hexdigest())
    output = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    print("GATE", payload["global_gate"]["status"], flush=True)
    print("OHLC_PERSISTED False", flush=True)
    print("STRATEGY_REPLAY_RUN False", flush=True)
    print("JSON_SHA256", hashlib.sha256(output.encode()).hexdigest(), flush=True)


if __name__ == "__main__":
    main()
