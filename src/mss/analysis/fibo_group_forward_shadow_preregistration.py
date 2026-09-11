"""Freeze the independent FIBO paired forward-shadow contract before runtime work."""

from __future__ import annotations

from pathlib import Path


class FiboGroupForwardShadowPreregistration:
    VERSION = "MSS_SPRINT93_3F_FIBO_GROUP_PAIRED_FORWARD_SHADOW_PREREGISTRATION_V1"
    EXECUTION_ID = "MSS_93_3F_FIBO_GROUP_PAIRED_FORWARD_SHADOW_V1"
    SYMBOLS = {"BTCUSD": "BTC", "ETHUSD": "ETH"}

    @classmethod
    def build(cls, root: Path) -> dict[str, object]:
        preflight = (
            root
            / "reports"
            / "MSS_Sprint93_3F_FIBO_Group_Forward_Demo_Preflight_LOCAL.json"
        )
        return {
            "schema_version": cls.VERSION,
            "execution_id": cls.EXECUTION_ID,
            "protocol_state": "BLOCKED_PENDING_DEDICATED_RUNTIME_AND_NEW_ACTIVATION_MANIFEST",
            "purpose": "Freeze an independent paired forward-shadow experiment on FIBO demo data",
            "broker_contract": {
                "provider": "FIBO Group",
                "required_server": "FIBOGroup-MT5 Server",
                "required_account_class": "DEMO",
                "terminal_preflight_passed_locally": preflight.is_file(),
                "terminal_preflight_report_publishable": False,
            },
            "experiment": {
                "canonical_to_broker_symbol": cls.SYMBOLS,
                "timeframe": "M15",
                "duration": "45_CALENDAR_DAYS",
                "baseline": "SmartMoneyPipeline",
                "candidate": "ConfluenceGatedSmartMoneyPipeline",
                "decision_pairing": "SAME_COMPLETED_CANDLE_SNAPSHOT",
                "parameter_optimization_during_experiment": False,
                "pre_activation_data_eligible": False,
            },
            "activation_contract": {
                "new_fibo_specific_manifest_required": True,
                "prior_alpari_manifest_reuse_allowed": False,
                "manifest_created_only_after_runtime_freeze_pr_is_publicly_merged": True,
                "manifest_published_and_verified_before_first_eligible_boundary": True,
                "runtime_git_blob_identity_frozen": True,
                "python_and_numpy_versions_frozen": True,
                "retroactive_activation_allowed": False,
                "all_pre_activation_data_permanently_ineligible": True,
            },
            "journal_contract": {
                "append_only": True,
                "sha256_hash_chain": True,
                "single_writer_lease": True,
                "duplicate_boundary_rejected": True,
                "partial_write_recovery_fail_closed": True,
                "restart_resumes_only_from_verified_durable_state": True,
                "restart_may_not_create_duplicate_decisions_or_positions": True,
            },
            "market_data_contract": {
                "completed_m15_candles_only": True,
                "broker_bar_open_must_match_requested_boundary": True,
                "missing_or_mismatched_boundary": "FAIL_CLOSED_AND_PRESERVE_PARTIAL_EVIDENCE",
                "weekend_role": "BTC_AND_ETH_ALLOW_CONTINUOUS_CALENDAR_OBSERVATION_SUBJECT_TO_BROKER_AVAILABILITY",
                "gap_or_disconnection": "NO_SYNTHETIC_BAR_NO_BACKFILL_NO_RETROACTIVE_DECISION",
            },
            "outcome_governance": {
                "interim_parameter_change_allowed": False,
                "rerun_after_outcome_access_allowed": False,
                "broker_accurate_profitability_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "final_evaluation_requires_complete_45_day_boundary_or_preserved_failure": True,
            },
            "safety": {
                "shadow_only": True,
                "order_check_called": False,
                "order_send_called": False,
                "real_order_send_allowed": False,
                "production_execution_enabled": False,
            },
            "next_authorized_action": "Implement and test the dedicated FIBO runtime while activation remains blocked",
        }
