"""Run the authoritative Sprint 92A.3 replay exactly once on Sprint 91 windows."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.multi_asset_historical_replay_v2 import MultiAssetHistoricalReplayV2
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata, HistoricalBacktestConfig


ROOT = Path(__file__).resolve().parents[1]
V1_JSON = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v1.json"
V1_XLSX = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v1.xlsx"
OUTPUT = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v2.json"


def config():
    return HistoricalBacktestConfig(
        warmup_candles=200, analysis_lookback=500, starting_balance=10000.0,
        risk_percent=1.0, reward_risk_ratio=2.0, spread_points=None,
        commission_per_lot=0.0, slippage_points=1.0,
        ambiguous_policy="STOP_LOSS_FIRST",
    )


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_window(broker_symbol, first_time, last_time):
    if not mt5.symbol_select(broker_symbol, True):
        raise RuntimeError(f"{broker_symbol}: selection failed: {mt5.last_error()}")
    rates = mt5.copy_rates_from(
        broker_symbol, mt5.TIMEFRAME_M15, datetime.fromisoformat(last_time), 10000,
    )
    if rates is None or len(rates) != 10000:
        raise RuntimeError(f"{broker_symbol}: expected 10000 frozen candles, got {0 if rates is None else len(rates)}")
    candles = [Candle(
        time=datetime.fromtimestamp(int(row["time"])), open=float(row["open"]),
        high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
        tick_volume=int(row["tick_volume"]), spread=int(row["spread"]),
        real_volume=int(row["real_volume"]),
    ) for row in rates]
    actual = (candles[0].time.isoformat(), candles[-1].time.isoformat())
    expected = (first_time, last_time)
    if actual != expected:
        raise RuntimeError(f"{broker_symbol}: frozen window mismatch {actual} != {expected}")
    return candles


def symbol_metadata(info, account_currency):
    return BacktestSymbolMetadata(
        account_currency=account_currency, currency_base=info.currency_base,
        currency_profit=info.currency_profit, currency_margin=info.currency_margin,
        trade_calc_mode=int(info.trade_calc_mode), point=info.point,
        digits=info.digits, tick_size=info.trade_tick_size,
        tick_value=info.trade_tick_value, contract_size=info.trade_contract_size,
        volume_min=info.volume_min, volume_max=info.volume_max,
        volume_step=info.volume_step, spread_points=info.spread,
    )


def main():
    before = {str(path): file_hash(path) for path in (V1_JSON, V1_XLSX)}
    v1 = json.loads(V1_JSON.read_text(encoding="utf-8"))
    availability = {row["canonical_symbol"]: row for row in v1["history_availability"]}
    replay = MultiAssetHistoricalReplayV2()
    adapter = MT5Adapter()
    connected, message = adapter.connect()
    if not connected:
        raise RuntimeError(f"MT5 connection failed: {message}")
    histories, metadata, windows = {}, {}, {}
    try:
        account = mt5.account_info()
        if account is None or not account.currency:
            raise RuntimeError("Account currency unavailable")
        print("REAL_ORDER_API_USED False", flush=True)
        for symbol in replay.SYMBOLS:
            source = availability[symbol]
            broker = source["broker_symbol"]
            histories[symbol] = load_window(
                broker, source["first_candle_open_time"], source["last_candle_open_time"],
            )
            info = mt5.symbol_info(broker)
            if info is None:
                raise RuntimeError(f"{broker}: metadata unavailable")
            metadata[symbol] = symbol_metadata(info, account.currency)
            windows[symbol] = {
                "canonical_symbol": symbol, "broker_symbol": broker,
                "asset_class": replay.CLASSES[symbol], "candle_count": 10000,
                "first_candle_open_time": source["first_candle_open_time"],
                "last_candle_open_time": source["last_candle_open_time"],
                "last_candle_close_time": source["last_candle_close_time"],
                "completed_candles_only": True, "source_authority": "SPRINT_91_V1_SAVED_WINDOW_METADATA",
                "source_sha256": replay.source_hash(histories[symbol]),
            }
            print("SOURCE", symbol, broker, source["first_candle_open_time"], source["last_candle_open_time"], flush=True)
        print("FULL_STRATEGY_REPLAY_COUNT 1", flush=True)
        frozen_results = replay.run_once(histories, metadata, config())
        first = replay.build(histories, metadata, frozen_results, v1, config(), windows)
        second = replay.build(histories, metadata, frozen_results, v1, config(), windows)
        first_json = json.dumps(first, indent=2, sort_keys=True, allow_nan=False) + "\n"
        second_json = json.dumps(second, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if first_json != second_json:
            raise RuntimeError("Frozen replay artifact rebuild is not deterministic")
        first["audit"]["deterministic_json_rebuild"] = True
        first_json = json.dumps(first, indent=2, sort_keys=True, allow_nan=False) + "\n"
        OUTPUT.write_text(first_json, encoding="utf-8", newline="\n")
        after = {str(path): file_hash(path) for path in (V1_JSON, V1_XLSX)}
        if before != after:
            raise RuntimeError("Protected Sprint 91 v1 artifact changed")
        for row in first["per_symbol_results"]:
            print("RESULT", row["canonical_symbol"], row["closed_trades"], row["net_profit"], row["return_percent"], flush=True)
        print("COMBINED", json.dumps(first["combined_independent_results"], sort_keys=True), flush=True)
        print("JSON_SHA256", hashlib.sha256(first_json.encode()).hexdigest(), flush=True)
        print("V1_PRESERVED True", flush=True)
        print("REAL_ORDERS_SENT False", flush=True)
    finally:
        adapter.shutdown()


if __name__ == "__main__":
    main()
