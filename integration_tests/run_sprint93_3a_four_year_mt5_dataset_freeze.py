"""Acquire and freeze the preregistered read-only four-year MT5 dataset."""

from __future__ import annotations

from pathlib import Path

from mss.analysis.four_year_mt5_dataset_freeze import FourYearMT5DatasetFreeze as Freeze


ROOT = Path(__file__).resolve().parents[1]
TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")
OUTPUT_ROOT = ROOT / "historical_data" / "sprint93_3a_v3"
MANIFEST = ROOT / "reports" / "MSS_Sprint93_3A_Four_Year_MT5_Dataset_Freeze_V1.json"


def main() -> None:
    import MetaTrader5 as mt5

    if MANIFEST.exists() or OUTPUT_ROOT.exists():
        raise FileExistsError("authoritative freeze output already exists")
    if not TERMINAL_PATH.is_file():
        raise RuntimeError(f"MT5 terminal missing: {TERMINAL_PATH}")
    mt5.shutdown()
    if not mt5.initialize(path=str(TERMINAL_PATH), timeout=120_000):
        raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
    symbols: list[dict[str, object]] = []
    try:
        request_start = Freeze.utc(Freeze.WINDOW_START_EPOCH - 45 * 24 * 60 * 60)
        request_end_inclusive = Freeze.utc(Freeze.WINDOW_END_EXCLUSIVE_EPOCH - 1)
        for canonical, broker, asset_class in Freeze.UNIVERSE:
            if not mt5.symbol_select(broker, True):
                raise RuntimeError(f"broker symbol unavailable: {broker}: {mt5.last_error()}")
            info = mt5.symbol_info(broker)
            if info is None:
                raise RuntimeError(f"contract metadata unavailable: {broker}: {mt5.last_error()}")
            rates = mt5.copy_rates_range(
                broker, mt5.TIMEFRAME_M15, request_start, request_end_inclusive,
            )
            if rates is None:
                raise RuntimeError(f"M15 retrieval failed: {broker}: {mt5.last_error()}")
            frozen = Freeze.write_symbol(OUTPUT_ROOT / f"{canonical}_M15.jsonl", rates)
            symbols.append({
                "canonical_symbol": canonical,
                "broker_symbol": broker,
                "asset_class": asset_class,
                "contract_metadata": Freeze.normalize_contract(info),
                "dataset": frozen,
            })
            print("FROZEN", canonical, frozen["sha256"], flush=True)
    finally:
        mt5.shutdown()
    manifest_sha256 = Freeze.write_manifest(MANIFEST, symbols)
    print("WROTE", MANIFEST, manifest_sha256, flush=True)


if __name__ == "__main__":
    main()
