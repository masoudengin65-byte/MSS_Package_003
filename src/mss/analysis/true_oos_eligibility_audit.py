"""Read-only true-OOS eligibility and frozen-prefix integrity logic."""

from __future__ import annotations

from mss.analysis.historical_depth_audit import HistoricalDepthAudit


class TrueOosEligibilityAudit:
    VERSION = "MSS_SPRINT92H8_1_TRUE_OOS_ELIGIBILITY_AUDIT_V1"

    SYMBOL = "USDJPY"
    BROKER_SYMBOL = "USDJPY"
    TIMEFRAME = "M15"

    REQUIRED_CANDLES = 10_000
    LOCKED_BOUNDARY_EPOCH = 1786122000  # 2026-08-07T17:00:00Z
    LOCKED_BOUNDARY_ISO = "2026-08-07T17:00:00Z"

    PREFIX_COUNT = 227
    PREFIX_FIRST_OPEN = "2026-08-07T17:00:00Z"
    PREFIX_LAST_OPEN = "2026-08-12T02:15:00Z"
    PREFIX_LAST_CLOSE = "2026-08-12T02:30:00Z"
    PREFIX_OHLCV_SHA256 = (
        "f65b4f41b2bedc4cc1fe4fed39e1c2f1"
        "e844098db95c904d38be2c8a30ad9d8e"
    )

    @staticmethod
    def _epoch(row):
        return int(HistoricalDepthAudit._value(row, "time"))

    @classmethod
    def eligible_completed(cls, rates, current_bar_open_epoch):
        completed = HistoricalDepthAudit.completed_candles(
            rates,
            cls.TIMEFRAME,
            current_bar_open_epoch,
        )

        eligible = [
            row
            for row in completed
            if cls._epoch(row) >= cls.LOCKED_BOUNDARY_EPOCH
        ]

        return sorted(
            eligible,
            key=cls._epoch,
        )

    @classmethod
    def prefix_audit(cls, eligible):
        if len(eligible) < cls.PREFIX_COUNT:
            return {
                "available": False,
                "reason": "FEWER_THAN_LOCKED_PREFIX_CANDLES_AVAILABLE",
                "expected_count": cls.PREFIX_COUNT,
                "available_count": len(eligible),
                "match": False,
            }

        prefix = eligible[: cls.PREFIX_COUNT]

        first = cls._epoch(prefix[0])
        last = cls._epoch(prefix[-1])

        actual_hash = HistoricalDepthAudit.candle_hash(prefix)

        checks = {
            "count_match": len(prefix) == cls.PREFIX_COUNT,
            "first_open_match": (
                HistoricalDepthAudit._iso(first)
                == cls.PREFIX_FIRST_OPEN
            ),
            "last_open_match": (
                HistoricalDepthAudit._iso(last)
                == cls.PREFIX_LAST_OPEN
            ),
            "last_close_match": (
                HistoricalDepthAudit._iso(
                    last
                    + HistoricalDepthAudit.TIMEFRAME_SECONDS[cls.TIMEFRAME]
                )
                == cls.PREFIX_LAST_CLOSE
            ),
            "ohlcv_sha256_match": (
                actual_hash == cls.PREFIX_OHLCV_SHA256
            ),
        }

        return {
            "available": True,
            "reason": None,
            "expected_count": cls.PREFIX_COUNT,
            "actual_count": len(prefix),
            "expected_ohlcv_sha256": cls.PREFIX_OHLCV_SHA256,
            "actual_ohlcv_sha256": actual_hash,
            **checks,
            "match": all(checks.values()),
        }

    @classmethod
    def build(cls, protocol, rates, current_bar_open_epoch):
        if protocol["schema_version"] != (
            "MSS_SPRINT92H7_DISTINCT_FUTURE_TRUE_OOS_PREREGISTRATION_V1"
        ):
            raise RuntimeError("unexpected H7 protocol schema")

        if protocol["execution_id"] != "MSS_92H7_USDJPY_TRUE_OOS_V1":
            raise RuntimeError("unexpected H7 execution id")

        if (
            protocol["source_lineage"]["true_oos_boundary"]["timestamp"]
            != cls.LOCKED_BOUNDARY_ISO
        ):
            raise RuntimeError("H7 true-OOS boundary mismatch")

        if (
            protocol["immutable_snapshot_contract"]
            ["required_completed_candles"]
            != cls.REQUIRED_CANDLES
        ):
            raise RuntimeError("H7 required candle count mismatch")

        eligible = cls.eligible_completed(
            rates,
            current_bar_open_epoch,
        )

        if not eligible:
            first_open = None
            last_open = None
            last_close = None
        else:
            first_epoch = cls._epoch(eligible[0])
            last_epoch = cls._epoch(eligible[-1])

            first_open = HistoricalDepthAudit._iso(first_epoch)
            last_open = HistoricalDepthAudit._iso(last_epoch)
            last_close = HistoricalDepthAudit._iso(
                last_epoch
                + HistoricalDepthAudit.TIMEFRAME_SECONDS[cls.TIMEFRAME]
            )

        integrity = HistoricalDepthAudit.integrity(
            eligible,
            cls.TIMEFRAME,
            current_bar_open_epoch,
        )

        prefix = cls.prefix_audit(eligible)

        integrity_pass = (
            integrity["strictly_increasing_timestamps"]
            and integrity["duplicate_timestamp_count"] == 0
            and integrity["invalid_ohlc_count"] == 0
            and integrity["nonfinite_price_count"] == 0
            and integrity["negative_spread_count"] == 0
            and integrity["negative_volume_count"] == 0
            and integrity["future_candle_count"] == 0
        )

        eligible_count = len(eligible)

        if not prefix["match"]:
            status = "PREFIX_INTEGRITY_FAILURE"
        elif not integrity_pass:
            status = "SOURCE_INTEGRITY_FAILURE"
        elif eligible_count >= cls.REQUIRED_CANDLES:
            status = "ELIGIBLE_FOR_H8_2_SNAPSHOT_EXPORT"
        else:
            status = "NOT_ELIGIBLE_YET"

        return {
            "schema_version": cls.VERSION,
            "mode": (
                "READ_ONLY_TRUE_OOS_ELIGIBILITY_"
                "AND_FROZEN_PREFIX_INTEGRITY_CHECK"
            ),
            "baseline_commit": "618ff82",
            "execution_id": protocol["execution_id"],

            "source": {
                "broker": "ALPARI_MT5",
                "access_mode": "READ_ONLY_MARKET_DATA",
                "canonical_symbol": cls.SYMBOL,
                "broker_symbol": cls.BROKER_SYMBOL,
                "timeframe": cls.TIMEFRAME,
                "locked_boundary": cls.LOCKED_BOUNDARY_ISO,
                "current_bar_open_epoch": int(current_bar_open_epoch),
                "current_bar_open_timestamp": (
                    HistoricalDepthAudit._iso(current_bar_open_epoch)
                ),
            },

            "eligibility": {
                "status": status,
                "required_completed_candles": cls.REQUIRED_CANDLES,
                "available_completed_candles": eligible_count,
                "remaining_candles": max(
                    0,
                    cls.REQUIRED_CANDLES - eligible_count,
                ),
                "first_eligible_open_timestamp": first_open,
                "last_eligible_open_timestamp": last_open,
                "last_eligible_close_timestamp": last_close,
                "snapshot_export_authorized": (
                    status == "ELIGIBLE_FOR_H8_2_SNAPSHOT_EXPORT"
                ),
                "snapshot_exported": False,
            },

            "frozen_prefix_audit": prefix,
            "source_integrity": {
                **integrity,
                "pass": integrity_pass,
            },

            "governance": {
                "strategy_replay_authorized": False,
                "strategy_replay_run": False,
                "outcomes_inspected": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "valuation_metadata_accessed": False,
                "partial_snapshot_exported": False,
                "true_oos_snapshot_exported": False,
            },

            "audit": {
                "mt5_accessed": True,
                "mt5_access_purpose": (
                    "READ_ONLY_CANDLE_ELIGIBILITY_CHECK_ONLY"
                ),
                "strategy_pipeline_imported": False,
                "strategy_replay_run": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },

            "acceptance": {
                "locked_boundary_respected": (
                    not eligible
                    or cls._epoch(eligible[0])
                    == cls.LOCKED_BOUNDARY_EPOCH
                ),
                "frozen_227_prefix_verified": prefix["match"],
                "source_integrity_passed": integrity_pass,
                "no_strategy_replay": True,
                "no_outcome_inspection": True,
                "no_orders": True,
            },
        }
