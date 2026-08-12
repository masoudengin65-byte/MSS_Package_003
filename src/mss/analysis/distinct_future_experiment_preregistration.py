"""Preregister the distinct immutable true-OOS experiment after Sprint 92H closure."""

from __future__ import annotations

import hashlib
import json


class DistinctFutureExperimentPreregistration:
    VERSION = "MSS_SPRINT92H7_DISTINCT_FUTURE_TRUE_OOS_PREREGISTRATION_V1"
    EXECUTION_ID = "MSS_92H7_USDJPY_TRUE_OOS_V1"

    REQUIRED_EXECUTION_FILES = (
        "src/mss/analysis/smart_money_pipeline.py",
        "src/mss/analysis/confluence_engine.py",
        "src/mss/domain/pipeline_result.py",
        "src/mss/analysis/risk_engine.py",
        "src/mss/analysis/order_builder.py",
        "src/mss/analysis/position_manager.py",
        "src/mss/analysis/historical_backtest_engine.py",
        "src/mss/analysis/historical_valuation.py",
        "src/mss/analysis/context_capture_engine.py",
        "src/mss/analysis/score_engine.py",
    )

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

    def build(self, h6, c2, execution_hashes):
        if h6["schema_version"] != (
            "MSS_SPRINT92H6_IMMUTABLE_DEVELOPMENT_RESEARCH_CLOSURE_V1"
        ):
            raise RuntimeError("unexpected H6 schema")

        if c2["schema_version"] != (
            "MSS_SPRINT92C2_EXTENDED_DATASET_MANIFEST_V1"
        ):
            raise RuntimeError("unexpected C2 schema")

        if not h6["acceptance"]["true_future_oos_remains_sealed"]:
            raise RuntimeError("H6 does not preserve true OOS seal")

        if (
            h6["immutable_development_closure"]
            ["final_classifications"]["USDJPY"]
            != "DEVELOPMENT_PROMISING_NOT_CONFIRMED"
        ):
            raise RuntimeError("USDJPY is not the H6 research candidate")

        if set(execution_hashes) != set(self.REQUIRED_EXECUTION_FILES):
            raise RuntimeError("execution-critical file universe mismatch")

        usd = next(
            row for row in c2["symbols"]
            if row["canonical_symbol"] == "USDJPY"
        )

        boundary = usd["v2_exposure_boundary"]

        if boundary["last_candle_close_time"] != "2026-08-07T17:00:00":
            raise RuntimeError("unexpected USDJPY true-OOS boundary")

        slices = {
            row["slice"]: row
            for row in usd["slices"]
        }

        accrual = slices["TRUE_OOS_ACCRUAL"]

        if accrual["analysis_access"] != "FROZEN_NO_ANALYSIS":
            raise RuntimeError("existing true-OOS prefix was already analyzed")

        if accrual["first_candle_open_timestamp"] != "2026-08-07T17:00:00Z":
            raise RuntimeError("true-OOS prefix does not start at locked boundary")

        return {
            "schema_version": self.VERSION,
            "mode": (
                "PREREGISTRATION_ONLY_"
                "NO_ELIGIBILITY_CHECK_NO_REPLAY_NO_OUTCOME_INSPECTION"
            ),
            "baseline_commit": "6f2189c",
            "execution_id": self.EXECUTION_ID,

            "research_hypothesis": {
                "primary_symbol": "USDJPY",
                "claim": (
                    "UNCHANGED_BASELINE_TRADING_DECISION_PATH_HAS_"
                    "POSITIVE_EXPECTANCY_ON_DISTINCT_TRUE_FUTURE_OOS"
                ),
                "development_status": (
                    "DEVELOPMENT_PROMISING_NOT_CONFIRMED"
                ),
                "development_temporal_status": "MIXED",
                "production_status_before_experiment": "UNCHANGED",
            },

            "source_lineage": {
                "development": {
                    "status": "CONSUMED",
                    "candles": 30000,
                    "first_open": "2024-07-29T05:30:00Z",
                    "last_close": "2025-10-17T08:15:00Z",
                },
                "validation": {
                    "status": "CONSUMED_NOT_CONFIRMATORY",
                    "candles": 10000,
                    "first_open": "2025-10-17T08:15:00Z",
                    "last_close": "2026-03-17T18:00:00Z",
                },
                "research_exposed_quarantine": {
                    "status": "PROHIBITED_FOR_CONFIRMATION",
                    "candles": 9773,
                    "first_open": "2026-03-17T18:00:00Z",
                    "last_close": "2026-08-07T17:00:00Z",
                },
                "true_oos_boundary": {
                    "rule": (
                        "CANDLE_OPEN_TIMESTAMP_MUST_BE_AT_OR_AFTER_"
                        "V2_LAST_CANDLE_CLOSE_TIMESTAMP"
                    ),
                    "timestamp": "2026-08-07T17:00:00Z",
                    "authority": boundary["source_authority"],
                    "authority_sha256": boundary["source_sha256"],
                },
                "existing_frozen_unanalyzed_prefix": {
                    "status": "FROZEN_NO_ANALYSIS",
                    "candles": accrual["candle_count"],
                    "first_open": accrual["first_candle_open_timestamp"],
                    "last_open": accrual["last_candle_open_timestamp"],
                    "last_close": accrual["last_candle_close_timestamp"],
                    "ohlcv_sha256": accrual["ohlcv_sha256"],
                    "may_form_prefix_of_future_snapshot": True,
                    "outcome_analysis_before_full_snapshot": False,
                },
            },

            "immutable_snapshot_contract": {
                "symbol": "USDJPY",
                "timeframe": "M15",
                "required_completed_candles": 10000,
                "selection_rule": (
                    "FIRST_10000_ELIGIBLE_COMPLETED_M15_CANDLES_"
                    "IN_STRICT_CHRONOLOGICAL_ORDER_STARTING_AT_"
                    "2026-08-07T17:00:00Z"
                ),
                "prefix_rule": (
                    "THE_EXISTING_227_FROZEN_NO_ANALYSIS_CANDLES_"
                    "MUST_MATCH_THE_PREFIX_OF_THE_FINAL_10000_"
                    "SNAPSHOT_BY_TIMESTAMP_AND_OHLCV"
                ),
                "all_or_fail": True,
                "partial_snapshot_outcome_analysis": False,
                "interim_peeking": False,
                "snapshot_before_strategy_replay": True,
                "write_once": True,
                "overwrite_prohibited": True,
                "atomic_staging_then_promotion": True,
                "file_sha256_before_parse_required": True,
                "row_count_boundary_and_ohlcv_hash_after_parse_required": True,
                "broker_history_fallback_after_verification_failure": False,
            },

            "execution_identity": {
                "identity_type": "HASH_FROZEN_CURRENT_EXECUTION_VERSION",
                "baseline_commit": "6f2189c",
                "classification": (
                    "BASELINE_TRADING_DECISION_PATH_UNCHANGED;"
                    "CONFLUENCE_DIAGNOSTIC_CAPTURE_PRESENT"
                ),
                "legacy_c6_binary_identity_claimed": False,
                "execution_file_sha256": dict(
                    sorted(execution_hashes.items())
                ),
                "any_hash_change_before_replay_requires_new_protocol": True,
            },

            "strategy_contract": {
                "timeframe": "M15",
                "warmup_candles": 200,
                "analysis_lookback": 500,
                "starting_balance": 10000.0,
                "risk_percent": 1.0,
                "reward_risk_ratio": 2.0,
                "spread_points": None,
                "commission_per_lot": 0.0,
                "slippage_points": 1.0,
                "ambiguous_exit_policy": "STOP_LOSS_FIRST",
                "entry_rule": "NEXT_CANDLE_OPEN",
                "completed_candles_only": True,
                "historical_account_currency_valuation": True,
                "parameter_optimization": False,
                "post_hoc_filtering": False,
                "direction_filtering": False,
                "retuning": False,
                "real_orders": False,
            },

            "broker_metadata_contract": {
                "source": (
                    "FROZEN_METADATA_FROM_SPRINT92H3_"
                    "IMMUTABLE_DEVELOPMENT_REPLAY_PREREGISTRATION"
                ),
                "current_mt5_symbol_info_prohibited": True,
                "current_tick_value_not_historical_valuation_authority": True,
                "metadata_refresh_before_replay_prohibited": True,
            },

            "authoritative_execution_contract": {
                "eligibility_check_runs_after_h7_commit_only": True,
                "authoritative_snapshot_exports": 1,
                "authoritative_strategy_replays": 1,
                "rerun_after_outcome_inspection": False,
                "replacement_snapshot_after_outcome_inspection": False,
                "partial_replay": False,
            },

            "primary_confirmation_gate": {
                "symbol": "USDJPY",
                "minimum_closed_trades": 100,
                "all_requirements_must_pass": True,
                "requirements": [
                    "observed expectancy > 0",
                    "observed mean R > 0",
                    "observed profit factor > 1",
                    (
                        "ordinary bootstrap 95% CI lower bound "
                        "for expectancy > 0"
                    ),
                    (
                        "ordinary bootstrap 95% CI lower bound "
                        "for mean R > 0"
                    ),
                    (
                        "circular moving-block bootstrap 95% CI "
                        "lower bound for expectancy > 0"
                    ),
                    (
                        "circular moving-block bootstrap 95% CI "
                        "lower bound for mean R > 0"
                    ),
                    (
                        "ordinary bootstrap probability "
                        "expectancy > 0 >= 0.975"
                    ),
                    (
                        "moving-block bootstrap probability "
                        "expectancy > 0 >= 0.975"
                    ),
                    "BUY net PnL > 0",
                    "SELL net PnL > 0",
                    (
                        "maximum realized loss <= 1.25% "
                        "of pre-trade equity"
                    ),
                    (
                        "zero source hash, boundary, lookahead, "
                        "reconciliation, or valuation failures"
                    ),
                ],
                "decision_if_all_pass": (
                    "TRUE_OOS_RESEARCH_CONFIRMED_CANDIDATE_"
                    "REQUIRES_SEPARATE_PRODUCTION_GOVERNANCE_REVIEW"
                ),
                "decision_if_any_fail": (
                    "TRUE_OOS_NOT_CONFIRMED_NO_PRODUCTION_CHANGE"
                ),
            },

            "reporting_contract": {
                "report_all_closed_trades": True,
                "report_unresolved_trades": True,
                "report_all_rejection_reasons": True,
                "report_directional_results": True,
                "report_ordinary_bootstrap": True,
                "report_moving_block_bootstrap": True,
                "report_risk_audit": True,
                "report_valuation_audit": True,
                "report_source_hash_audit": True,
                "preserve_failed_or_null_result": True,
            },

            "data_governance": {
                "development_reuse_for_selection": False,
                "validation_reuse_for_confirmation": False,
                "research_quarantine_reuse_for_confirmation": False,
                "external_history_reuse_for_confirmation": False,
                "true_oos_current_status": "SEALED",
                "eligibility_checked_in_h7": False,
                "true_oos_outcomes_inspected_in_h7": False,
            },

            "audit": {
                "mt5_accessed": False,
                "eligibility_checked": False,
                "strategy_replay_run": False,
                "outcomes_analyzed": False,
                "true_oos_used": False,
                "validation_accessed": False,
                "external_history_accessed": False,
                "strategy_code_changed": False,
                "production_behavior_changed": False,
            },

            "acceptance": {
                "distinct_execution_id_defined": True,
                "true_oos_boundary_locked": True,
                "execution_hashes_locked": True,
                "immutable_snapshot_rule_locked": True,
                "pass_fail_gate_locked": True,
                "legacy_consumed_data_excluded": True,
                "eligibility_not_checked": True,
                "outcomes_not_inspected": True,
                "true_oos_remains_sealed": True,
                "production_change_justified": False,
            },
        }
