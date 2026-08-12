"""Deterministic M15 dataset partitioning and OOS quarantine helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from mss.analysis.historical_depth_audit import HistoricalDepthAudit


class ExtendedDatasetFreeze:
    """Freeze a fixed history without invoking strategy or performance logic."""

    DATASET_CANDLES = 50_000
    DEVELOPMENT_CANDLES = 30_000
    VALIDATION_CANDLES = 10_000
    TIMEFRAME = "M15"

    @staticmethod
    def parse_utc(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())

    @classmethod
    def _slice_manifest(cls, name, rates, analysis_access):
        count = len(rates)
        first = int(HistoricalDepthAudit._value(rates[0], "time")) if count else None
        last = int(HistoricalDepthAudit._value(rates[-1], "time")) if count else None
        return {
            "slice": name,
            "candle_count": count,
            "first_candle_open_timestamp": HistoricalDepthAudit._iso(first) if first is not None else None,
            "last_candle_open_timestamp": HistoricalDepthAudit._iso(last) if last is not None else None,
            "last_candle_close_timestamp": (
                HistoricalDepthAudit._iso(last + HistoricalDepthAudit.TIMEFRAME_SECONDS[cls.TIMEFRAME])
                if last is not None else None
            ),
            "ohlcv_sha256": HistoricalDepthAudit.candle_hash(rates),
            "analysis_access": analysis_access,
        }

    @classmethod
    def freeze_symbol(cls, rates, source_window, completed_boundary_epoch):
        if len(rates) != cls.DATASET_CANDLES:
            raise ValueError(f"Expected exactly {cls.DATASET_CANDLES} candles, received {len(rates)}")
        integrity = HistoricalDepthAudit.integrity(rates, cls.TIMEFRAME, completed_boundary_epoch)
        if not integrity["strictly_increasing_timestamps"]:
            raise ValueError("Dataset timestamps must be strictly increasing")
        if any(integrity[key] for key in (
            "duplicate_timestamp_count", "invalid_ohlc_count", "nonfinite_price_count",
            "negative_spread_count", "negative_volume_count", "future_candle_count",
        )):
            raise ValueError("Dataset failed candle-integrity requirements")

        development = rates[:cls.DEVELOPMENT_CANDLES]
        validation_start = cls.DEVELOPMENT_CANDLES
        validation_end = validation_start + cls.VALIDATION_CANDLES
        validation = rates[validation_start:validation_end]
        quarantine = rates[validation_end:]

        exposed_first = cls.parse_utc(source_window["first_candle_open_time"])
        exposed_close = cls.parse_utc(source_window["last_candle_close_time"])
        research_exposed = [
            row for row in quarantine
            if exposed_first <= int(HistoricalDepthAudit._value(row, "time")) < exposed_close
        ]
        true_oos = [
            row for row in quarantine
            if int(HistoricalDepthAudit._value(row, "time")) >= exposed_close
        ]
        unclassified = [
            row for row in quarantine
            if int(HistoricalDepthAudit._value(row, "time")) < exposed_first
        ]
        if unclassified:
            raise ValueError("The fixed development/validation boundary leaves pre-exposure quarantine candles")
        if len(research_exposed) + len(true_oos) != len(quarantine):
            raise ValueError("Quarantine partition is incomplete")

        slices = [
            cls._slice_manifest("DEVELOPMENT", development, "ANALYSIS_ALLOWED_FUTURE_SPRINT"),
            cls._slice_manifest("VALIDATION", validation, "ANALYSIS_ALLOWED_FUTURE_SPRINT"),
            cls._slice_manifest("RESEARCH_EXPOSED_QUARANTINE", research_exposed, "QUARANTINED_ALREADY_EXPOSED"),
            cls._slice_manifest("TRUE_OOS_ACCRUAL", true_oos, "FROZEN_NO_ANALYSIS"),
        ]
        all_times = [int(HistoricalDepthAudit._value(row, "time")) for row in rates]
        return {
            "canonical_symbol": source_window["canonical_symbol"],
            "broker_symbol": source_window["broker_symbol"],
            "asset_class": source_window["asset_class"],
            "timeframe": cls.TIMEFRAME,
            "frozen_candle_count": len(rates),
            "full_dataset_sha256": HistoricalDepthAudit.candle_hash(rates),
            "first_candle_open_timestamp": HistoricalDepthAudit._iso(all_times[0]),
            "last_candle_open_timestamp": HistoricalDepthAudit._iso(all_times[-1]),
            "completed_candle_boundary_timestamp": HistoricalDepthAudit._iso(completed_boundary_epoch),
            "v2_exposure_boundary": source_window,
            "partition_rule": "30000_DEVELOPMENT_THEN_10000_VALIDATION_THEN_V2_BOUNDARY_QUARANTINE",
            "true_oos_rule": "candle_open_timestamp >= v2_last_candle_close_timestamp",
            "slices": slices,
            "integrity": integrity,
            "partition_reconciliation": {
                "slice_candle_sum": sum(row["candle_count"] for row in slices),
                "equals_frozen_dataset": sum(row["candle_count"] for row in slices) == len(rates),
                "no_overlap": len(all_times) == len(set(all_times)),
                "chronological": all_times == sorted(all_times),
            },
        }
