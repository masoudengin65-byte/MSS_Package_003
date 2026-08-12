"""Run Sprint 92C.3 once on only the frozen development and validation slices."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.extended_dataset_freeze import ExtendedDatasetFreeze
from mss.analysis.extended_development_validation_replay import ExtendedDevelopmentValidationReplay
from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata, HistoricalBacktestConfig


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json"
OUTPUT = ROOT / "reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json"


def config():
    return HistoricalBacktestConfig(warmup_candles=200, analysis_lookback=500, starting_balance=10000.0,
        risk_percent=1.0, reward_risk_ratio=2.0, spread_points=None, commission_per_lot=0.0,
        slippage_points=1.0, ambiguous_policy="STOP_LOSS_FIRST")


def candle(row):
    return Candle(time=datetime.fromtimestamp(int(row["time"])), open=float(row["open"]),
        high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
        tick_volume=int(row["tick_volume"]), spread=int(row["spread"]), real_volume=int(row["real_volume"]))


def metadata(info, account_currency):
    return BacktestSymbolMetadata(account_currency=account_currency, currency_base=info.currency_base,
        currency_profit=info.currency_profit, currency_margin=info.currency_margin,
        trade_calc_mode=int(info.trade_calc_mode), point=info.point, digits=info.digits,
        tick_size=info.trade_tick_size, tick_value=info.trade_tick_value,
        contract_size=info.trade_contract_size, volume_min=info.volume_min,
        volume_max=info.volume_max, volume_step=info.volume_step, spread_points=info.spread)


def main():
    manifest_bytes = MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes)
    rows = {row["canonical_symbol"]: row for row in manifest["symbols"]}
    engine = ExtendedDevelopmentValidationReplay()
    adapter = MT5Adapter()
    connected, message = adapter.connect()
    if not connected:
        raise RuntimeError(f"MT5 connection failed: {message}")
    histories = {segment: {} for segment in engine.SEGMENTS}
    symbol_metadata = {}
    try:
        account = mt5.account_info()
        if account is None or not account.currency:
            raise RuntimeError("Account currency unavailable")
        for symbol in engine.replay.SYMBOLS:
            frozen = rows[symbol]
            broker = frozen["broker_symbol"]
            anchor = datetime.fromisoformat(frozen["freeze_anchor_timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc)
            raw = mt5.copy_rates_from(broker, mt5.TIMEFRAME_M15, anchor, 50_000)
            if raw is None or len(raw) != 50_000:
                raise RuntimeError(f"{symbol}: exact 50000 snapshot unavailable")
            actual_hash = HistoricalDepthAudit.candle_hash(raw)
            if actual_hash != frozen["full_dataset_sha256"]:
                raise RuntimeError(f"{symbol}: frozen 50000 hash mismatch; replay prohibited")
            histories["DEVELOPMENT"][symbol] = [candle(row) for row in raw[:30_000]]
            histories["VALIDATION"][symbol] = [candle(row) for row in raw[30_000:40_000]]
            info = mt5.symbol_info(broker)
            if info is None:
                raise RuntimeError(f"{symbol}: metadata unavailable")
            symbol_metadata[symbol] = metadata(info, account.currency)
            print("SOURCE_VERIFIED", symbol, actual_hash, flush=True)
        print("TRUE_OOS_CANDLES_USED 0", flush=True)
        print("RESEARCH_EXPOSED_CANDLES_USED 0", flush=True)
        results = engine.run(histories, symbol_metadata, config())
        payload = engine.build(histories, symbol_metadata, results, config(), manifest, hashlib.sha256(manifest_bytes).hexdigest())
        first = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        second = json.dumps(engine.build(histories, symbol_metadata, results, config(), manifest, hashlib.sha256(manifest_bytes).hexdigest()), indent=2, sort_keys=True, allow_nan=False) + "\n"
        if first != second:
            raise RuntimeError("Artifact rebuild is not deterministic")
        payload["audit"]["deterministic_artifact_rebuild"] = True
        output = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        OUTPUT.write_text(output, encoding="utf-8", newline="\n")
        for segment in engine.SEGMENTS:
            for row in payload["segments"][segment]["per_symbol_results"]:
                print("RESULT", segment, row["canonical_symbol"], row["closed_trades"], row["net_profit"], row["profit_factor"], flush=True)
        print("JSON_SHA256", hashlib.sha256(output.encode()).hexdigest(), flush=True)
        print("REAL_ORDERS_SENT False", flush=True)
    finally:
        adapter.shutdown()


if __name__ == "__main__":
    main()
