"""Generate Sprint 86 MTF evidence from verified Alpari MT5 history."""

from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.history import HistoryService
from mss.analysis.mtf_evidence_engine import HistoricalTimeframeLoader, MTFEvidenceEngine


TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")
SOURCE_PATH = Path("reports/MSS_Historical_Backtest_Context_v1.xlsx")
EXCEL_PATH = Path("reports/MSS_MTF_Context_v1.xlsx")
JSON_PATH = Path("reports/MSS_MTF_Context_v1.json")
REQUEST_COUNTS = {"M15": 30000, "H1": 12000, "H4": 5000, "D1": 2500}


def load_history(rows):
    if not TERMINAL_PATH.is_file():
        raise RuntimeError(f"Configured MT5 terminal does not exist: {TERMINAL_PATH}")
    mt5.shutdown()
    if not mt5.initialize(path=str(TERMINAL_PATH), timeout=120000):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    terminal = mt5.terminal_info()
    account = mt5.account_info()
    if terminal is None or account is None:
        error = mt5.last_error()
        mt5.shutdown()
        raise RuntimeError(f"MT5 terminal/account unavailable: {error}")
    maximum_decision = max(row["decision_time"] for row in rows)
    service = HistoryService(max_attempts=3, retry_delay=0.5)
    candle_data = {}
    symbols = {}
    try:
        for symbol in sorted({row["symbol"] for row in rows}):
            candle_data[symbol] = {}
            symbols[symbol] = {}
            for timeframe in MTFEvidenceEngine.TIMEFRAMES:
                mt5_timeframe = getattr(mt5, f"TIMEFRAME_{timeframe}")
                result = service.load(
                    symbol, mt5_timeframe, REQUEST_COUNTS[timeframe], start_position=1,
                )
                if not result.success:
                    raise RuntimeError(
                        f"{symbol} {timeframe} history failed: {result.diagnostic}"
                    )
                duration = HistoricalTimeframeLoader.DURATIONS[timeframe]
                candles = sorted(
                    (item for item in result.candles if item.time + duration <= maximum_decision),
                    key=lambda item: item.time,
                )
                candle_data[symbol][timeframe] = candles
                symbols[symbol].update({
                    "resolved_symbol": result.resolved_symbol,
                    f"{timeframe}_requested_count": result.requested_count,
                    f"{timeframe}_returned_count": result.returned_count,
                    f"{timeframe}_retained_count": len(candles),
                    f"{timeframe}_attempts": result.attempts,
                    f"{timeframe}_last_error": [result.error_code, result.error_message],
                })
        metadata = {
            "terminal_path": str(TERMINAL_PATH),
            "terminal_name": terminal.name,
            "terminal_build": terminal.build,
            "terminal_connected": bool(terminal.connected),
            "python_metatrader5_version": mt5.__version__,
            "python_metatrader5_module": mt5.__file__,
            "account_login": account.login,
            "account_server": account.server,
            "maximum_decision_time": maximum_decision.isoformat(),
            "symbols": symbols,
        }
        return candle_data, metadata
    finally:
        mt5.shutdown()


def main():
    engine = MTFEvidenceEngine()
    rows, validation = engine.load(SOURCE_PATH)
    if (validation["trade_count"], validation["closed_trade_count"], validation["unresolved_trade_count"]) != (170, 169, 1):
        raise RuntimeError(f"Unexpected validated population: {validation}")
    candle_data, metadata = load_history(rows)
    result = engine.run(SOURCE_PATH, candle_data, EXCEL_PATH, JSON_PATH, metadata)
    print("TOTAL_TRADES", result["data_validation"]["trade_count"])
    print("CLOSED_TRADES", result["data_validation"]["closed_trade_count"])
    print("UNRESOLVED_TRADES", result["data_validation"]["unresolved_trade_count"])
    for item in result["timeframe_availability"]:
        print("TIMEFRAME_AVAILABILITY", item["timeframe"], item["available_count"], item["availability_percent"])
    print("PRODUCTION_CHANGE_JUSTIFIED", result["production_change_justified"])
    return result


if __name__ == "__main__":
    main()
