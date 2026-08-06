"""Run Sprint 89 read-only multi-asset MT5 data validation."""

from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5

from mss.adapters.mt5.broker_clock import BrokerClock
from mss.adapters.mt5.history import HistoryService
from mss.analysis.multi_asset_registry import MultiAssetRegistry


TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")
EXCEL_PATH = Path("reports/MSS_Multi_Asset_Data_Validation.xlsx")
JSON_PATH = Path("reports/MSS_Multi_Asset_Data_Validation.json")
REQUEST_COUNTS = {"M15": 1000, "H1": 1000, "H4": 1000, "D1": 1000}


def unavailable_payload(resolved_symbol, timeframe, message, error_code=0):
    return {
        "resolved_symbol": resolved_symbol or "",
        "requested_count": REQUEST_COUNTS[timeframe],
        "returned_count": 0,
        "attempts": 0,
        "error_code": error_code,
        "error_message": message,
        "candles": [],
    }


def load_mt5_inputs(registry):
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
        for definition in registry.universe:
            canonical = definition.canonical_symbol
            resolved = registry.resolve_symbol(canonical, broker_symbols)
            print("SYMBOL_RESOLUTION", canonical, resolved or "NOT_AVAILABLE", flush=True)
            history[canonical] = {}
            if resolved is None:
                for timeframe in registry.TIMEFRAMES:
                    history[canonical][timeframe] = unavailable_payload(
                        "", timeframe, "No deterministic broker-symbol match was found.",
                    )
                continue
            info = mt5.symbol_info(resolved)
            if info is None:
                for timeframe in registry.TIMEFRAMES:
                    history[canonical][timeframe] = unavailable_payload(
                        resolved, timeframe, "Resolved broker symbol has no symbol_info record.",
                    )
                continue
            if not mt5.symbol_select(resolved, True):
                error = mt5.last_error() or (0, "Symbol selection failed")
                for timeframe in registry.TIMEFRAMES:
                    history[canonical][timeframe] = unavailable_payload(
                        resolved, timeframe, str(error[1]), int(error[0]),
                    )
                continue
            for timeframe in registry.TIMEFRAMES:
                print(
                    "HISTORY_REQUEST", canonical, resolved, timeframe,
                    REQUEST_COUNTS[timeframe], flush=True,
                )
                history[canonical][timeframe] = service.load(
                    resolved,
                    getattr(mt5, f"TIMEFRAME_{timeframe}"),
                    REQUEST_COUNTS[timeframe],
                    start_position=1,
                )
                result = history[canonical][timeframe]
                print(
                    "HISTORY_RESULT", canonical, timeframe, result.returned_count,
                    result.attempts, result.error_code, result.error_message, flush=True,
                )

        system_time = datetime.now().replace(microsecond=0)
        broker_times = []
        clock = BrokerClock()
        for definition in registry.universe:
            resolved = registry.resolve_symbol(definition.canonical_symbol, broker_symbols)
            if resolved:
                broker_time = clock.now(resolved)
                if broker_time is not None:
                    broker_times.append(broker_time.replace(microsecond=0))
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
    registry = MultiAssetRegistry()
    broker_symbols, history, as_of, runtime_metadata = load_mt5_inputs(registry)
    result = registry.run(
        broker_symbols, history, as_of, EXCEL_PATH, JSON_PATH, runtime_metadata,
    )
    print("TARGET_SYMBOLS", result["summary"]["target_symbol_count"])
    print("RESOLVED_SYMBOLS", result["summary"]["resolved_symbol_count"])
    print("AVAILABLE_TIMEFRAMES", result["summary"]["available_timeframe_count"])
    print("MISSING_TIMEFRAMES", result["summary"]["missing_timeframe_count"])
    for row in result["symbol_data_quality"]:
        print(
            "SYMBOL_QUALITY", row["canonical_symbol"], row["broker_symbol"],
            row["available_timeframe_count"], row["highest_severity"],
            row["overall_quality_status"],
        )
    for row in result["history_availability"]:
        print(
            "HISTORY", row["canonical_symbol"], row["timeframe"],
            row["requested_count"], row["returned_count"],
            row["availability_status"], row["first_candle_open_time"],
            row["last_candle_close_time"],
        )
    print("PRODUCTION_CHANGE_JUSTIFIED", result["production_change_justified"])
    return result


if __name__ == "__main__":
    main()
