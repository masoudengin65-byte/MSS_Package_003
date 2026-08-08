"""Run the Sprint 77 MT5 historical baseline without sending real orders."""

import json

import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.adapters.mt5.history import HistoryLoadError, HistoryService
from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.analysis.historical_backtest_report_engine import (
    HistoricalBacktestReportEngine,
)
from mss.domain.historical_backtest import (
    BacktestSymbolMetadata,
    HistoricalBacktestConfig,
)


SYMBOLS = ("EURUSD", "XAUUSD")
TIMEFRAME = mt5.TIMEFRAME_M15
TIMEFRAME_NAME = "M15"
CANDLE_COUNT = 10000


def main():
    adapter = MT5Adapter()
    connected, message = adapter.connect()
    if not connected:
        raise RuntimeError(f"MT5 connection failed: {message}")

    config = HistoricalBacktestConfig(
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
    history_service = HistoryService(max_attempts=3, retry_delay=0.25)
    results = []

    try:
        print("CONFIG", json.dumps(vars(config), sort_keys=True))
        print("COMPLETED_CANDLE_START_POSITION", 1)
        print("REAL_ORDER_API_USED", False)

        for symbol in SYMBOLS:
            history = history_service.load(
                symbol,
                TIMEFRAME,
                count=CANDLE_COUNT,
                start_position=1,
            )
            print("HISTORY", symbol, history.diagnostic)
            if not history.success:
                raise HistoryLoadError(history)

            symbol_info = mt5.symbol_info(history.resolved_symbol)
            metadata = BacktestSymbolMetadata(
                point=symbol_info.point,
                digits=symbol_info.digits,
                tick_size=symbol_info.trade_tick_size,
                tick_value=symbol_info.trade_tick_value,
                contract_size=symbol_info.trade_contract_size,
                volume_min=symbol_info.volume_min,
                volume_max=symbol_info.volume_max,
                volume_step=symbol_info.volume_step,
                spread_points=symbol_info.spread,
            )
            result = HistoricalBacktestEngine().run(
                symbol=history.resolved_symbol,
                timeframe=TIMEFRAME_NAME,
                candles=history.candles,
                config=config,
                metadata=metadata,
            )
            results.append(result)
            print("METRICS", symbol, json.dumps(vars(result.metrics), default=str, sort_keys=True))
            print(
                "DIAGNOSTICS",
                symbol,
                json.dumps(vars(result.diagnostics), default=str, sort_keys=True),
            )

        output = HistoricalBacktestReportEngine().build(results)
        print("OUTPUT", output)
        print("NO_LOOKAHEAD_RULE", "decision close -> next candle open")
        print("AMBIGUOUS_POLICY", config.ambiguous_policy)
        print("REAL_ORDERS_SENT", False)
        return results, output
    finally:
        adapter.shutdown()


if __name__ == "__main__":
    main()
