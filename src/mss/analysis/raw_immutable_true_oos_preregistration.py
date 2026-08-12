"""Preregister a new raw-immutable true-OOS experiment after H8.2 closure."""

from __future__ import annotations


class RawImmutableTrueOosPreregistration:
    VERSION = (
        "MSS_SPRINT92H9_RAW_IMMUTABLE_TRUE_OOS_PREREGISTRATION_V2"
    )

    EXECUTION_ID = (
        "MSS_92H9_USDJPY_RAW_IMMUTABLE_TRUE_OOS_V2"
    )

    def build(self, h7, h82):
        if h7["schema_version"] != (
            "MSS_SPRINT92H7_DISTINCT_FUTURE_TRUE_OOS_PREREGISTRATION_V1"
        ):
            raise RuntimeError("unexpected H7 schema")

        if h82["schema_version"] != (
            "MSS_SPRINT92H8_2_TRUE_OOS_SOURCE_INTEGRITY_CLOSURE_V1"
        ):
            raise RuntimeError("unexpected H8.2 schema")

        if (
            h82["closed_experiment"]["status"]
            != "DATA_INTEGRITY_BLOCKED"
        ):
            raise RuntimeError("legacy H7 experiment is not integrity-blocked")

        if not h82["acceptance"]["new_preregistration_required"]:
            raise RuntimeError("H8.2 does not authorize new preregistration")

        return {
            "schema_version": self.VERSION,
            "mode": (
                "PREREGISTRATION_ONLY_NO_MT5_NO_DATA_ACQUISITION_"
                "NO_REPLAY_NO_OUTCOME_INSPECTION"
            ),

            "baseline_commit": "41f72c7",
            "execution_id": self.EXECUTION_ID,

            "legacy_experiment": {
                "execution_id": h7["execution_id"],
                "status": "CLOSED_DATA_INTEGRITY_BLOCKED",
                "reuse_prohibited": True,
                "legacy_true_oos_boundary_reuse_prohibited": True,
                "legacy_frozen_prefix_reuse_prohibited": True,
            },

            "research_hypothesis": {
                "primary_symbol": "USDJPY",
                "timeframe": "M15",
                "claim": (
                    "THE_HASH_FROZEN_BASELINE_TRADING_DECISION_PATH_"
                    "HAS_POSITIVE_EXPECTANCY_ON_A_NEW_DISTINCT_"
                    "TRUE_FUTURE_OUT_OF_SAMPLE_WINDOW"
                ),
                "candidate_origin": (
                    "SPRINT92H_IMMUTABLE_DEVELOPMENT_ANALYSIS"
                ),
                "candidate_status": (
                    "DEVELOPMENT_PROMISING_NOT_CONFIRMED"
                ),
                "production_status_before_test": "UNCHANGED",
            },

            "new_boundary_contract": {
                "exact_timestamp_locked_in_h9": False,
                "exact_timestamp_must_be_created_after_h9_commit": True,
                "boundary_authority_stage": (
                    "SPRINT92H10_ONE_TIME_TRUE_OOS_ANCHOR"
                ),
                "rule": (
                    "NEW_TRUE_OOS_BOUNDARY_EQUALS_THE_USDJPY_M15_"
                    "CURRENT_BAR_OPEN_TIMESTAMP_OBSERVED_ONCE_AFTER_"
                    "THE_H9_PREREGISTRATION_COMMIT"
                ),
                "first_eligible_candle_rule": (
                    "CANDLE_OPEN_TIMESTAMP_MUST_BE_GREATER_THAN_OR_"
                    "EQUAL_TO_THE_H10_LOCKED_BOUNDARY"
                ),
                "pre_h9_observed_candles_eligible": False,
                "h81_observed_candles_eligible": False,
                "legacy_h7_prefix_eligible": False,
            },

            "immutable_accrual_contract": {
                "required_completed_candles": 10000,
                "timeframe": "M15",
                "symbol": "USDJPY",
                "completed_candles_only": True,
                "chronological_order_required": True,

                "storage_model": (
                    "APPEND_ONLY_CANONICAL_BROKER_CANDLE_LEDGER"
                ),

                "canonical_record_fields": [
                    "time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "tick_volume",
                    "spread",
                    "real_volume",
                ],

                "canonical_record_representation": (
                    "COMPACT_JSON_ARRAY_ONE_CANDLE_PER_LINE"
                ),

                "record_layout": (
                    "[time,open,high,low,close,"
                    "tick_volume,spread,real_volume]"
                ),

                "raw_broker_fields_preserved": True,
                "write_once": True,
                "append_only": True,
                "overwrite_prohibited": True,
                "row_replacement_prohibited": True,
                "historical_backfill_over_frozen_rows_prohibited": True,

                "duplicate_timestamp_prohibited": True,
                "timestamp_regression_prohibited": True,

                "per_record_sha256_required": True,
                "chunk_sha256_required": True,
                "ledger_sha256_required": True,

                "atomic_write_required": True,
                "manifest_update_after_successful_append_only": True,

                "broker_revision_policy": (
                    "A_LATER_BROKER_VALUE_DIFFERING_FROM_AN_ALREADY_"
                    "FROZEN_CANDLE_IS_RECORDED_AS_DRIFT_EVIDENCE_AND_"
                    "MUST_NEVER_REPLACE_THE_FROZEN_CANDLE"
                ),

                "drift_localization_required": True,
                "drift_localization_granularity": (
                    "TIMESTAMP_AND_FIELD"
                ),
            },

            "eligibility_contract": {
                "required_frozen_rows": 10000,
                "eligibility_source": (
                    "IMMUTABLE_LOCAL_LEDGER_NOT_REDOWNLOADED_BROKER_HISTORY"
                ),
                "partial_ledger_outcome_analysis": False,
                "interim_strategy_replay": False,
                "interim_performance_metrics": False,

                "eligible_when": (
                    "THE_LEDGER_CONTAINS_THE_FIRST_10000_VALID_"
                    "COMPLETED_M15_CANDLES_FROM_THE_LOCKED_H10_BOUNDARY"
                ),

                "final_snapshot_definition": (
                    "EXACTLY_THE_FIRST_10000_ROWS_OF_THE_IMMUTABLE_LEDGER"
                ),
            },

            "execution_identity": {
                "source_authority": (
                    "H7_HASH_FROZEN_EXECUTION_IDENTITY"
                ),
                "execution_file_sha256": (
                    h7["execution_identity"]["execution_file_sha256"]
                ),
                "trading_decision_path": (
                    "BASELINE_TRADING_DECISION_PATH_UNCHANGED"
                ),
                "confluence_status": (
                    "DIAGNOSTIC_CAPTURE_PRESENT_NOT_A_TRADING_GATE"
                ),
                "any_execution_hash_change_requires_new_protocol": True,
                "retuning_prohibited": True,
                "parameter_change_prohibited": True,
                "post_hoc_filtering_prohibited": True,
            },

            "strategy_contract": {
                "starting_balance": 10000.0,
                "risk_percent": 1.0,
                "reward_risk_ratio": 2.0,
                "warmup_candles": 200,
                "analysis_lookback": 500,
                "entry_rule": "NEXT_CANDLE_OPEN",
                "ambiguous_exit_policy": "STOP_LOSS_FIRST",
                "slippage_points": 1.0,
                "commission_per_lot": 0.0,
                "parameter_optimization": False,
                "direction_filtering": False,
                "retuning": False,
            },

            "confirmation_gate": (
                h7["primary_confirmation_gate"]
            ),

            "execution_governance": {
                "h10_anchor_acquisitions": 1,
                "authoritative_final_snapshot_count": 1,
                "authoritative_strategy_replays": 1,

                "strategy_replay_before_10000_rows": False,
                "outcome_access_before_10000_rows": False,

                "failed_or_negative_result_must_be_preserved": True,
                "rerun_after_outcome_inspection": False,
                "replacement_snapshot_after_outcome_inspection": False,

                "production_change_requires_separate_governance": True,
            },

            "audit": {
                "mt5_accessed": False,
                "new_boundary_observed": False,
                "market_data_acquired": False,
                "true_oos_rows_written": 0,
                "strategy_replay_run": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
                "production_behavior_changed": False,
            },

            "acceptance": {
                "new_execution_id_defined": True,
                "legacy_experiment_not_reused": True,
                "new_boundary_must_follow_preregistration": True,
                "raw_immutable_accrual_required": True,
                "broker_drift_cannot_overwrite_frozen_rows": True,
                "no_mt5_access": True,
                "no_market_data_acquisition": True,
                "no_strategy_replay": True,
                "no_outcome_inspection": True,
                "production_change_justified": False,
            },
        }
