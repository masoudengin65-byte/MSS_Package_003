"""Run Sprint 90 read-only multi-asset historical dataset preparation."""

from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.broker_clock import BrokerClock
from mss.adapters.mt5.history import HistoryService
from mss.analysis.multi_asset_dataset_builder import MultiAssetDatasetBuilder


TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")
EXCEL_PATH = Path("reports/MSS_Multi_Asset_Dataset_v1.xlsx")
JSON_PATH = Path("reports/MSS_Multi_Asset_Dataset_v1.json")
REQUEST_COUNTS = {"M15": 1000, "H1": 1000, "H4": 1000, "D1": 1000}


def unavailable_payload(broker_symbol, timeframe, message, error_code=0):
    return {
        "resolved_symbol": broker_symbol or "",
        "requested_count": REQUEST_COUNTS[timeframe],
        "returned_count": 0,
        "attempts": 0,
        "error_code": error_code,
        "error_message": message,
        "candles": [],
    }


def load_completed_history(builder):
    if not TERMINAL_PATH.is_file():
        raise RuntimeError(f"Configured MT5 terminal does not exist: {TERMINAL_PATH}")
    mt5.shutdown()
    if not mt5.initialize(path=str(TERMINAL_PATH), timeout=120000):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        broker_symbols = tuple(mt5.symbols_get() or ())
        if terminal is None or account is None or not broker_symbols:
            raise RuntimeError(f"MT5 terminal/account/symbol inventory unavailable: {mt5.last_error()}")

        service = HistoryService(max_attempts=3, retry_delay=0.5)
        history = {}
        resolved_symbols = {}
        for definition in builder.universe:
            canonical = definition.canonical_symbol
            broker_symbol = builder.resolve_symbol(canonical, broker_symbols)
            resolved_symbols[canonical] = broker_symbol
            history[canonical] = {}
            print("SYMBOL", canonical, broker_symbol or "NOT_AVAILABLE", flush=True)
            if broker_symbol is None:
                for timeframe in builder.TIMEFRAMES:
                    history[canonical][timeframe] = unavailable_payload(
                        "", timeframe, "No deterministic broker-symbol match was found.",
                    )
                continue
            if not mt5.symbol_select(broker_symbol, True):
                error = mt5.last_error() or (0, "Symbol selection failed")
                for timeframe in builder.TIMEFRAMES:
                    history[canonical][timeframe] = unavailable_payload(
                        broker_symbol, timeframe, str(error[1]), int(error[0]),
                    )
                continue
            for timeframe in builder.TIMEFRAMES:
                result = service.load(
                    broker_symbol,
                    getattr(mt5, f"TIMEFRAME_{timeframe}"),
                    REQUEST_COUNTS[timeframe],
                    start_position=1,
                )
                history[canonical][timeframe] = result
                print(
                    "HISTORY", canonical, broker_symbol, timeframe,
                    result.returned_count, result.attempts,
                    result.error_code, result.error_message, flush=True,
                )

        system_time = datetime.now().replace(microsecond=0)
        clock = BrokerClock()
        broker_times = []
        for broker_symbol in resolved_symbols.values():
            if broker_symbol:
                value = clock.now(broker_symbol)
                if value is not None:
                    broker_times.append(value.replace(microsecond=0))
        as_of = max(broker_times) if broker_times else system_time
        runtime_metadata = {
            "terminal_path": str(TERMINAL_PATH),
            "terminal_name": terminal.name,
            "terminal_build": terminal.build,
            "terminal_connected": bool(terminal.connected),
            "python_metatrader5_version": mt5.__version__,
            "python_metatrader5_module": mt5.__file__,
            "account_server": account.server,
            "broker_symbol_inventory_count": len(broker_symbols),
            "request_counts": REQUEST_COUNTS,
            "history_start_position": 1,
            "evidence_boundary_source": (
                "LATEST_RESOLVED_SYMBOL_TICK" if broker_times else "SYSTEM_CLOCK_FALLBACK"
            ),
            "broker_evidence_time": as_of.isoformat(),
            "system_time_at_capture": system_time.isoformat(),
            "broker_system_offset_seconds": (as_of - system_time).total_seconds(),
            "trading_operations_performed": 0,
        }
        return broker_symbols, history, as_of, runtime_metadata
    finally:
        mt5.shutdown()


def main():
    builder = MultiAssetDatasetBuilder()
    broker_symbols, history, as_of, runtime_metadata = load_completed_history(builder)
    result = builder.run(
        broker_symbols, history, as_of, EXCEL_PATH, JSON_PATH,
        runtime_metadata,
    )
    print("SUPPORTED_ASSETS", result["summary"]["supported_asset_count"])
    print("RESOLVED_ASSETS", result["summary"]["resolved_asset_count"])
    print("TIMEFRAME_SLICES", result["summary"]["timeframe_slice_count"])
    print("AVAILABLE_SLICES", result["summary"]["available_timeframe_slice_count"])
    print("CANDLE_RECORDS", result["summary"]["candle_record_count"])
    print("ISSUES", result["summary"]["data_quality_issue_count"])
    for row in result["coverage"]:
        print(
            "COVERAGE", row["canonical_symbol"], row["broker_symbol"],
            row["timeframe"], row["observed_candle_count"],
            row["first_candle_open_time"], row["last_candle_close_time"],
            row["missing_candle_interval_count"], row["quality_status"],
        )
    print("PRODUCTION_CHANGE_JUSTIFIED", result["production_change_justified"])
    return result


if __name__ == "__main__":
    main()
