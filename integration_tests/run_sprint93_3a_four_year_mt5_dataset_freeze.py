"""Acquire and freeze the preregistered read-only four-year MT5 dataset."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

from mss.analysis.four_year_mt5_dataset_freeze import FourYearMT5DatasetFreeze as Freeze


ROOT = Path(__file__).resolve().parents[1]
TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")
OUTPUT_ROOT = ROOT / "historical_data" / "sprint93_3a_v5"
MANIFEST = ROOT / "reports" / "MSS_Sprint93_3A_Four_Year_MT5_Dataset_Freeze_V2.json"
PREREGISTRATION = ROOT / "reports" / "MSS_Sprint93_3A_Availability_Preregistration_V5.json"


def main() -> None:
    import MetaTrader5 as mt5

    if MANIFEST.exists() or OUTPUT_ROOT.exists():
        raise FileExistsError("authoritative freeze output already exists")
    protocol_bytes = PREREGISTRATION.read_bytes()
    protocol = json.loads(protocol_bytes)
    window = protocol["core_universe"]["historical_window"]
    if (int(datetime.fromisoformat(window["start_utc_inclusive"].replace("Z", "+00:00")).timestamp()) != Freeze.WINDOW_START_EPOCH
            or int(datetime.fromisoformat(window["end_utc_exclusive"].replace("Z", "+00:00")).timestamp()) != Freeze.WINDOW_END_EXCLUSIVE_EPOCH
            or window["warmup_candles_before_window"] != Freeze.WARMUP_CANDLES):
        raise RuntimeError("freezer differs from the published protocol")
    provenance = {
        "preregistration_file": PREREGISTRATION.name,
        "preregistration_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "acquisition_started_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_directory": str(OUTPUT_ROOT.relative_to(ROOT)),
        "contract_metadata_scope": "CURRENT_SNAPSHOT_NOT_HISTORICAL_VALUATION_AUTHORITY",
    }
    if not TERMINAL_PATH.is_file():
        raise RuntimeError(f"MT5 terminal missing: {TERMINAL_PATH}")
    mt5.shutdown()
    if not mt5.initialize(path=str(TERMINAL_PATH), timeout=120_000):
        raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
    symbols: list[dict[str, object]] = []
    prepared = []
    try:
        for canonical, broker, asset_class in Freeze.UNIVERSE:
            if not mt5.symbol_select(broker, True):
                raise RuntimeError(f"broker symbol unavailable: {broker}: {mt5.last_error()}")
            info = mt5.symbol_info(broker)
            if info is None:
                raise RuntimeError(f"contract metadata unavailable: {broker}: {mt5.last_error()}")
            rates: list[object] = []
            for request_start, request_end_inclusive in Freeze.acquisition_ranges():
                chunk = mt5.copy_rates_range(
                    broker, mt5.TIMEFRAME_M15, request_start, request_end_inclusive,
                )
                if chunk is None:
                    raise RuntimeError(
                        f"M15 retrieval failed: {broker}: {request_start.isoformat()}: "
                        f"{mt5.last_error()}"
                    )
                rates.extend(chunk)
            contract = Freeze.normalize_contract(info)
            Freeze.select_window(rates)
            prepared.append((canonical, broker, asset_class, contract, rates))
            print("PREFLIGHT_PASS", canonical, flush=True)
        # Every symbol must pass before the first raw file is published.
        for canonical, broker, asset_class, contract, rates in prepared:
            frozen = Freeze.write_symbol(OUTPUT_ROOT / f"{canonical}_M15.jsonl", rates)
            symbols.append({
                "canonical_symbol": canonical,
                "broker_symbol": broker,
                "asset_class": asset_class,
                "contract_metadata": contract,
                "dataset": frozen,
            })
            print("FROZEN", canonical, frozen["sha256"], flush=True)
    finally:
        mt5.shutdown()
    provenance["acquisition_finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest_sha256 = Freeze.write_manifest(MANIFEST, symbols, provenance)
    print("WROTE", MANIFEST, manifest_sha256, flush=True)


if __name__ == "__main__":
    main()
