"""Initialize the empty immutable True-OOS ledger after the H10 anchor lock."""

from __future__ import annotations


class TrueOosLedgerInitialization:
    VERSION = (
        "MSS_SPRINT92H11_APPEND_ONLY_TRUE_OOS_LEDGER_INITIALIZATION_V1"
    )

    def build(self, h9, h10):
        if h9["schema_version"] != (
            "MSS_SPRINT92H9_RAW_IMMUTABLE_TRUE_OOS_PREREGISTRATION_V2"
        ):
            raise RuntimeError("unexpected H9 schema")

        if h10["schema_version"] != (
            "MSS_SPRINT92H10_ONE_TIME_TRUE_OOS_ANCHOR_LOCK_V1"
        ):
            raise RuntimeError("unexpected H10 schema")

        if h9["execution_id"] != h10["execution_id"]:
            raise RuntimeError("H9/H10 execution identity mismatch")

        boundary = h10["anchor"]["boundary_timestamp"]

        if boundary != "2026-08-12T17:45:00Z":
            raise RuntimeError("unexpected H10 boundary")

        if not h10["acceptance"]["new_boundary_locked"]:
            raise RuntimeError("H10 boundary is not locked")

        return {
            "schema_version": self.VERSION,
            "mode": (
                "EMPTY_LEDGER_INITIALIZATION_ONLY_"
                "NO_MT5_NO_MARKET_DATA_NO_REPLAY_NO_OUTCOMES"
            ),
            "baseline_commit": "80cfaed",
            "execution_id": h9["execution_id"],

            "ledger_identity": {
                "canonical_symbol": "USDJPY",
                "broker_symbol": "USDJPY",
                "timeframe": "M15",
                "true_oos_boundary": boundary,
                "required_completed_candles": 10000,
                "storage_model": (
                    "APPEND_ONLY_WRITE_ONCE_JSONL_CHUNK_LEDGER"
                ),
            },

            "physical_layout": {
                "root": (
                    "research_data/sprint92h_true_oos_v2/"
                    "USDJPY_M15"
                ),
                "chunk_directory": (
                    "research_data/sprint92h_true_oos_v2/"
                    "USDJPY_M15/chunks"
                ),
                "initial_manifest": (
                    "research_data/sprint92h_true_oos_v2/"
                    "USDJPY_M15/manifest_000000.json"
                ),
                "chunk_name_pattern": (
                    "chunk_{sequence:06d}.jsonl"
                ),
                "manifest_name_pattern": (
                    "manifest_{sequence:06d}.json"
                ),
            },

            "canonical_serialization": {
                "container": (
                    "WRITE_ONCE_UTF8_JSONL_CHUNKS"
                ),
                "record_type": "JSON_ARRAY",
                "record_layout": [
                    "time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "tick_volume",
                    "spread",
                    "real_volume",
                ],
                "compact_separators": True,
                "allow_nan": False,
                "newline": "LF",
                "bom": False,
                "integer_fields": [
                    "time",
                    "tick_volume",
                    "spread",
                    "real_volume",
                ],
                "float_fields": [
                    "open",
                    "high",
                    "low",
                    "close",
                ],
            },

            "immutability_contract": {
                "existing_chunk_modification_prohibited": True,
                "existing_chunk_deletion_prohibited": True,
                "existing_manifest_modification_prohibited": True,
                "existing_manifest_deletion_prohibited": True,
                "chunk_sequence_reuse_prohibited": True,
                "manifest_sequence_reuse_prohibited": True,
                "duplicate_timestamp_prohibited": True,
                "timestamp_regression_prohibited": True,
                "broker_revision_may_not_replace_frozen_row": True,
                "later_broker_revision_is_drift_evidence_only": True,
                "per_record_sha256_required": True,
                "per_chunk_sha256_required": True,
                "aggregate_ledger_sha256_required": True,
                "atomic_temporary_write_then_promotion": True,
            },

            "initial_state": {
                "manifest_sequence": 0,
                "chunk_count": 0,
                "row_count": 0,
                "first_candle_open_timestamp": None,
                "last_candle_open_timestamp": None,
                "chunks": [],
                "aggregate_ledger_sha256": (
                    "e3b0c44298fc1c149afbf4c8996fb924"
                    "27ae41e4649b934ca495991b7852b855"
                ),
                "eligibility_status": "ACCRUAL_NOT_STARTED",
            },

            "next_append_contract": {
                "next_chunk_sequence": 1,
                "next_manifest_sequence": 1,
                "first_allowed_candle_open_timestamp": boundary,
                "completed_candles_only": True,
                "read_existing_frozen_rows_before_append": True,
                "verify_all_existing_chunk_hashes_before_append": True,
                "verify_manifest_chain_before_append": True,
                "append_only_new_completed_rows": True,
                "strategy_replay_during_append": False,
                "outcome_analysis_during_append": False,
            },

            "audit": {
                "mt5_accessed": False,
                "market_data_acquired": False,
                "completed_candles_acquired": 0,
                "ledger_rows_written": 0,
                "strategy_replay_run": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },

            "acceptance": {
                "empty_ledger_initialized": True,
                "boundary_preserved": True,
                "canonical_format_locked": True,
                "write_once_chunk_model_locked": True,
                "versioned_manifest_model_locked": True,
                "zero_market_rows_written": True,
                "no_mt5_access": True,
                "no_strategy_replay": True,
                "no_outcome_inspection": True,
            },
        }
