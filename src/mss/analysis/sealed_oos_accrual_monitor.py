"""Timestamp-only True-OOS accrual monitoring with no price or strategy analysis."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


class SealedOosAccrualMonitor:
    VERSION = "MSS_SPRINT92D1_SEALED_OOS_ACCRUAL_MONITOR_V1"
    TIMEFRAME_SECONDS = 900
    TARGET = 10_000

    @staticmethod
    def parse_utc(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())

    @staticmethod
    def iso(epoch):
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def timestamp_hash(timestamps):
        raw = json.dumps(timestamps, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def inspect_symbol(cls, canonical, broker, asset_class, boundary_iso, timestamps, current_bar_open_epoch):
        boundary = cls.parse_utc(boundary_iso)
        eligible = sorted(int(value) for value in timestamps if int(value) >= boundary and int(value) < current_bar_open_epoch)
        duplicates = len(eligible) - len(set(eligible))
        unique = sorted(set(eligible))
        gaps = [current - previous for previous, current in zip(unique, unique[1:]) if current - previous > cls.TIMEFRAME_SECONDS]
        count = len(unique)
        return {
            "canonical_symbol": canonical, "broker_symbol": broker, "asset_class": asset_class,
            "timeframe": "M15", "v2_exposure_boundary_timestamp": boundary_iso,
            "completed_timestamp_count": count,
            "target_timestamp_count": cls.TARGET,
            "remaining_timestamp_count": max(0, cls.TARGET - count),
            "progress_percent": round(min(count, cls.TARGET) / cls.TARGET * 100, 4),
            "gate_met": count >= cls.TARGET,
            "first_eligible_open_timestamp": cls.iso(unique[0]) if unique else None,
            "last_completed_open_timestamp": cls.iso(unique[-1]) if unique else None,
            "current_bar_open_boundary_timestamp": cls.iso(current_bar_open_epoch),
            "timestamp_sha256": cls.timestamp_hash(unique),
            "quality": {
                "strictly_increasing": all(left < right for left, right in zip(unique, unique[1:])),
                "duplicate_timestamp_count": duplicates,
                "pre_boundary_timestamp_count_included": 0,
                "current_or_future_bar_count_included": 0,
                "gap_event_count": len(gaps),
                "largest_gap_seconds": max(gaps, default=0),
                "gap_policy": "REPORTED_ONLY; MARKET_CLOSURES_NOT_IMPUTED_OR_CLASSIFIED_AS_FAILURE",
            },
        }

    @classmethod
    def build(cls, rows, protocol_sha256):
        all_met = len(rows) == 8 and all(row["gate_met"] for row in rows)
        quality_pass = len(rows) == 8 and all(
            row["quality"]["strictly_increasing"]
            and row["quality"]["duplicate_timestamp_count"] == 0
            and row["quality"]["pre_boundary_timestamp_count_included"] == 0
            and row["quality"]["current_or_future_bar_count_included"] == 0
            for row in rows
        )
        return {
            "schema_version": cls.VERSION, "mode": "TIMESTAMP_ONLY_OPERATIONAL_ACCRUAL_MONITOR",
            "protocol": {
                "artifact": "reports/MSS_Sprint92C6_Research_Closure_True_OOS_Preregistration.json",
                "file_sha256": protocol_sha256, "target_per_symbol": cls.TARGET,
            },
            "privacy_and_seal_contract": {
                "ohlc_fields_read_into_report": False, "ohlc_fields_persisted": False,
                "price_hash_computed": False, "strategy_replay_run": False,
                "signals_or_trades_computed": False, "pnl_or_performance_computed": False,
                "only_persisted_market_data": "CANDLE_OPEN_TIMESTAMPS_AND_TIMESTAMP_DERIVED_QUALITY_METADATA",
            },
            "symbols": rows,
            "global_gate": {
                "all_eight_symbols_present": len(rows) == 8,
                "all_symbols_at_least_10000_completed_m15": all_met,
                "timestamp_quality_pass": quality_pass,
                "authoritative_replay_allowed": all_met and quality_pass,
                "status": "ELIGIBLE_FOR_SINGLE_PREREGISTERED_REPLAY" if all_met and quality_pass else "ACCRUING_REPLAY_PROHIBITED",
            },
            "audit": {
                "operational_count_check_only": True, "outcomes_analyzed": False,
                "interim_strategy_analysis_performed": False, "production_behavior_changed": False,
            },
        }
