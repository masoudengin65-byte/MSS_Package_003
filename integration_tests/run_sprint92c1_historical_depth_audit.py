"""Run the read-only Sprint 92C.1 MT5 historical-depth audit."""

import json
import time
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.historical_depth_audit import HistoricalDepthAudit


ROOT = Path(__file__).resolve().parents[1]
TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")
OUTPUT = ROOT / "reports" / "MSS_Sprint92C1_Historical_Depth_Audit.json"
V2_SOURCE = ROOT / "reports" / "MSS_Multi_Asset_Historical_Replay_v2.json"


def fetch(broker_symbol, timeframe, count):
    rates = mt5.copy_rates_from_pos(broker_symbol, getattr(mt5, f"TIMEFRAME_{timeframe}"), 1, count)
    error = mt5.last_error()
    return rates, {"code": int(error[0]), "message": str(error[1])} if error else None


def completed_boundary(broker_symbol, timeframe):
    current = mt5.copy_rates_from_pos(broker_symbol, getattr(mt5, f"TIMEFRAME_{timeframe}"), 0, 1)
    if current is None or len(current) != 1:
        raise RuntimeError(f"Current-bar boundary unavailable for {broker_symbol} {timeframe}: {mt5.last_error()}")
    return int(current[0]["time"])


def main():
    if not TERMINAL_PATH.is_file():
        raise RuntimeError(f"MT5 terminal missing: {TERMINAL_PATH}")
    mt5.shutdown()
    if not mt5.initialize(path=str(TERMINAL_PATH), timeout=120_000):
        raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
    audit = HistoricalDepthAudit()
    results = []
    stability = {}
    capture_epoch = int(time.time())
    try:
        for canonical, broker, asset_class in audit.UNIVERSE:
            if mt5.symbol_info(broker) is None or not mt5.symbol_select(broker, True):
                raise RuntimeError(f"Required broker symbol unavailable: {canonical} -> {broker}: {mt5.last_error()}")
            for timeframe in audit.TIMEFRAME_SECONDS:
                print("DISCOVER", canonical, broker, timeframe, flush=True)
                boundary_epoch = completed_boundary(broker, timeframe)
                result, maximum_rates = audit.progressive_discovery(
                    fetch, canonical, broker, asset_class, timeframe, boundary_epoch,
                )
                results.append(result)
                print("DEPTH", canonical, timeframe, result["returned_candle_count"], result["stop_reason"], flush=True)
                if timeframe == "M15" and maximum_rates:
                    second_raw, error = fetch(broker, timeframe, len(maximum_rates))
                    second = audit.completed_candles(second_raw if second_raw is not None else [], timeframe, boundary_epoch)
                    stability[canonical] = {
                        **audit.stability(maximum_rates, second),
                        "second_request_count": len(maximum_rates), "second_request_error": error,
                    }
    finally:
        mt5.shutdown()

    v2 = json.loads(V2_SOURCE.read_text(encoding="utf-8"))
    exposed = {row["canonical_symbol"]: row for row in v2["source_windows"]}
    m15 = {row["canonical_symbol"]: row for row in results if row["timeframe"] == "M15"}
    payload = {
        "schema_version": "MSS_SPRINT92C1_HISTORICAL_DEPTH_AUDIT_V1",
        "mode": "DATA_AVAILABILITY_AUDIT_ONLY",
        "generated_as_of_utc": audit._iso(capture_epoch),
        "methodology": {
            "source": "ALPARI_MT5_READ_ONLY_COPY_RATES_FROM_POS",
            "history_start_position": 1,
            "completed_candle_rule": "start_position=1 and candle_open_epoch + timeframe_seconds <= broker current-bar open boundary for the same symbol/timeframe",
            "request_sizes_by_timeframe": {key: list(value) for key, value in audit.REQUEST_SIZES.items()},
            "stopping_rules": ["RETURNED_FEWER_THAN_REQUESTED", "OLDEST_TIMESTAMP_NOT_MOVING", "RETRIEVAL_ERROR", "PROBE_CEILING_REACHED"],
            "depth_thresholds_m15": {"DEEP_HISTORY": ">=30000", "MODERATE_HISTORY": "10000-29999", "LIMITED_HISTORY": "<10000"},
            "gap_policy": "Calendar-agnostic interval gaps reported without imputation or automatic bad-data classification.",
            "strategy_or_replay_run": False, "trading_operations_performed": 0,
        },
        "universe": [
            {"canonical_symbol": canonical, "broker_symbol": broker, "asset_class": asset_class}
            for canonical, broker, asset_class in audit.UNIVERSE
        ],
        "timeframes": list(audit.TIMEFRAME_SECONDS),
        "depth_results": results,
        "m15_summary": [{
            "canonical_symbol": symbol,
            "broker_symbol": row["broker_symbol"], "asset_class": row["asset_class"],
            "available_candles": row["returned_candle_count"],
            "exact_depth_known": row["broker_depth_limit_reached"],
            "oldest_timestamp": row["oldest_candle_open_timestamp"],
            "newest_timestamp": row["newest_completed_candle_open_timestamp"],
            "approximate_months": row["approximate_duration_months"],
            "approximate_years": row["approximate_duration_years"],
            "supports_20000": row["supports_at_least_20000_m15"],
            "supports_30000": row["supports_at_least_30000_m15"],
            "supports_50000": row["supports_at_least_50000_m15"],
            "classification": row["depth_classification"],
            "stability": stability.get(symbol, {}).get("status", "NOT_AVAILABLE"),
        } for symbol, row in m15.items()],
        "m15_stability": stability,
        "research_suitability": {symbol: row["depth_classification"] for symbol, row in m15.items()},
        "proposed_future_dataset_split": {
            "method": "CHRONOLOGICAL_NO_SHUFFLE",
            "current_v2_period_status": "RESEARCH_EXPOSED_NOT_TRUE_OOS",
            "current_v2_windows": exposed,
            "proposal": {
                "development": "Oldest available completed M15 history before the validation boundary; target approximately 60% of a future frozen pre-OOS dataset.",
                "validation": "Chronologically following development segment; target approximately 20%; must remain before the true-OOS boundary.",
                "true_out_of_sample": "Newest approximately 20%, frozen only after sufficient candles strictly later than each symbol's v2 last close have accumulated and before any analysis of that segment.",
            },
            "important_limitation": "March-August 2026 v2 history has already been analyzed extensively and cannot be relabeled as untouched OOS.",
        },
        "crypto_specific_audit": {
            symbol: [row for row in results if row["canonical_symbol"] == symbol]
            for symbol in ("BTCUSD", "ETHUSD")
        },
        "limitations": [
            "Accessible depth reflects this broker account, terminal history configuration, and capture time; it is not a universal market-data bound.",
            "A PROBE_CEILING_REACHED result is a lower bound rather than an exact maximum.",
            "Calendar-agnostic gap counts include legitimate market closures and session breaks.",
            "Recent completed bars may change later because of broker corrections or backfills; M15 duplicate retrieval is the bounded stability check.",
            "No common crypto/forex start date is imposed.",
        ],
        "acceptance": {
            "all_32_symbol_timeframes_available": len(results) == 32 and all(row["returned_candle_count"] > 0 for row in results),
            "all_m15_stability_checks_completed": len(stability) == 8,
            "no_strategy_or_replay_run": True,
            "no_trading_operations": True,
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print("WROTE", OUTPUT)


if __name__ == "__main__":
    main()
