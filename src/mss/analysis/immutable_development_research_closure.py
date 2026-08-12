"""Close immutable Development research and govern any future confirmatory experiment."""

from __future__ import annotations

import hashlib
import json


class ImmutableDevelopmentResearchClosure:
    VERSION = "MSS_SPRINT92H6_IMMUTABLE_DEVELOPMENT_RESEARCH_CLOSURE_V1"

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

    def build(self, h5, c6, e8, g5):
        if h5["schema_version"] != (
            "MSS_SPRINT92H5_IMMUTABLE_DEVELOPMENT_OUTCOME_ANALYSIS_V1"
        ):
            raise RuntimeError("unexpected H5 schema")

        if c6["schema_version"] != (
            "MSS_SPRINT92C6_RESEARCH_CLOSURE_TRUE_OOS_PREREGISTRATION_V1"
        ):
            raise RuntimeError("unexpected C6 schema")

        if e8["schema_version"] != (
            "MSS_SPRINT92E8_EXTERNAL_HISTORICAL_VALIDATION_CLOSURE_V1"
        ):
            raise RuntimeError("unexpected E8 schema")

        if g5["schema_version"] != (
            "MSS_SPRINT92G5_CONFLUENCE_GATE_RESEARCH_CLOSURE_V1"
        ):
            raise RuntimeError("unexpected G5 schema")

        classifications = h5["final_classifications"]

        if classifications["USDJPY"] != (
            "DEVELOPMENT_PROMISING_NOT_CONFIRMED"
        ):
            raise RuntimeError(
                "H5 USDJPY classification differs from expected closure input"
            )

        if h5["production_governance"]["strategy_change_authorized"]:
            raise RuntimeError("H5 unexpectedly authorizes strategy change")

        if not c6["acceptance"]["oos_remains_uninspected"]:
            raise RuntimeError("C6 does not preserve uninspected OOS")

        if not e8["acceptance"]["true_future_oos_preserved"]:
            raise RuntimeError("E8 does not preserve true future OOS")

        if not g5["data_governance"]["true_future_oos_remains_sealed"]:
            raise RuntimeError("G5 does not preserve sealed true future OOS")

        return {
            "schema_version": self.VERSION,
            "mode": (
                "IMMUTABLE_DEVELOPMENT_RESEARCH_CLOSURE_"
                "AND_FUTURE_EXPERIMENT_GOVERNANCE_ONLY"
            ),
            "baseline_commit": "617fe17",

            "source_artifacts": {
                "h5": {
                    "schema_version": h5["schema_version"],
                    "payload_sha256": self.digest(h5),
                },
                "c6": {
                    "schema_version": c6["schema_version"],
                    "payload_sha256": self.digest(c6),
                },
                "e8": {
                    "schema_version": e8["schema_version"],
                    "payload_sha256": self.digest(e8),
                },
                "g5": {
                    "schema_version": g5["schema_version"],
                    "payload_sha256": self.digest(g5),
                },
            },

            "immutable_development_closure": {
                "development_closed_trade_count": (
                    h5["source"]["closed_trade_count"]
                ),
                "final_classifications": classifications,
                "primary_observation": (
                    "USDJPY_IS_DEVELOPMENT_PROMISING_NOT_CONFIRMED_"
                    "BUT_TEMPORALLY_MIXED"
                ),
                "confirmed_robust_positive_symbols": [],
                "production_decision": (
                    "NO_STRATEGY_SYMBOL_DIRECTION_OR_RISK_CHANGE"
                ),
                "additional_post_hoc_development_search": (
                    "PROHIBITED_TO_AVOID_ADDITIONAL_DATA_MINING"
                ),
            },

            "historical_validation_status": {
                "existing_validation_status": "CONSUMED_NOT_CONFIRMATORY",
                "existing_validation_reuse_for_confirmation": "PROHIBITED",
                "external_historical_windows_status": (
                    "CONSUMED_OR_SEALED_PER_SPRINT92E8"
                ),
                "external_history_reuse_for_confirmation": "PROHIBITED",
                "scientific_status": (
                    "UNCHANGED_STRATEGY_NOT_CONFIRMED_BY_PRIOR_"
                    "VALIDATION_OR_EXTERNAL_HISTORY"
                ),
            },

            "legacy_true_oos_protocol": {
                "source": (
                    "MSS_Sprint92C6_Research_Closure_"
                    "True_OOS_Preregistration.json"
                ),
                "historical_protocol_preserved": True,
                "original_strategy_version": (
                    c6["true_oos_preregistration"]
                    ["execution_contract"]["strategy_version"]
                ),
                "original_primary_symbol": (
                    c6["true_oos_preregistration"]
                    ["primary_hypothesis"]["symbol"]
                ),
                "executed": False,
                "automatic_execution_authorized_by_h6": False,
                "eligibility_check_authorized_by_h6": False,
                "outcome_inspection_authorized_by_h6": False,
                "reason": (
                    "LATER_GOVERNANCE_REQUIRES_A_DISTINCT_"
                    "FUTURE_EXPERIMENT_AFTER_SOURCE_IMMUTABILITY"
                ),
            },

            "future_experiment_governance": {
                "true_future_oos_status": "SEALED",
                "validation_status": "SEALED_FROM_CONFIRMATORY_REUSE",
                "next_experiment_requires_new_preregistration": True,
                "next_experiment_must_be_distinct": True,
                "new_execution_id_required": True,
                "eligibility_check_before_new_preregistration": "PROHIBITED",
                "outcome_peeking_before_new_preregistration": "PROHIBITED",
                "mt5_history_access_before_new_preregistration": (
                    "PROHIBITED_IF_IT_REVEALS_ELIGIBILITY_OR_OUTCOMES"
                ),
                "candidate_symbol": "USDJPY",
                "candidate_status": (
                    "RESEARCH_CANDIDATE_ONLY_NOT_PRODUCTION_AUTHORIZED"
                ),
                "future_protocol_may_reference_c6_methodology": True,
                "future_protocol_must_not_claim_c6_was_executed": True,
                "future_protocol_must_freeze_current_execution_identity": True,
                "future_protocol_must_define_source_snapshot_before_outcomes": True,
                "future_protocol_must_preserve_no_retuning_rule": True,
            },

            "production_governance": {
                "strategy_change_authorized": False,
                "symbol_filter_change_authorized": False,
                "direction_filter_change_authorized": False,
                "risk_change_authorized": False,
                "production_status": "UNCHANGED",
            },

            "audit": {
                "strategy_replay_run": False,
                "outcomes_recomputed": False,
                "mt5_accessed": False,
                "validation_accessed": False,
                "external_history_accessed": False,
                "true_future_oos_used": False,
                "true_oos_eligibility_checked": False,
                "strategy_code_changed": False,
                "production_behavior_changed": False,
            },

            "acceptance": {
                "h5_development_analysis_respected": True,
                "existing_validation_not_reused": True,
                "external_history_closure_respected": True,
                "legacy_c6_protocol_preserved": True,
                "legacy_c6_not_executed": True,
                "g5_distinct_future_experiment_rule_respected": True,
                "true_future_oos_remains_sealed": True,
                "production_change_justified": False,
            },

            "allowed_next_actions": [
                "COMMIT_H6_RESEARCH_CLOSURE",
                "CREATE_A_DISTINCT_FUTURE_EXPERIMENT_PREREGISTRATION",
                "LOCK_CURRENT_STRATEGY_AND_EXECUTION_IDENTITY_BEFORE_ANY_ELIGIBILITY_CHECK",
                "DEFINE_IMMUTABLE_TRUE_OOS_SOURCE_SNAPSHOT_RULE_BEFORE_OUTCOME_INSPECTION",
            ],

            "prohibited_next_actions": [
                "REUSE_CONSUMED_VALIDATION_AS_CONFIRMATORY",
                "REUSE_E4_OR_E7_AS_CONFIRMATORY",
                "EXECUTE_LEGACY_C6_AUTOMATICALLY_WITHOUT_NEW_GOVERNANCE",
                "CHECK_TRUE_OOS_ELIGIBILITY_BEFORE_NEW_PREREGISTRATION",
                "PEEK_AT_TRUE_OOS_OUTCOMES",
                "RETUNE_USDJPY_FROM_H5_RESULTS",
                "PROMOTE_USDJPY_TO_PRODUCTION_FROM_DEVELOPMENT_ONLY_EVIDENCE",
            ],
        }
