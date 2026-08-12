"""First append-only accrual into the raw-immutable True-OOS ledger."""

from __future__ import annotations

import hashlib

from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.analysis.true_oos_ledger_store import TrueOosLedgerStore


class TrueOosFirstAccrual:
    VERSION = "MSS_SPRINT92H12_FIRST_APPEND_ONLY_TRUE_OOS_ACCRUAL_V1"

    SYMBOL = "USDJPY"
    TIMEFRAME = "M15"
    TIMEFRAME_SECONDS = 900
    REQUIRED_CANDLES = 10_000

    @staticmethod
    def epoch(row):
        return int(HistoricalDepthAudit._value(row, "time"))

    @classmethod
    def eligible_completed(
        cls,
        rates,
        raw_boundary_epoch,
        current_bar_epoch,
    ):
        raw_boundary_epoch = int(raw_boundary_epoch)
        current_bar_epoch = int(current_bar_epoch)

        rows = [
            row
            for row in rates
            if cls.epoch(row) >= raw_boundary_epoch
            and cls.epoch(row) + cls.TIMEFRAME_SECONDS <= current_bar_epoch
        ]

        rows = sorted(rows, key=cls.epoch)

        times = [cls.epoch(row) for row in rows]

        if len(times) != len(set(times)):
            raise RuntimeError("duplicate eligible timestamp")

        if times != sorted(times):
            raise RuntimeError("eligible rows not chronological")

        return rows

    @classmethod
    def chunk_manifest(cls, rows, chunk_path):
        if not rows:
            raise RuntimeError("cannot create empty H12 chunk")

        payload = b"".join(
            TrueOosLedgerStore.canonical_line(row).encode("utf-8")
            for row in rows
        )

        first_epoch = cls.epoch(rows[0])
        last_epoch = cls.epoch(rows[-1])

        return {
            "sequence": 1,
            "path": str(chunk_path).replace("\\", "/"),
            "row_count": len(rows),
            "first_epoch": first_epoch,
            "last_epoch": last_epoch,
            "first_open_broker_time_label": HistoricalDepthAudit._iso(
                first_epoch
            ),
            "last_open_broker_time_label": HistoricalDepthAudit._iso(
                last_epoch
            ),
            "file_sha256": hashlib.sha256(payload).hexdigest(),
            "record_sha256": [
                TrueOosLedgerStore.record_sha256(row)
                for row in rows
            ],
        }

    @classmethod
    def build(
        cls,
        h10,
        h11,
        h111,
        genesis_manifest,
        rows,
        current_bar_epoch,
        chunk_relative_path,
        genesis_manifest_sha256,
    ):
        if h10["schema_version"] != (
            "MSS_SPRINT92H10_ONE_TIME_TRUE_OOS_ANCHOR_LOCK_V1"
        ):
            raise RuntimeError("unexpected H10 schema")

        if h11["schema_version"] != (
            "MSS_SPRINT92H11_APPEND_ONLY_TRUE_OOS_LEDGER_INITIALIZATION_V1"
        ):
            raise RuntimeError("unexpected H11 schema")

        if h111["schema_version"] != (
            "MSS_SPRINT92H11_1_MT5_TIME_AUTHORITY_AUDIT_V1"
        ):
            raise RuntimeError("unexpected H11.1 schema")

        execution_id = h10["execution_id"]

        if h11["execution_id"] != execution_id:
            raise RuntimeError("H10/H11 execution mismatch")

        if h111["execution_id"] != execution_id:
            raise RuntimeError("H10/H11.1 execution mismatch")

        if (
            h111["time_authority"]["status"]
            != "BROKER_TIME_DOMAIN_CONFIRMED"
        ):
            raise RuntimeError("broker time domain not confirmed")

        if (
            h111["time_authority"]["boundary_comparison_authority"]
            != "RAW_MT5_TIME_FIELD"
        ):
            raise RuntimeError("unexpected boundary authority")

        if genesis_manifest["manifest_sequence"] != 0:
            raise RuntimeError("not genesis manifest")

        if genesis_manifest["row_count"] != 0:
            raise RuntimeError("genesis ledger is not empty")

        if genesis_manifest["chunk_count"] != 0:
            raise RuntimeError("genesis ledger already contains chunks")

        raw_boundary_epoch = int(h10["anchor"]["boundary_epoch"])

        eligible = cls.eligible_completed(
            rows,
            raw_boundary_epoch,
            current_bar_epoch,
        )

        if not eligible:
            raise RuntimeError(
                "NO_COMPLETED_TRUE_OOS_CANDLES_AVAILABLE"
            )

        if cls.epoch(eligible[0]) != raw_boundary_epoch:
            raise RuntimeError(
                "first available completed candle does not equal locked anchor"
            )

        integrity = HistoricalDepthAudit.integrity(
            eligible,
            cls.TIMEFRAME,
            int(current_bar_epoch),
        )

        integrity_pass = (
            integrity["strictly_increasing_timestamps"]
            and integrity["duplicate_timestamp_count"] == 0
            and integrity["invalid_ohlc_count"] == 0
            and integrity["nonfinite_price_count"] == 0
            and integrity["negative_spread_count"] == 0
            and integrity["negative_volume_count"] == 0
            and integrity["future_candle_count"] == 0
        )

        if not integrity_pass:
            raise RuntimeError(
                "eligible True-OOS candles failed integrity"
            )

        chunk = cls.chunk_manifest(
            eligible,
            chunk_relative_path,
        )

        aggregate_payload = b"".join(
            TrueOosLedgerStore.canonical_line(row).encode("utf-8")
            for row in eligible
        )

        aggregate_sha = hashlib.sha256(
            aggregate_payload
        ).hexdigest()

        row_count = len(eligible)

        eligibility_status = (
            "ELIGIBLE_FOR_FINAL_SNAPSHOT_GOVERNANCE"
            if row_count >= cls.REQUIRED_CANDLES
            else "ACCRUAL_IN_PROGRESS"
        )

        manifest_1 = {
            "schema_version": "MSS_TRUE_OOS_LEDGER_MANIFEST_V1",
            "execution_id": execution_id,
            "manifest_sequence": 1,
            "previous_manifest_sha256": genesis_manifest_sha256,
            "true_oos_boundary": genesis_manifest["true_oos_boundary"],
            "raw_true_oos_boundary_epoch": raw_boundary_epoch,
            "time_authority": "RAW_MT5_TIME_FIELD",
            "timeframe": cls.TIMEFRAME,
            "symbol": cls.SYMBOL,
            "chunk_count": 1,
            "row_count": row_count,
            "first_candle_open_epoch": cls.epoch(eligible[0]),
            "last_candle_open_epoch": cls.epoch(eligible[-1]),
            "chunks": [chunk],
            "aggregate_ledger_sha256": aggregate_sha,
            "eligibility_status": eligibility_status,
        }

        return {
            "schema_version": cls.VERSION,
            "mode": (
                "FIRST_APPEND_ONLY_TRUE_OOS_ACCRUAL_"
                "NO_STRATEGY_REPLAY_NO_OUTCOMES"
            ),
            "execution_id": execution_id,
            "baseline_commit": "3c8cba0",

            "time_contract": {
                "execution_time_domain": "RAW_MT5_BROKER_EPOCH_DOMAIN",
                "boundary_epoch": raw_boundary_epoch,
                "boundary_string_is_execution_authority": False,
                "raw_mt5_time_field_is_execution_authority": True,
                "stored_candle_epochs_shifted": False,
            },

            "accrual": {
                "current_bar_epoch": int(current_bar_epoch),
                "completed_rows_appended": row_count,
                "first_appended_epoch": cls.epoch(eligible[0]),
                "last_appended_epoch": cls.epoch(eligible[-1]),
                "required_final_rows": cls.REQUIRED_CANDLES,
                "remaining_rows": max(
                    0,
                    cls.REQUIRED_CANDLES - row_count,
                ),
                "eligibility_status": eligibility_status,
            },

            "integrity": {
                **integrity,
                "pass": integrity_pass,
            },

            "chunk": chunk,
            "next_manifest": manifest_1,

            "immutability": {
                "genesis_manifest_modified": False,
                "chunk_000001_write_once": True,
                "manifest_000001_write_once": True,
                "broker_revision_overwrite_allowed": False,
                "historical_row_replacement_allowed": False,
            },

            "audit": {
                "mt5_accessed": True,
                "completed_market_data_acquired": True,
                "strategy_pipeline_imported": False,
                "strategy_replay_run": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
                "production_behavior_changed": False,
            },

            "acceptance": {
                "first_chunk_created": True,
                "first_manifest_successor_created": True,
                "raw_boundary_preserved": True,
                "broker_time_authority_preserved": True,
                "source_integrity_passed": integrity_pass,
                "no_replay": True,
                "no_outcome_inspection": True,
                "no_orders": True,
            },

            "_eligible_rows": eligible,
        }
