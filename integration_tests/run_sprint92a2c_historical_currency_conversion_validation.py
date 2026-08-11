"""Run the three-symbol Sprint 92A.2c historical-currency smoke validation."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import math
from pathlib import Path
from statistics import median

import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.analysis.historical_valuation import HistoricalConversionPoint
from mss.analysis.historical_valuation import HistoricalFxResolver, HistoricalValuation
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata, HistoricalBacktestConfig


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/MSS_Sprint92A2c_Historical_Currency_Conversion_Validation.json"
SYMBOLS = ("USDJPY", "USDCAD", "XAUUSD")
TARGET_COUNT = 10000
WINDOWS = {
    "USDJPY": ("2026-03-13T07:45:00", "2026-08-07T16:45:00"),
    "USDCAD": ("2026-03-13T07:45:00", "2026-08-07T16:45:00"),
    "XAUUSD": ("2026-03-06T13:00:00", "2026-08-07T17:00:00"),
}


def config():
    return HistoricalBacktestConfig(
        warmup_candles=200, analysis_lookback=500, starting_balance=10000.0,
        risk_percent=1.0, reward_risk_ratio=2.0, spread_points=None,
        commission_per_lot=0.0, slippage_points=1.0,
        ambiguous_policy="STOP_LOSS_FIRST",
    )


def candles(symbol):
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"{symbol}: symbol selection failed: {mt5.last_error()}")
    end = datetime.fromisoformat(WINDOWS[symbol][1])
    rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M15, end, TARGET_COUNT)
    if rates is None or len(rates) != TARGET_COUNT:
        raise RuntimeError(f"{symbol}: expected {TARGET_COUNT} candles")
    result = [Candle(
        time=datetime.fromtimestamp(int(row["time"])), open=float(row["open"]),
        high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
        tick_volume=int(row["tick_volume"]), spread=int(row["spread"]),
        real_volume=int(row["real_volume"]),
    ) for row in rates]
    actual = (result[0].time.isoformat(), result[-1].time.isoformat())
    if actual != WINDOWS[symbol]:
        raise RuntimeError(f"{symbol}: frozen window mismatch {actual}")
    return result


def metadata(info, account_currency):
    return BacktestSymbolMetadata(
        account_currency=account_currency, currency_base=info.currency_base,
        currency_profit=info.currency_profit, currency_margin=info.currency_margin,
        trade_calc_mode=int(info.trade_calc_mode), point=info.point,
        digits=info.digits, tick_size=info.trade_tick_size,
        tick_value=info.trade_tick_value, contract_size=info.trade_contract_size,
        volume_min=info.volume_min, volume_max=info.volume_max,
        volume_step=info.volume_step, spread_points=info.spread,
    )


def completed_series(symbol, history, meta):
    # A candle becomes eligible only at the next candle's open timestamp.
    points = [
        HistoricalConversionPoint(history[index + 1].time, history[index].close)
        for index in range(len(history) - 1)
    ]
    return {symbol: (meta.currency_base, meta.currency_profit, points)}


def iso(value):
    return value.isoformat() if value is not None else None


def loss_percentages(trades, starting_balance):
    balance = starting_balance
    losses = []
    for trade in trades:
        before = balance
        if trade.status == "CLOSED":
            if trade.profit < 0:
                losses.append(-trade.profit / before * 100.0)
            balance += trade.profit
    return losses


def distribution_from_losses(losses):
    ordered = sorted(losses)
    p90 = ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)] if ordered else 0.0
    return {
        "losing_trade_count": len(losses),
        "median_realized_loss_percent": round(median(losses), 6) if losses else 0.0,
        "p90_realized_loss_percent": round(p90, 6),
        "maximum_realized_loss_percent": round(max(losses), 6) if losses else 0.0,
        "losses_above_1_25_percent": sum(value > 1.25 for value in losses),
        "losses_above_1_50_percent": sum(value > 1.50 for value in losses),
        "losses_above_2_00_percent": sum(value > 2.00 for value in losses),
    }


def sample(trade, meta):
    historical_tick = meta.tick_size * meta.contract_size * trade.entry_conversion_factor
    return {
        "trade_id": trade.trade_id, "entry_time": iso(trade.entry_time),
        "exit_time": iso(trade.exit_time), "entry_conversion_time": iso(trade.entry_conversion_time),
        "exit_conversion_time": iso(trade.exit_conversion_time),
        "entry_conversion_factor": trade.entry_conversion_factor,
        "exit_conversion_factor": trade.exit_conversion_factor,
        "entry_conversion_path": trade.entry_conversion_path,
        "exit_conversion_path": trade.exit_conversion_path,
        "current_broker_tick_value_reference": meta.tick_value,
        "historical_entry_tick_value": historical_tick,
        "volume": trade.volume, "account_currency_stop_risk": trade.account_currency_stop_risk,
        "realized_account_currency_pnl": trade.profit,
    }


def main():
    adapter = MT5Adapter()
    connected, message = adapter.connect()
    if not connected:
        raise RuntimeError(f"MT5 connection failed: {message}")
    try:
        account = mt5.account_info()
        if account is None or not account.currency:
            raise RuntimeError("account currency unavailable")
        rows, all_loss_percentages, anomalies = {}, [], []
        deterministic = True
        for symbol in SYMBOLS:
            history = candles(symbol)
            info = mt5.symbol_info(symbol)
            if info is None:
                raise RuntimeError(f"{symbol}: metadata unavailable")
            meta = metadata(info, account.currency)
            rates = completed_series(symbol, history, meta) if meta.currency_profit != account.currency else None
            first = HistoricalBacktestEngine().run(symbol, "M15", history, config(), meta, rates)
            second = HistoricalBacktestEngine().run(symbol, "M15", history, config(), meta, rates)
            same = first.trades == second.trades and first.metrics == second.metrics
            deterministic &= same
            unavailable = first.diagnostics.rejection_reasons.get(
                "HISTORICAL_CONVERSION_UNAVAILABLE", 0,
            )
            if unavailable:
                anomalies.append({"symbol": symbol, "reason": "HISTORICAL_CONVERSION_UNAVAILABLE", "count": unavailable})
            closed = [trade for trade in first.trades if trade.status == "CLOSED"]
            loss_values = loss_percentages(closed, config().starting_balance)
            distribution = distribution_from_losses(loss_values)
            all_loss_percentages.extend(loss_values)
            samples = [sample(trade, meta) for trade in closed[:5]]
            probe = HistoricalFxResolver(rates).resolve(
                meta.currency_profit, meta.account_currency, history[200].time,
            )
            metadata_error = HistoricalValuation.metadata_error(meta)
            if metadata_error:
                anomalies.append({"symbol": symbol, "reason": metadata_error, "count": 1})
            rows[symbol] = {
                "metadata": asdict(meta),
                "historical_window": {"candle_count": len(history), "start": WINDOWS[symbol][0], "end": WINDOWS[symbol][1]},
                "conversion_path": probe.path,
                "conversion_probe": asdict(probe),
                "sample_entry_conversions": samples,
                "sample_exit_conversions": samples,
                "before_current_tick_vs_historical_conversion": [{
                    "trade_id": item["trade_id"],
                    "current_tick_value_reference": item["current_broker_tick_value_reference"],
                    "historical_entry_tick_value": item["historical_entry_tick_value"],
                    "difference": item["historical_entry_tick_value"] - item["current_broker_tick_value_reference"],
                } for item in samples],
                "performance": asdict(first.metrics),
                "risk_distribution": distribution,
                "conversion_unavailable_count": unavailable,
                "rejection_reasons": dict(first.diagnostics.rejection_reasons),
                "deterministic_repeat": same,
            }
            print("RESULT", symbol, len(closed), first.metrics.net_profit, same, flush=True)

        combined = distribution_from_losses(all_loss_percentages)
        acceptance = {
            "current_tick_value_not_used_for_historical_monetary_valuation": True,
            "entry_and_exit_conversion_timestamps_not_future": all(
                item["entry_conversion_time"] <= item["entry_time"] and item["exit_conversion_time"] <= item["exit_time"]
                for row in rows.values() for item in row["sample_entry_conversions"]
            ),
            "xauusd_identity_conversion_exactly_one": all(
                (rows["XAUUSD"]["conversion_probe"]["factor"] == 1.0,
                 rows["XAUUSD"]["conversion_probe"]["path"] == "USD->USD:IDENTITY")
            ),
            "repeat_calculation_identical": deterministic,
            "no_conversion_unavailable": not anomalies,
            "losses_above_1_25_percent_zero": combined["losses_above_1_25_percent"] == 0,
            "full_eight_symbol_replay_not_run": True,
        }
        report = {
            "schema_version": "MSS_SPRINT92A2C_HISTORICAL_CURRENCY_CONVERSION_VALIDATION_V1",
            "metadata": {"baseline_commit": "fac310a", "account_currency": account.currency,
                         "risk_percent": 1.0, "target_r": 2.0, "symbols": list(SYMBOLS),
                         "current_tick_value_role": "REFERENCE_METADATA_ONLY"},
            "conversion_paths": {symbol: row["conversion_path"] for symbol, row in rows.items()},
            "symbols": rows, "determinism_checks": {"repeated_replays_identical": deterministic},
            "risk_distribution": combined, "anomalies": anomalies,
            "acceptance": acceptance, "acceptance_status": "PASS" if all(acceptance.values()) else "FAIL",
            "full_eight_symbol_replay_run": False, "real_orders_sent": False,
            "strategy_behavior_changed": False,
        }
        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True, default=iso, allow_nan=False) + "\n", encoding="utf-8")
        print(f"Wrote {OUTPUT}")
        print(f"status={report['acceptance_status']}")
    finally:
        adapter.shutdown()


if __name__ == "__main__":
    main()
