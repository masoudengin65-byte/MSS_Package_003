"""Run only the three Sprint 92A.2a corrected-valuation smoke symbols."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.corrected_valuation_smoke_replay import CorrectedValuationSmokeReplay
from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata, HistoricalBacktestConfig


ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v1.json"
AUDIT_PATH = ROOT / "reports/MSS_Sprint92A_Replay_Integrity_Audit.json"
OUTPUT_PATH = ROOT / "reports/MSS_Sprint92A2a_Corrected_Valuation_Smoke_Replay.json"
TARGET_COUNT = 10000
EXPECTED_WINDOWS = {
    "USDJPY": ("2026-03-13T07:45:00", "2026-08-07T16:45:00"),
    "USDCAD": ("2026-03-13T07:45:00", "2026-08-07T16:45:00"),
    "XAUUSD": ("2026-03-06T13:00:00", "2026-08-07T17:00:00"),
}


def config():
    return HistoricalBacktestConfig(
        warmup_candles=200, analysis_lookback=500,
        starting_balance=10000.0, risk_percent=1.0,
        reward_risk_ratio=2.0, spread_points=None,
        commission_per_lot=0.0, slippage_points=1.0,
        ambiguous_policy="STOP_LOSS_FIRST",
    )


def metadata(info):
    return BacktestSymbolMetadata(
        point=info.point, digits=info.digits,
        tick_size=info.trade_tick_size, tick_value=info.trade_tick_value,
        contract_size=info.trade_contract_size,
        volume_min=info.volume_min, volume_max=info.volume_max,
        volume_step=info.volume_step, spread_points=info.spread,
    )


def load_exact_window(symbol, expected_window):
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"{symbol}: symbol selection failed: {mt5.last_error()}")
    end_time = datetime.fromisoformat(expected_window[1])
    rates = mt5.copy_rates_from(
        symbol, mt5.TIMEFRAME_M15, end_time, TARGET_COUNT,
    )
    if rates is None or len(rates) != TARGET_COUNT:
        count = 0 if rates is None else len(rates)
        raise RuntimeError(f"{symbol}: expected {TARGET_COUNT} candles, got {count}")
    candles = [
        Candle(
            time=datetime.fromtimestamp(int(rate["time"])),
            open=float(rate["open"]), high=float(rate["high"]),
            low=float(rate["low"]), close=float(rate["close"]),
            tick_volume=int(rate["tick_volume"]), spread=int(rate["spread"]),
            real_volume=int(rate["real_volume"]),
        )
        for rate in rates
    ]
    actual_window = (candles[0].time.isoformat(), candles[-1].time.isoformat())
    if actual_window != expected_window:
        raise RuntimeError(
            f"{symbol}: exact frozen window mismatch: "
            f"{actual_window} != {expected_window}"
        )
    return candles


def main():
    adapter = MT5Adapter()
    connected, message = adapter.connect()
    if not connected:
        raise RuntimeError(f"MT5 connection failed: {message}")
    rows = []
    try:
        for symbol in CorrectedValuationSmokeReplay.SYMBOLS:
            candles = load_exact_window(symbol, EXPECTED_WINDOWS[symbol])
            info = mt5.symbol_info(symbol)
            if info is None:
                raise RuntimeError(f"{symbol}: broker metadata unavailable")
            broker_metadata = metadata(info)
            result = HistoricalBacktestEngine().run(
                symbol, "M15", candles,
                config(), broker_metadata,
            )
            if not result.valid:
                raise RuntimeError(f"{symbol}: corrected smoke replay invalid")
            rows.append({
                "canonical_symbol": symbol,
                "historical_window": {
                    "candle_count": len(candles),
                    "first_candle_open_time": EXPECTED_WINDOWS[symbol][0],
                    "last_candle_open_time": EXPECTED_WINDOWS[symbol][1],
                    "completed_candles_only": True,
                    "start_position": 1,
                    "source_selection": "MT5_COPY_RATES_FROM_EXACT_SPRINT91_END",
                    "requested_end_time": EXPECTED_WINDOWS[symbol][1],
                },
                "metadata": broker_metadata,
                "result": result,
            })
            print(
                "RESULT", symbol, result.diagnostics.opened_trades,
                result.diagnostics.closed_trades, result.metrics.net_profit,
                flush=True,
            )
        v1 = json.loads(V1_PATH.read_text(encoding="utf-8"))
        audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        report = CorrectedValuationSmokeReplay().build_report(rows, v1, audit)
        OUTPUT_PATH.write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(f"Wrote {OUTPUT_PATH}")
        print(f"status={report['overall_status']}")
        print("REAL_ORDERS_SENT=False")
        return report
    finally:
        adapter.shutdown()


if __name__ == "__main__":
    main()
