"""Preregister the distinct Sprint 93 confluence-gate forward experiment."""

from __future__ import annotations


class Sprint93ConfluenceGateV2Preregistration:
    """Build an outcome-blind, production-isolated experiment contract."""

    VERSION = (
        "MSS_SPRINT93_2A_CONFLUENCE_GATE_V2_"
        "FORWARD_SHADOW_PREREGISTRATION_V1"
    )
    EXECUTION_ID = "MSS_93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_V1"
    FIRST_ELIGIBLE_CANDLE_OPEN_UTC = "2026-08-23T20:15:00Z"
    BASELINE_COMMIT = "0e643da"

    REQUIRED_EXECUTION_FILES = (
        "src/mss/analysis/smart_money_pipeline.py",
        "src/mss/analysis/confluence_engine.py",
        "src/mss/analysis/confluence_gated_smart_money_pipeline.py",
        "src/mss/domain/pipeline_result.py",
        "src/mss/analysis/frozen_shadow_strategy_adapter.py",
        "src/mss/analysis/shadow_trade_engine.py",
        "src/mss/analysis/virtual_position_engine.py",
        "src/mss/analysis/risk_engine.py",
    )

    SYMBOLS = (
        ("BTCUSD", "BITCOIN"),
        ("ETHUSD", "ETHEREUM"),
    )

    @staticmethod
    def _by_symbol(c2):
        return {
            row["canonical_symbol"]: row
            for row in c2["symbols"]
        }

    def _validate(self, g5, h6, c2, execution_hashes):
        if g5["schema_version"] != (
            "MSS_SPRINT92G5_CONFLUENCE_GATE_RESEARCH_CLOSURE_V1"
        ):
            raise RuntimeError("unexpected G5 schema")
        if h6["schema_version"] != (
            "MSS_SPRINT92H6_IMMUTABLE_DEVELOPMENT_RESEARCH_CLOSURE_V1"
        ):
            raise RuntimeError("unexpected H6 schema")
        if c2["schema_version"] != (
            "MSS_SPRINT92C2_EXTENDED_DATASET_MANIFEST_V1"
        ):
            raise RuntimeError("unexpected C2 schema")

        if g5["hypothesis_status"]["status"] != (
            "NOT_EVALUATED_DUE_TO_AUTHORITATIVE_SOURCE_INTEGRITY_FAILURE"
        ):
            raise RuntimeError("G1 status was not preserved")
        if g5["governance"]["g3_rerun_authorized"]:
            raise RuntimeError("G3 rerun must remain prohibited")
        if not h6["future_experiment_governance"]["next_experiment_must_be_distinct"]:
            raise RuntimeError("H6 distinct-experiment rule missing")
        if h6["future_experiment_governance"]["validation_status"] != (
            "SEALED_FROM_CONFIRMATORY_REUSE"
        ):
            raise RuntimeError("consumed validation is not sealed")
        if set(execution_hashes) != set(self.REQUIRED_EXECUTION_FILES):
            raise RuntimeError("execution-critical file universe mismatch")
        if not all(
            isinstance(value, str) and len(value) == 64
            for value in execution_hashes.values()
        ):
            raise RuntimeError("invalid execution hash")

        by_symbol = self._by_symbol(c2)
        for canonical, broker in self.SYMBOLS:
            row = by_symbol.get(canonical)
            if row is None or row["broker_symbol"] != broker:
                raise RuntimeError(f"missing frozen symbol identity: {canonical}")
            if row["v2_exposure_boundary"]["last_candle_close_time"] != (
                "2026-08-07T17:15:00"
            ):
                raise RuntimeError(f"unexpected prior boundary: {canonical}")

    def build(self, g5, h6, c2, execution_hashes):
        self._validate(g5, h6, c2, execution_hashes)
        by_symbol = self._by_symbol(c2)

        prior_prefixes = []
        for canonical, broker in self.SYMBOLS:
            row = by_symbol[canonical]
            prefix = next(
                item
                for item in row["slices"]
                if item["slice"] == "TRUE_OOS_ACCRUAL"
            )
            prior_prefixes.append(
                {
                    "canonical_symbol": canonical,
                    "broker_symbol": broker,
                    "status": prefix["analysis_access"],
                    "candle_count": prefix["candle_count"],
                    "last_candle_close_timestamp": (
                        prefix["last_candle_close_timestamp"]
                    ),
                    "ohlcv_sha256": prefix["ohlcv_sha256"],
                    "eligible_for_sprint93_outcomes": False,
                }
            )

        return {
            "schema_version": self.VERSION,
            "mode": (
                "PREREGISTRATION_ONLY_NO_MT5_NO_REPLAY_"
                "NO_OUTCOME_INSPECTION_NO_PRODUCTION_CHANGE"
            ),
            "baseline_commit": self.BASELINE_COMMIT,
            "execution_id": self.EXECUTION_ID,
            "experiment_identity": {
                "experiment_id": "SPRINT93_2A_CONFLUENCE_GATE_V2",
                "prior_g1_hypothesis_id": "G1_FALSE_BREAKOUT_CONFLUENCE_GATE",
                "prior_g1_status": (
                    "ARCHIVED_UNEVALUATED_SOURCE_INTEGRITY_FAILURE"
                ),
                "g3_rerun": False,
                "distinct_hypothesis_version": True,
                "distinct_execution_id": True,
                "research_only": True,
            },
            "research_hypothesis": {
                "claim": (
                    "REQUIRING_THE_EXISTING_DIRECTION_ALIGNED_CONFLUENCE_"
                    "SIGNAL_ON_A_BOS_REDUCES_FALSE_BOS_ENTRIES_AND_IMPROVES_"
                    "PAIRED_FORWARD_SHADOW_MEAN_R_PROFIT_FACTOR_AND_WIN_RATE"
                ),
                "mechanism": (
                    "DISPLACEMENT_ORDER_BLOCK_AND_FAIR_VALUE_GAP_MUST_"
                    "CONFIRM_THE_BOS_DIRECTION_BEFORE_ENTRY_ELIGIBILITY"
                ),
                "falsifiable": True,
                "no_new_numeric_strategy_threshold": True,
                "not_selected_from_sprint93_forward_outcomes": True,
            },
            "candidate_contract": {
                "baseline": "UNCHANGED_SMART_MONEY_PIPELINE",
                "candidate": "CONFLUENCE_GATED_SMART_MONEY_PIPELINE",
                "single_change": (
                    "ENTRY_ELIGIBLE_ONLY_WHEN_EXISTING_CONFLUENCE_ENGINE_"
                    "RETURNS_VALID_DIRECTION_MATCHING_BOS"
                ),
                "unchanged": [
                    "swing detection",
                    "structure detection",
                    "BOS detection",
                    "next-candle entry",
                    "stop placement",
                    "risk 1%",
                    "reward-risk 2.0",
                    "valuation",
                    "STOP_LOSS_FIRST ambiguous-exit policy",
                    "one-position policy",
                ],
                "no_symbol_specific_rule": True,
                "no_direction_filter": True,
                "no_score_threshold": True,
                "parameter_optimization": False,
                "production_pipeline_replacement": False,
            },
            "source_governance": {
                "first_eligible_candle_open_utc": (
                    self.FIRST_ELIGIBLE_CANDLE_OPEN_UTC
                ),
                "selection_rule": (
                    "COMPLETED_M15_CANDLES_WITH_OPEN_TIMESTAMP_AT_OR_AFTER_"
                    "2026_08_23T20_15_00Z_OBSERVED_FORWARD_ONLY"
                ),
                "historical_backfill": False,
                "development_reuse": False,
                "validation_reuse": False,
                "research_quarantine_reuse": False,
                "pre_protocol_true_oos_prefix_reuse": False,
                "broker_history_redownload": False,
                "prior_unanalyzed_prefixes_excluded": prior_prefixes,
                "append_only_journal_required": True,
                "write_once_session_manifests_required": True,
                "partial_outcome_analysis": False,
                "interim_parameter_change": False,
            },
            "paired_forward_shadow_contract": {
                "symbols": [
                    {
                        "canonical_symbol": canonical,
                        "broker_symbol": broker,
                        "timeframe": "M15",
                    }
                    for canonical, broker in self.SYMBOLS
                ],
                "same_completed_candles": True,
                "same_decision_timestamps": True,
                "same_cost_and_valuation_model": True,
                "independent_baseline_and_candidate_journals": True,
                "baseline_can_open_virtual_positions": True,
                "candidate_can_open_virtual_positions": True,
                "order_check_allowed": False,
                "order_send_allowed": False,
                "real_order_allowed": False,
                "timebox_calendar_days": 45,
                "maximum_m15_candles_per_symbol": 4320,
                "extension_after_timebox": False,
            },
            "research_evaluation_gate": {
                "primary_metric": (
                    "PAIRED_MEAN_R_DIFFERENCE_CANDIDATE_MINUS_BASELINE"
                ),
                "minimum_candidate_closed_trades_pooled": 50,
                "minimum_candidate_closed_trades_per_symbol": 15,
                "target_candidate_profit_factor": 1.10,
                "target_candidate_win_rate": 0.36,
                "requirements": [
                    "paired candidate-minus-baseline mean R > 0",
                    "candidate pooled mean R > 0",
                    "candidate pooled expectancy > 0",
                    "candidate pooled profit factor >= 1.10",
                    "candidate pooled win rate >= 0.36",
                    "candidate maximum drawdown <= baseline maximum drawdown",
                    "ordinary and moving-block bootstrap probability mean R > 0 >= 0.80",
                    "minimum pooled and per-symbol sample gates pass",
                    "zero integrity lookahead valuation or risk failures",
                ],
                "decision_if_all_pass": (
                    "RESEARCH_GATE_PASSED_REQUIRES_SEPARATE_LARGER_"
                    "CONFIRMATION_AND_PRODUCTION_GOVERNANCE"
                ),
                "decision_if_performance_fails": (
                    "CLOSE_CANDIDATE_NO_RETUNING_NO_PRODUCTION_CHANGE"
                ),
                "decision_if_sample_insufficient_at_timebox": (
                    "CLOSE_INCONCLUSIVE_NO_EXTENSION_NO_PRODUCTION_CHANGE"
                ),
            },
            "future_release_gate_not_authorized_here": {
                "minimum_closed_trades": 100,
                "minimum_profit_factor": 1.20,
                "positive_expectancy_95_percent_lower_bound": True,
                "maximum_drawdown_rate": 0.15,
                "demo_order_lifecycle_evidence_required": True,
                "separate_preregistration_required": True,
                "real_money_authorized": False,
            },
            "execution_identity": {
                "identity_type": "HASH_FROZEN_RESEARCH_EXECUTION",
                "baseline_commit": self.BASELINE_COMMIT,
                "execution_file_sha256": dict(sorted(execution_hashes.items())),
                "any_hash_change_before_first_forward_candle_requires_new_version": True,
            },
            "prohibited_actions": [
                "RUN_G3_AGAIN",
                "REUSE_H4_DEVELOPMENT_FOR_CONFIRMATION",
                "REUSE_C4_VALIDATION_FOR_CONFIRMATION",
                "BACKFILL_PRE_PROTOCOL_CANDLES",
                "TUNE_SCORE_OR_CONFLUENCE_COMPONENTS_DURING_EXPERIMENT",
                "DROP_BUY_OR_SELL_AFTER_INTERIM_RESULTS",
                "EXTEND_THE_45_DAY_TIMEBOX_AFTER_OUTCOME_INSPECTION",
                "SEND_OR_CHECK_REAL_BROKER_ORDERS",
                "CHANGE_PRODUCTION_STRATEGY",
            ],
            "audit": {
                "mt5_accessed": False,
                "strategy_replay_run": False,
                "outcomes_analyzed": False,
                "development_accessed": False,
                "validation_accessed": False,
                "pre_protocol_true_oos_used": False,
                "strategy_code_changed": False,
                "production_behavior_changed": False,
                "order_check_called": False,
                "order_send_called": False,
            },
            "acceptance": {
                "new_version_and_execution_id": True,
                "g3_failure_preserved": True,
                "consumed_data_excluded": True,
                "forward_boundary_locked": True,
                "single_change_locked": True,
                "timebox_and_stop_rules_locked": True,
                "execution_hashes_locked": True,
                "production_change_justified": False,
            },
        }
