"""Compare frozen Alpari and FIBO OHLC patterns without replay or execution."""

from __future__ import annotations

import json
import math
from pathlib import Path

MAPPINGS = (
    ("EURUSD", "EURUSD"),
    ("XAUUSD", "XAUUSD"),
    ("BTCUSD", "BTC"),
    ("ETHUSD", "ETH"),
)
BAR_SECONDS = 15 * 60


def _read_rates(path: Path) -> dict[int, dict[str, object]]:
    rows: dict[int, dict[str, object]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if not row.get("performance_eligible", True):
                continue
            timestamp = int(row["time"])
            if timestamp in rows:
                raise ValueError(f"Duplicate timestamp in {path.name}: {timestamp}")
            rows[timestamp] = row
    if not rows:
        raise ValueError(f"No eligible rates in {path.name}")
    return rows


def _quantiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    return {str(q): ordered[round((len(ordered) - 1) * q)] for q in (0.05, 0.5, 0.95)}


def _gap_boundaries(rows: dict[int, dict[str, object]]) -> set[tuple[int, int]]:
    timestamps = sorted(rows)
    return {
        (previous, current)
        for previous, current in zip(timestamps, timestamps[1:])
        if current - previous > BAR_SECONDS
    }


def _comparison_row(
    frozen_symbol: str,
    fibo_symbol: str,
    frozen: dict[int, dict[str, object]],
    fibo: dict[int, dict[str, object]],
) -> dict[str, object]:
    common = sorted(frozen.keys() & fibo.keys())
    open_return_differences: list[float] = []
    close_return_differences: list[float] = []
    high_low_range_differences: list[float] = []
    for timestamp in common:
        left, right = frozen[timestamp], fibo[timestamp]
        high_low_range_differences.append(
            math.log(float(left["high"]) / float(left["low"]))
            - math.log(float(right["high"]) / float(right["low"]))
        )
        previous = timestamp - BAR_SECONDS
        if previous in frozen and previous in fibo:
            open_return_differences.append(
                math.log(float(left["open"]) / float(frozen[previous]["open"]))
                - math.log(float(right["open"]) / float(fibo[previous]["open"]))
            )
            close_return_differences.append(
                math.log(float(left["close"]) / float(frozen[previous]["close"]))
                - math.log(float(right["close"]) / float(fibo[previous]["close"]))
            )
    frozen_gaps, fibo_gaps = _gap_boundaries(frozen), _gap_boundaries(fibo)
    shared_gaps = frozen_gaps & fibo_gaps
    minimum_gap_count = min(len(frozen_gaps), len(fibo_gaps))
    return {
        "frozen_broker_symbol": frozen_symbol,
        "fibo_group_symbol": fibo_symbol,
        "frozen_timestamp_count": len(frozen),
        "fibo_timestamp_count": len(fibo),
        "matched_timestamp_count": len(common),
        "matched_timestamp_coverage": len(common) / min(len(frozen), len(fibo)),
        "unmatched_frozen_timestamp_count": len(frozen) - len(common),
        "unmatched_fibo_timestamp_count": len(fibo) - len(common),
        "return_comparison_timestamp_count": len(open_return_differences),
        "open_return_difference_quantiles": _quantiles(open_return_differences),
        "close_return_difference_quantiles": _quantiles(close_return_differences),
        "high_low_range_difference_quantiles": _quantiles(high_low_range_differences),
        "frozen_gap_boundary_count": len(frozen_gaps),
        "fibo_gap_boundary_count": len(fibo_gaps),
        "shared_gap_boundary_count": len(shared_gaps),
        "gap_boundary_agreement_coverage": (
            len(shared_gaps) / minimum_gap_count if minimum_gap_count else None
        ),
    }


def build_comparison(
    root: Path, frozen_root: Path | None = None, fibo_root: Path | None = None
) -> dict[str, object]:
    frozen_root = frozen_root or root / "historical_data" / "sprint93_3a_v5"
    fibo_root = fibo_root or root / "historical_data" / "sprint93_3f_fibo_candidate"
    symbols = []
    for frozen_symbol, fibo_symbol in MAPPINGS:
        frozen = _read_rates(frozen_root / f"{frozen_symbol}_M15.jsonl")
        fibo = _read_rates(fibo_root / f"{fibo_symbol}_M15.jsonl")
        symbols.append(_comparison_row(frozen_symbol, fibo_symbol, frozen, fibo))
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_PRICE_PATTERN_COMPARISON_V1",
        "purpose": "Timestamp and OHLC pattern comparison only; no strategy, replay, order, or performance result",
        "method": {
            "timeframe": "M15",
            "timestamp_matching": "exact UTC epoch equality only",
            "return_definition": "log(current price / immediately previous M15 price) within each source, then frozen minus FIBO",
            "range_definition": "log(high / low) within each source, then frozen minus FIBO at exact common timestamps",
            "gap_definition": "adjacent observed timestamps separated by more than one M15 interval",
            "no_interpolation": True,
            "no_resampling_across_market_closures": True,
        },
        "symbols": symbols,
        "interpretation_boundary": {
            "allowed": "State price-pattern consistency or discrepancy only",
            "cannot_establish": [
                "historical Alpari trading sessions",
                "historical Alpari commission or swap",
                "historical Alpari execution quality",
                "broker-accurate net profit",
                "production readiness",
            ],
        },
        "safety": {
            "raw_data_modified": False,
            "comparison_run": True,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
