"""Generate Sprint 87 Smart Money evidence from verified Alpari M15 history."""

from datetime import timedelta
from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.history import HistoryService
from mss.analysis.mtf_evidence_engine import HistoricalTimeframeLoader
from mss.analysis.smart_money_evidence_engine import SmartMoneyEvidenceEngine


TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")
SOURCE_PATH = Path("reports/MSS_Historical_Backtest_Context_v1.xlsx")
EXCEL_PATH = Path("reports/MSS_SmartMoney_Evidence_v1.xlsx")
JSON_PATH = Path("reports/MSS_SmartMoney_Evidence_v1.json")
REQUEST_COUNT = 30000
HISTORY_BUFFER_DAYS = 60


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
    minimum_history = min(row["decision_time"] for row in rows) - timedelta(days=HISTORY_BUFFER_DAYS)
    duration = HistoricalTimeframeLoader.DURATIONS["M15"]
    service = HistoryService(max_attempts=3, retry_delay=0.5)
    candle_data = {}
    symbols = {}
    try:
        for symbol in sorted({row["symbol"] for row in rows}):
            result = service.load(symbol, mt5.TIMEFRAME_M15, REQUEST_COUNT, start_position=1)
            if not result.success:
                raise RuntimeError(f"{symbol} M15 history failed: {result.diagnostic}")
            candles = sorted(
                (
                    item for item in result.candles
                    if item.time >= minimum_history
                    and item.time + duration <= maximum_decision
                ),
                key=lambda item: item.time,
            )
            if not candles or candles[0].time > min(row["decision_time"] for row in rows) - timedelta(days=14):
                raise RuntimeError(f"{symbol} M15 history does not include the required decision-time lookback")
            candle_data[symbol] = {"M15": candles}
            symbols[symbol] = {
                "resolved_symbol": result.resolved_symbol,
                "requested_count": result.requested_count,
                "returned_count": result.returned_count,
                "retained_count": len(candles), "attempts": result.attempts,
                "last_error": [result.error_code, result.error_message],
            }
        metadata = {
            "terminal_path": str(TERMINAL_PATH), "terminal_name": terminal.name,
            "terminal_build": terminal.build, "terminal_connected": bool(terminal.connected),
            "python_metatrader5_version": mt5.__version__,
            "python_metatrader5_module": mt5.__file__,
            "account_login": account.login, "account_server": account.server,
            "minimum_history_time": minimum_history.isoformat(),
            "maximum_decision_time": maximum_decision.isoformat(), "symbols": symbols,
        }
        return candle_data, metadata
    finally:
        mt5.shutdown()


def main():
    engine = SmartMoneyEvidenceEngine()
    rows, validation = engine.load(SOURCE_PATH)
    population = (
        validation["trade_count"], validation["closed_trade_count"],
        validation["unresolved_trade_count"],
    )
    if population != (170, 169, 1):
        raise RuntimeError(f"Unexpected validated population: {validation}")
    candles, metadata = load_history(rows)
    result = engine.run(SOURCE_PATH, candles, EXCEL_PATH, JSON_PATH, metadata)
    print("TOTAL_TRADES", result["data_validation"]["trade_count"])
    print("CLOSED_TRADES", result["data_validation"]["closed_trade_count"])
    print("UNRESOLVED_TRADES", result["data_validation"]["unresolved_trade_count"])
    for item in result["availability"]:
        if item["row_type"] == "category":
            print("EVIDENCE_AVAILABILITY", item["category"], item["available_count"], item["availability_percent"])
    print("PRODUCTION_CHANGE_JUSTIFIED", result["production_change_justified"])
    return result


if __name__ == "__main__":
    main()
