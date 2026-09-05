"""Freeze the preregistered four-year MT5 M15 dataset without analysis."""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Mapping


class FourYearMT5DatasetFreeze:
    VERSION = "MSS_SPRINT93_3A_FOUR_YEAR_MT5_DATASET_FREEZE_V1"
    TIMEFRAME_SECONDS = 900
    WARMUP_CANDLES = 500
    WINDOW_START_EPOCH = 1_630_454_400  # 2021-09-01T00:00:00Z
    WINDOW_END_EXCLUSIVE_EPOCH = 1_756_684_800  # 2025-09-01T00:00:00Z
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
    RATE_FIELDS = (
        "time", "open", "high", "low", "close", "tick_volume", "spread",
        "real_volume",
    )
    CONTRACT_FIELDS = (
        "name", "description", "path", "currency_base", "currency_profit",
        "currency_margin", "digits", "point", "trade_contract_size",
        "trade_tick_size", "trade_tick_value", "trade_tick_value_profit",
        "trade_tick_value_loss", "volume_min", "volume_step", "volume_max",
        "trade_calc_mode",
    )

    @staticmethod
    def _value(row: object, name: str) -> object:
        if isinstance(row, Mapping):
            return row[name]
        dtype = getattr(row, "dtype", None)
        names = getattr(dtype, "names", None)
        if names and name in names:
            return row[name]  # type: ignore[index]
        return getattr(row, name)

    @classmethod
    def normalize_rates(cls, rows: Iterable[object]) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        previous: int | None = None
        for source in rows:
            epoch = int(cls._value(source, "time"))
            if previous is not None and epoch <= previous:
                raise ValueError("bar epochs must be strictly increasing and unique")
            if epoch % cls.TIMEFRAME_SECONDS:
                raise ValueError("bar epoch is not M15 aligned")
            values = {
                name: cls._value(source, name) for name in cls.RATE_FIELDS
            }
            floats = {name: float(values[name]) for name in ("open", "high", "low", "close")}
            if not all(math.isfinite(value) for value in floats.values()):
                raise ValueError("OHLC values must be finite")
            if floats["high"] < max(floats["open"], floats["close"], floats["low"]):
                raise ValueError("bar high is inconsistent with OHLC values")
            if floats["low"] > min(floats["open"], floats["close"], floats["high"]):
                raise ValueError("bar low is inconsistent with OHLC values")
            integers = {
                name: int(values[name]) for name in ("tick_volume", "spread", "real_volume")
            }
            if any(value < 0 for value in integers.values()):
                raise ValueError("volume and spread values must be nonnegative")
            normalized.append({"time": epoch, **floats, **integers})
            previous = epoch
        return normalized

    @classmethod
    def select_window(cls, rows: Iterable[object]) -> list[dict[str, object]]:
        normalized = cls.normalize_rates(rows)
        performance = [
            row for row in normalized
            if cls.WINDOW_START_EPOCH <= int(row["time"]) < cls.WINDOW_END_EXCLUSIVE_EPOCH
        ]
        warmup = [row for row in normalized if int(row["time"]) < cls.WINDOW_START_EPOCH][-cls.WARMUP_CANDLES:]
        future = [row for row in normalized if int(row["time"]) >= cls.WINDOW_END_EXCLUSIVE_EPOCH]
        if future:
            raise ValueError("source contains a bar at or after the exclusive end")
        if len(warmup) != cls.WARMUP_CANDLES:
            raise ValueError("exactly 500 pre-window warmup candles are required")
        if not performance or int(performance[0]["time"]) != cls.WINDOW_START_EPOCH:
            raise ValueError("the first performance candle must equal the inclusive start")
        return [
            {**row, "performance_eligible": index >= cls.WARMUP_CANDLES}
            for index, row in enumerate(warmup + performance)
        ]

    @classmethod
    def normalize_contract(cls, info: object) -> dict[str, object]:
        result: dict[str, object] = {}
        for name in cls.CONTRACT_FIELDS:
            value = cls._value(info, name)
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"contract field {name} must be finite")
            result[name] = value
        for name in ("point", "trade_contract_size", "trade_tick_size", "volume_min", "volume_step", "volume_max"):
            if float(result[name]) <= 0:
                raise ValueError(f"contract field {name} must be positive")
        return result

    @staticmethod
    def _canonical_line(value: object) -> bytes:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

    @classmethod
    def write_symbol(cls, path: Path, rows: Iterable[object]) -> dict[str, object]:
        selected = cls.select_window(rows)
        if path.exists():
            raise FileExistsError(f"refusing to overwrite frozen dataset: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        digest = hashlib.sha256()
        try:
            with temporary.open("xb") as handle:
                for row in selected:
                    line = cls._canonical_line(row)
                    handle.write(line)
                    digest.update(line)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        performance_count = sum(bool(row["performance_eligible"]) for row in selected)
        gaps = [
            {
                "after_epoch": int(left["time"]),
                "before_epoch": int(right["time"]),
                "missing_m15_slots": (int(right["time"]) - int(left["time"])) // cls.TIMEFRAME_SECONDS - 1,
            }
            for left, right in zip(selected, selected[1:])
            if int(right["time"]) - int(left["time"]) > cls.TIMEFRAME_SECONDS
        ]
        return {
            "path": path.name,
            "sha256": digest.hexdigest(),
            "row_count": len(selected),
            "warmup_row_count": cls.WARMUP_CANDLES,
            "performance_row_count": performance_count,
            "first_epoch": selected[0]["time"],
            "first_performance_epoch": selected[cls.WARMUP_CANDLES]["time"],
            "last_epoch": selected[-1]["time"],
            "gap_count": len(gaps),
            "missing_m15_slot_count": sum(int(gap["missing_m15_slots"]) for gap in gaps),
            "gaps": gaps,
        }

    @classmethod
    def build_manifest(cls, symbols: list[dict[str, object]]) -> dict[str, object]:
        expected = [canonical for canonical, _broker, _asset_class in cls.UNIVERSE]
        actual = [str(row["canonical_symbol"]) for row in symbols]
        if actual != expected:
            raise ValueError("frozen symbol order differs from the preregistered core universe")
        return {
            "schema_version": cls.VERSION,
            "mode": "RAW_DATASET_FREEZE_ONLY_NO_STRATEGY_NO_REPLAY",
            "window": {
                "start_utc_inclusive": "2021-09-01T00:00:00Z",
                "end_utc_exclusive": "2025-09-01T00:00:00Z",
                "timeframe": "M15",
                "warmup_candles": cls.WARMUP_CANDLES,
            },
            "timezone_contract": {
                "request_datetime_timezone": "UTC_AWARE",
                "returned_bar_epoch_domain": "UTC_PER_OFFICIAL_METATRADER5_API",
                "manual_broker_offset_applied": False,
                "local_timezone_conversion_applied": False,
            },
            "symbols": symbols,
            "audit": {
                "strategy_or_replay_run": False,
                "performance_metrics_computed": False,
                "real_orders_sent": False,
                "sprint93_2b_forward_accessed_or_modified": False,
            },
        }

    @classmethod
    def write_manifest(cls, path: Path, symbols: list[dict[str, object]]) -> str:
        if path.exists():
            raise FileExistsError(f"refusing to overwrite frozen manifest: {path}")
        payload = cls.build_manifest(symbols)
        encoded = json.dumps(
            payload, indent=2, sort_keys=True, allow_nan=False,
        ).encode("utf-8") + b"\n"
        temporary = path.with_name(path.name + ".tmp")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with temporary.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def utc(epoch: int) -> datetime:
        return datetime.fromtimestamp(epoch, timezone.utc)

    @classmethod
    def acquisition_ranges(cls, lookback_days: int = 45, chunk_days: int = 180) -> list[tuple[datetime, datetime]]:
        """Return non-overlapping inclusive MT5 ranges below terminal max-bars limits."""
        if lookback_days <= 0 or chunk_days <= 0:
            raise ValueError("acquisition range sizes must be positive")
        cursor = cls.utc(cls.WINDOW_START_EPOCH) - timedelta(days=lookback_days)
        exclusive_end = cls.utc(cls.WINDOW_END_EXCLUSIVE_EPOCH)
        ranges: list[tuple[datetime, datetime]] = []
        while cursor < exclusive_end:
            next_cursor = min(cursor + timedelta(days=chunk_days), exclusive_end)
            ranges.append((cursor, next_cursor - timedelta(seconds=1)))
            cursor = next_cursor
        return ranges
