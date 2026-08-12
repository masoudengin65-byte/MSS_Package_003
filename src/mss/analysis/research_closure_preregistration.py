"""Deterministic Sprint 92C research closure and True-OOS preregistration."""

from __future__ import annotations

import hashlib
import json


class ResearchClosurePreregistration:
    VERSION = "MSS_SPRINT92C6_RESEARCH_CLOSURE_TRUE_OOS_PREREGISTRATION_V1"
    SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "XAUUSD", "BTCUSD", "ETHUSD")

    @staticmethod
    def sha256(payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    def build(self, sources):
        c3, c4, c5 = sources["c3"], sources["c4"], sources["c5"]
        dev = c3["segments"]["DEVELOPMENT"]["combined_independent_results"]
        val = c3["segments"]["VALIDATION"]["combined_independent_results"]
        return {
            "schema_version": self.VERSION,
            "mode": "RESEARCH_CLOSURE_AND_FUTURE_PROTOCOL_ONLY",
            "baseline_commit": "06377a7",
            "source_artifacts": {
                key: {"schema_version": value["schema_version"], "payload_sha256": self.sha256(value)}
                for key, value in sources.items()
            },
            "sprint_92c_closure": {
                "completed_sprints": ["92C.1", "92C.2", "92C.3", "92C.4", "92C.5"],
                "development_combined": {
                    "closed_trades": dev["closed_trades"], "net_profit": dev["net_profit"],
                    "return_percent": dev["return_percent"], "profit_factor": dev["profit_factor"],
                },
                "validation_combined": {
                    "closed_trades": val["closed_trades"], "net_profit": val["net_profit"],
                    "return_percent": val["return_percent"], "profit_factor": val["profit_factor"],
                },
                "statistical_classifications": c4["final_classifications"],
                "usdjpy_falsification_assessment": c5["final_assessment"],
                "scientific_conclusion": "NO_SYMBOL_HAS_CONFIRMED_ROBUST_POSITIVE_EVIDENCE",
                "production_decision": "NO_STRATEGY_OR_SYMBOL_FILTER_CHANGE",
                "further_analysis_of_existing_development_validation_data": "CLOSED_TO_AVOID_ADDITIONAL_DATA_MINING",
            },
            "true_oos_preregistration": {
                "status": "LOCKED_BEFORE_ELIGIBILITY_CHECK_OR_OUTCOME_ANALYSIS",
                "accrual_gate": {
                    "minimum_completed_m15_candles_per_symbol": 10_000,
                    "required_symbols": list(self.SYMBOLS),
                    "boundary_rule": "EVERY_CANDLE_OPEN_MUST_BE_AT_OR_AFTER_EACH_SYMBOL_V2_LAST_CANDLE_CLOSE",
                    "common_gate": "DO_NOT_RUN_UNTIL_ALL_EIGHT_SYMBOLS_MEET_THE_10000_CANDLE_REQUIREMENT",
                    "interim_peeking": "PROHIBITED",
                    "current_oos_eligibility_or_outcome_checked_in_this_sprint": False,
                },
                "execution_contract": {
                    "number_of_authoritative_replays": 1,
                    "snapshot_rule": "FIRST_10000_ELIGIBLE_COMPLETED_M15_CANDLES_PER_SYMBOL_IN_CHRONOLOGICAL_ORDER",
                    "strategy_version": "EXACT_CODE_AND_CONFIGURATION_FROZEN_AT_COMMIT_06377a7",
                    "starting_balance_per_symbol": 10_000.0, "risk_percent": 1.0,
                    "reward_risk_ratio": 2.0, "warmup_candles": 200,
                    "analysis_lookback": 500, "entry": "NEXT_CANDLE_OPEN",
                    "ambiguous_exit_policy": "STOP_LOSS_FIRST", "real_orders": False,
                    "parameter_optimization": False, "post_hoc_filtering": False,
                },
                "primary_hypothesis": {
                    "symbol": "USDJPY",
                    "claim": "UNCHANGED_STRATEGY_HAS_POSITIVE_TRUE_OOS_EXPECTANCY",
                    "minimum_closed_trades": 100,
                    "all_confirmation_requirements": [
                        "observed expectancy > 0", "observed mean R > 0", "observed profit factor > 1",
                        "ordinary bootstrap 95% CI lower bounds for expectancy and mean R > 0",
                        "circular moving-block bootstrap 95% CI lower bounds for expectancy and mean R > 0",
                        "BUY net PnL > 0 and SELL net PnL > 0",
                        "maximum realized loss <= 1.25% of pre-trade equity",
                        "zero lookahead, reconciliation, hash, or valuation failures",
                    ],
                    "decision_if_all_pass": "RESEARCH_CONFIRMED_CANDIDATE_REQUIRES_SEPARATE_PRODUCTION_GOVERNANCE_REVIEW",
                    "decision_if_any_fail": "NOT_CONFIRMED_NO_PRODUCTION_CHANGE",
                },
                "secondary_symbols": {
                    "symbols": [symbol for symbol in self.SYMBOLS if symbol != "USDJPY"],
                    "status": "EXPLORATORY_ONLY",
                    "production_claims_allowed": False,
                    "reason": "NO_SECONDARY_SYMBOL_WAS_PREREGISTERED_AS_A_CONFIRMATORY_CANDIDATE",
                },
                "reporting_requirements": [
                    "report every symbol regardless of outcome", "report unresolved trades and every rejection reason",
                    "report ordinary and moving-block bootstrap intervals", "report directional results",
                    "report risk, valuation, source hash, boundary, and reconciliation audits",
                    "preserve failed and null results; do not rerun or replace the snapshot",
                ],
                "amendment_policy": "ANY_CHANGE_REQUIRES_A_NEW_COMMIT_BEFORE_OOS_ELIGIBILITY_OR_OUTCOME_INSPECTION_AND_INVALIDATES_CONFIRMATORY_STATUS_IF_DATA_WAS_PEEKED",
            },
            "audit": {
                "mt5_accessed": False, "history_downloaded": False, "strategy_replay_run": False,
                "true_oos_eligibility_checked": False, "true_oos_outcomes_analyzed": False,
                "strategy_or_production_behavior_changed": False,
            },
            "acceptance": {
                "all_source_artifacts_present": set(sources) == {"c1", "c2", "c3", "c4", "c5"},
                "closure_matches_c4": c4["final_classifications"].get("USDJPY") == "PROMISING_NOT_CONFIRMED"
                    and not any(value == "ROBUST_POSITIVE" for value in c4["final_classifications"].values()),
                "closure_matches_c5": c5["final_assessment"] == "FAILS_ONE_OR_MORE_STABILITY_CHECKS",
                "oos_remains_uninspected": True, "production_change_justified": False,
            },
        }
