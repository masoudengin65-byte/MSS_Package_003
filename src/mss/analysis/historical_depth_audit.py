"""Read-only historical depth and candle-integrity audit helpers."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone


class HistoricalDepthAudit:
    REQUEST_SIZES = {
        "M15": (1_000, 5_000, 10_000, 20_000, 50_000, 100_000),
        "H1": (1_000, 5_000, 10_000, 20_000, 50_000),
        "H4": (1_000, 5_000, 10_000, 20_000),
        "D1": (1_000, 5_000, 10_000),
    }
    TIMEFRAME_SECONDS = {"M15": 900, "H1": 3_600, "H4": 14_400, "D1": 86_400}
    UNIVERSE = (
        ("EURUSD", "EURUSD", "FOREX"),
        ("GBPUSD", "GBPUSD", "FOREX"),
        ("USDJPY", "USDJPY", "FOREX"),
        ("AUDUSD", "AUDUSD", "FOREX"),
        ("USDCAD", "USDCAD", "FOREX"),
        ("XAUUSD", "XAUUSD", "METAL"),
        ("BTCUSD", "BITCOIN", "CRYPTO"),
        ("ETHUSD", "ETHEREUM", "CRYPTO"),
    )

    @staticmethod
    def _value(row, field):
        try:
            return row[field]
        except (KeyError, TypeError, ValueError, IndexError):
            return getattr(row, field)

    @classmethod
    def completed_candles(cls, rates, timeframe, as_of_epoch):
        duration = cls.TIMEFRAME_SECONDS[timeframe]
        return [row for row in rates if int(cls._value(row, "time")) + duration <= as_of_epoch]

    @classmethod
    def candle_hash(cls, rates):
        rows = []
        for row in rates:
            rows.append([
                int(cls._value(row, "time")),
                float(cls._value(row, "open")), float(cls._value(row, "high")),
                float(cls._value(row, "low")), float(cls._value(row, "close")),
                int(cls._value(row, "tick_volume")), int(cls._value(row, "spread")),
                int(cls._value(row, "real_volume")),
            ])
        encoded = json.dumps(rows, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def depth_classification(m15_count):
        if m15_count >= 30_000:
            return "DEEP_HISTORY"
        if m15_count >= 10_000:
            return "MODERATE_HISTORY"
        return "LIMITED_HISTORY"

    @classmethod
    def request_sizes(cls, timeframe):
        if isinstance(cls.REQUEST_SIZES, dict):
            return cls.REQUEST_SIZES[timeframe]
        return cls.REQUEST_SIZES

    @classmethod
    def integrity(cls, rates, timeframe, as_of_epoch):
        duration = cls.TIMEFRAME_SECONDS[timeframe]
        times = [int(cls._value(row, "time")) for row in rates]
        duplicate_count = len(times) - len(set(times))
        invalid_ohlc = nonfinite = negative_spread = negative_volume = future = 0
        for row in rates:
            prices = [float(cls._value(row, field)) for field in ("open", "high", "low", "close")]
            if not all(math.isfinite(value) for value in prices):
                nonfinite += 1
            elif prices[2] > min(prices[0], prices[1], prices[3]) or prices[1] < max(prices[0], prices[2], prices[3]):
                invalid_ohlc += 1
            if int(cls._value(row, "spread")) < 0:
                negative_spread += 1
            if int(cls._value(row, "tick_volume")) < 0 or int(cls._value(row, "real_volume")) < 0:
                negative_volume += 1
            if int(cls._value(row, "time")) + duration > as_of_epoch:
                future += 1
        gaps = []
        for previous, current in zip(times, times[1:]):
            delta = current - previous
            if delta > duration:
                gaps.append({
                    "previous_open_epoch": previous, "next_open_epoch": current,
                    "elapsed_seconds": delta, "implied_missing_intervals": max(0, delta // duration - 1),
                })
        return {
            "chronological_order": times == sorted(times),
            "strictly_increasing_timestamps": all(left < right for left, right in zip(times, times[1:])),
            "duplicate_timestamp_count": duplicate_count,
            "invalid_ohlc_count": invalid_ohlc,
            "nonfinite_price_count": nonfinite,
            "negative_spread_count": negative_spread,
            "negative_volume_count": negative_volume,
            "future_candle_count": future,
            "gap_event_count": len(gaps),
            "implied_missing_interval_count": sum(row["implied_missing_intervals"] for row in gaps),
            "largest_gap_seconds": max((row["elapsed_seconds"] for row in gaps), default=0),
            "gap_policy": "CALENDAR_AGNOSTIC; NO_IMPUTATION; GAPS_ARE_NOT_AUTOMATICALLY_BAD_DATA",
        }

    @staticmethod
    def _iso(epoch):
        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    @classmethod
    def progressive_discovery(cls, fetch, canonical_symbol, broker_symbol, asset_class, timeframe, as_of_epoch):
        probes = []
        maximum_rates = []
        previous_oldest = None
        stop_reason = "PROBE_CEILING_REACHED"
        depth_limit_reached = False
        error = None
        for requested in cls.request_sizes(timeframe):
            rates, error = fetch(broker_symbol, timeframe, requested)
            if rates is None:
                probes.append({"requested_count": requested, "raw_returned_count": 0, "completed_returned_count": 0, "error": error})
                stop_reason = "RETRIEVAL_ERROR"
                break
            completed = cls.completed_candles(rates, timeframe, as_of_epoch)
            oldest = int(cls._value(completed[0], "time")) if completed else None
            newest = int(cls._value(completed[-1], "time")) if completed else None
            probes.append({
                "requested_count": requested, "raw_returned_count": len(rates),
                "completed_returned_count": len(completed),
                "oldest_open_timestamp": cls._iso(oldest) if oldest is not None else None,
                "newest_open_timestamp": cls._iso(newest) if newest is not None else None,
                "error": error,
            })
            if completed:
                maximum_rates = completed
            if len(completed) < requested:
                stop_reason = "RETURNED_FEWER_THAN_REQUESTED"
                depth_limit_reached = True
                break
            if previous_oldest is not None and oldest >= previous_oldest:
                stop_reason = "OLDEST_TIMESTAMP_NOT_MOVING"
                depth_limit_reached = True
                break
            previous_oldest = oldest
        count = len(maximum_rates)
        oldest = int(cls._value(maximum_rates[0], "time")) if maximum_rates else None
        newest = int(cls._value(maximum_rates[-1], "time")) if maximum_rates else None
        duration_seconds = newest - oldest + cls.TIMEFRAME_SECONDS[timeframe] if count else 0
        result = {
            "canonical_symbol": canonical_symbol, "broker_symbol": broker_symbol,
            "asset_class": asset_class, "timeframe": timeframe,
            "requested_maximum": probes[-1]["requested_count"] if probes else 0,
            "returned_candle_count": count,
            "total_available_candles": count if depth_limit_reached else None,
            "availability_lower_bound": count,
            "oldest_candle_open_timestamp": cls._iso(oldest) if oldest is not None else None,
            "newest_completed_candle_open_timestamp": cls._iso(newest) if newest is not None else None,
            "newest_candle_close_timestamp": cls._iso(newest + cls.TIMEFRAME_SECONDS[timeframe]) if newest is not None else None,
            "completed_candle_boundary_timestamp": cls._iso(as_of_epoch),
            "historical_duration_seconds": duration_seconds,
            "approximate_duration_days": round(duration_seconds / 86_400, 6),
            "approximate_duration_months": round(duration_seconds / (86_400 * 30.436875), 6),
            "approximate_duration_years": round(duration_seconds / (86_400 * 365.2425), 6),
            "broker_depth_limit_reached": depth_limit_reached,
            "stop_reason": stop_reason,
            "data_retrieval_status": "AVAILABLE" if count and depth_limit_reached else "AVAILABLE_LOWER_BOUND" if count else "UNAVAILABLE",
            "probe_results": probes,
            "integrity": cls.integrity(maximum_rates, timeframe, as_of_epoch) if count else None,
            "ohlc_sha256": cls.candle_hash(maximum_rates) if count else None,
            "supports_at_least_20000_m15": count >= 20_000 if timeframe == "M15" else None,
            "supports_at_least_30000_m15": count >= 30_000 if timeframe == "M15" else None,
            "supports_at_least_50000_m15": count >= 50_000 if timeframe == "M15" else None,
            "depth_classification": cls.depth_classification(count) if timeframe == "M15" else None,
            "retrieval_error": error,
        }
        return result, maximum_rates

    @classmethod
    def stability(cls, first_rates, second_rates):
        first_times = [int(cls._value(row, "time")) for row in first_rates]
        second_times = [int(cls._value(row, "time")) for row in second_rates]
        comparison = {
            "first_count": len(first_rates), "second_count": len(second_rates),
            "first_timestamp": cls._iso(first_times[0]) if first_times else None,
            "second_first_timestamp": cls._iso(second_times[0]) if second_times else None,
            "last_timestamp": cls._iso(first_times[-1]) if first_times else None,
            "second_last_timestamp": cls._iso(second_times[-1]) if second_times else None,
            "first_ohlc_sha256": cls.candle_hash(first_rates) if first_rates else None,
            "second_ohlc_sha256": cls.candle_hash(second_rates) if second_rates else None,
        }
        comparison["status"] = "STABLE" if (
            comparison["first_count"] == comparison["second_count"]
            and comparison["first_timestamp"] == comparison["second_first_timestamp"]
            and comparison["last_timestamp"] == comparison["second_last_timestamp"]
            and comparison["first_ohlc_sha256"] == comparison["second_ohlc_sha256"]
        ) else "UNSTABLE"
        return comparison
