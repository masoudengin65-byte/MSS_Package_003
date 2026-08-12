"""Close the blocked H7 true-OOS experiment after immutable prefix drift."""

from __future__ import annotations

import hashlib
import json


class TrueOosSourceIntegrityClosure:
    VERSION = "MSS_SPRINT92H8_2_TRUE_OOS_SOURCE_INTEGRITY_CLOSURE_V1"

    @staticmethod
    def digest(payload):
        return hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

    def build(self, h7, h81):
        if h7["schema_version"] != (
            "MSS_SPRINT92H7_DISTINCT_FUTURE_TRUE_OOS_PREREGISTRATION_V1"
        ):
            raise RuntimeError("unexpected H7 schema")

        if h81["schema_version"] != (
            "MSS_SPRINT92H8_1_TRUE_OOS_ELIGIBILITY_AUDIT_V1"
        ):
            raise RuntimeError("unexpected H8.1 schema")

        if h81["eligibility"]["status"] != "PREFIX_INTEGRITY_FAILURE":
            raise RuntimeError("H8.1 did not establish prefix integrity failure")

        prefix = h81["frozen_prefix_audit"]

        if prefix["actual_count"] != 227:
            raise RuntimeError("unexpected H8.1 prefix count")

        if prefix["match"]:
            raise RuntimeError("prefix unexpectedly matches")

        if not h81["source_integrity"]["pass"]:
            raise RuntimeError("structural source integrity also failed")

        return {
            "schema_version": self.VERSION,
            "mode": "RESEARCH_GOVERNANCE_CLOSURE_ONLY",
            "baseline_commit": "a1a098b",

            "closed_experiment": {
                "execution_id": h7["execution_id"],
                "primary_symbol": "USDJPY",
                "status": "DATA_INTEGRITY_BLOCKED",
                "strategy_outcome_status": "NOT_EVALUATED",
                "production_status": "UNCHANGED",
            },

            "true_oos_boundary": {
                "timestamp": (
                    h7["source_lineage"]
                    ["true_oos_boundary"]["timestamp"]
                ),
                "status": "LEGACY_EXPERIMENT_BOUNDARY_CLOSED",
            },

            "integrity_failure": {
                "failure_type": "FROZEN_PREFIX_CONTENT_DRIFT",
                "prefix_candle_count": prefix["actual_count"],
                "timestamp_boundary_match": (
                    prefix["first_open_match"]
                    and prefix["last_open_match"]
                    and prefix["last_close_match"]
                ),
                "expected_ohlcv_sha256": (
                    prefix["expected_ohlcv_sha256"]
                ),
                "actual_ohlcv_sha256": (
                    prefix["actual_ohlcv_sha256"]
                ),
                "ohlcv_sha256_match": False,
                "structural_source_integrity_passed": True,
                "drift_localization_possible": False,
                "drift_localization_reason": (
                    "C2 preserved the frozen prefix hash but did not "
                    "commit the raw 227-candle payload; therefore the "
                    "first changed candle and changed field cannot be "
                    "scientifically reconstructed from the two hashes."
                ),
            },

            "eligibility_state_at_failure": {
                "available_completed_candles": (
                    h81["eligibility"]["available_completed_candles"]
                ),
                "required_completed_candles": (
                    h81["eligibility"]["required_completed_candles"]
                ),
                "remaining_candles": (
                    h81["eligibility"]["remaining_candles"]
                ),
                "snapshot_exported": False,
                "snapshot_export_authorized": False,
            },

            "scientific_interpretation": {
                "strategy_failure_claimed": False,
                "strategy_success_claimed": False,
                "true_oos_performance_claimed": False,
                "failure_attributed_to_strategy": False,
                "failure_attributed_to_data_integrity_contract": True,
                "h7_confirmation_test_completed": False,
            },

            "prohibited_actions": {
                "continue_h7_snapshot_accrual_using_drifted_prefix": True,
                "replace_old_prefix_with_current_broker_history": True,
                "rerun_h81_to_seek_a_matching_history_version": True,
                "run_h7_strategy_replay": True,
                "inspect_h7_true_oos_outcomes": True,
                "reinterpret_exposed_history_as_true_oos": True,
                "production_change_from_h7": True,
            },

            "next_experiment_requirements": {
                "new_execution_id_required": True,
                "new_preregistration_required": True,
                "new_true_oos_boundary_required": True,
                "raw_candle_immutability_required": True,
                "write_once_snapshot_storage_required": True,
                "per_candle_canonical_serialization_required": True,
                "per_candle_or_chunk_hashing_required": True,
                "full_snapshot_sha256_required": True,
                "broker_corrections_must_not_overwrite_frozen_data": True,
                "future_broker_retrieval_may_be_used_only_for_drift_audit": True,
                "no_outcome_access_before_full_eligibility": True,
                "strategy_execution_identity_must_be_re_frozen": True,
            },

            "audit": {
                "mt5_accessed": False,
                "strategy_replay_run": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
                "production_behavior_changed": False,
            },

            "acceptance": {
                "legacy_h7_experiment_closed": True,
                "data_integrity_block_recorded": True,
                "no_strategy_outcome_inference": True,
                "no_replay": True,
                "no_outcome_inspection": True,
                "new_preregistration_required": True,
                "production_change_justified": False,
            },
        }
