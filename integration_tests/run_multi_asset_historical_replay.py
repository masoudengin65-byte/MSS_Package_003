"""Run Sprint 91 multi-asset historical research without sending orders."""

import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.adapters.mt5.history import HistoryLoadError, HistoryService
from mss.analysis.multi_asset_historical_replay import MultiAssetHistoricalReplay
from mss.domain.historical_backtest import HistoricalBacktestConfig


JSON_PATH = Path("reports/MSS_Multi_Asset_Historical_Replay_v2.json")
TARGET_CANDLE_COUNT = 10000
TIMEFRAME = mt5.TIMEFRAME_M15


def replay_config():
    return HistoricalBacktestConfig(
        warmup_candles=200,
        analysis_lookback=500,
        starting_balance=10000.0,
        risk_percent=1.0,
        reward_risk_ratio=2.0,
        spread_points=None,
        commission_per_lot=0.0,
        slippage_points=1.0,
        ambiguous_policy="STOP_LOSS_FIRST",
    )


def main():
    adapter = MT5Adapter()
    connected, message = adapter.connect()
    if not connected:
        raise RuntimeError(f"MT5 connection failed: {message}")

    replay = MultiAssetHistoricalReplay()
    service = HistoryService(max_attempts=3, retry_delay=0.5)
    history = {}
    metadata = {}
    try:
        broker_symbols = tuple(mt5.symbols_get() or ())
        if not broker_symbols:
            raise RuntimeError(f"Broker symbol inventory unavailable: {mt5.last_error()}")
        print("REAL_ORDER_API_USED", False, flush=True)
        print("COMPLETED_CANDLE_START_POSITION", 1, flush=True)

        for definition in replay.universe:
            canonical = definition.canonical_symbol
            broker_symbol = replay.resolve_symbol(canonical, broker_symbols)
            if broker_symbol is None:
                raise RuntimeError(f"Broker symbol unresolved: {canonical}")
            result = service.load(
                broker_symbol,
                TIMEFRAME,
                count=TARGET_CANDLE_COUNT,
                start_position=1,
            )
            print(
                "HISTORY", canonical, broker_symbol, result.returned_count,
                result.attempts, result.error_code, result.error_message,
                flush=True,
            )
            if not result.success:
                raise HistoryLoadError(result)
            symbol_info = mt5.symbol_info(broker_symbol)
            if symbol_info is None:
                raise RuntimeError(f"Broker metadata unavailable: {broker_symbol}")
            info = symbol_info._asdict()
            metadata[canonical] = {
                "canonical_symbol": canonical,
                "broker_symbol": broker_symbol,
                "asset_class": definition.asset_class,
                "digits": info["digits"],
                "point": info["point"],
                "trade_tick_size": info["trade_tick_size"],
                "trade_tick_value": info["trade_tick_value"],
                "trade_contract_size": info["trade_contract_size"],
                "volume_min": info["volume_min"],
                "volume_max": info["volume_max"],
                "volume_step": info["volume_step"],
                "spread": info["spread"],
            }
            history[canonical] = result

        evidence_boundary = max(
            item.candles[-1].time + replay.DURATIONS[replay.TIMEFRAME]
            for item in history.values()
        )
        snapshot = replay.replay(
            history_results=history,
            broker_metadata=metadata,
            as_of=evidence_boundary,
            config=replay_config(),
            target_count=TARGET_CANDLE_COUNT,
        )
        output = snapshot.to_dict()
        replay.write_json(output, JSON_PATH)
        print("JSON", JSON_PATH, flush=True)
        print("COMMON_CANDLES", output["replay_configuration"]["common_candle_count"], flush=True)
        for row in output["per_symbol_results"]:
            print("RESULT", row["canonical_symbol"], json.dumps(row, sort_keys=True), flush=True)
        print(
            "COMBINED",
            json.dumps(output["combined_independent_results"], sort_keys=True),
            flush=True,
        )
        print("REAL_ORDERS_SENT", False, flush=True)
        return output
    finally:
        adapter.shutdown()


if __name__ == "__main__":
    main()
