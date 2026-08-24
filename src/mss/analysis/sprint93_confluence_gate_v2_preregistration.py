"""Outcome-blind Sprint 93.2A V2 preregistration contract."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re

class Sprint93ConfluenceGateV2Preregistration:
    VERSION="MSS_SPRINT93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_PREREGISTRATION_V2"
    EXECUTION_ID="MSS_93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_V2"
    BASELINE_COMMIT="0e643da"
    PROTOCOL_STATE="BLOCKED_PENDING_PAIRED_EXECUTION_FREEZE"
    INVALID_V1_BOUNDARY="2026-08-23T20:15:00Z"
    BOOTSTRAP_SEED=9320260825; BOOTSTRAP_RESAMPLES=10000; MOVING_BLOCK_LENGTH=8
    STRATEGY_COMPONENT_ROOTS=tuple(sorted((
        "src/mss/analysis/smart_money_pipeline.py","src/mss/analysis/confluence_engine.py","src/mss/analysis/confluence_gated_smart_money_pipeline.py","src/mss/domain/pipeline_result.py","src/mss/analysis/frozen_shadow_strategy_adapter.py","src/mss/analysis/shadow_trade_engine.py","src/mss/analysis/virtual_position_engine.py","src/mss/analysis/risk_engine.py","src/mss/analysis/shadow_risk_calculator.py","src/mss/analysis/shadow_trade_journal.py","src/mss/analysis/shadow_trade_valuation.py","src/mss/domain/trade_signal.py","src/mss/domain/risk_profile.py")))
    REQUIRED_STRATEGY_COMPONENT_FILES=tuple(sorted((
        "src/mss/analysis/bos_detector.py","src/mss/analysis/choch_detector.py","src/mss/analysis/confluence_engine.py","src/mss/analysis/confluence_gated_smart_money_pipeline.py","src/mss/analysis/displacement_detector.py","src/mss/analysis/frozen_shadow_strategy_adapter.py","src/mss/analysis/fvg_detector.py","src/mss/analysis/fvg_validator.py","src/mss/analysis/liquidity_detector.py","src/mss/analysis/order_block_detector.py","src/mss/analysis/premium_discount_engine.py","src/mss/analysis/real_swing_engine.py","src/mss/analysis/risk_engine.py","src/mss/analysis/setup_scoring_engine.py","src/mss/analysis/shadow_risk_calculator.py","src/mss/analysis/shadow_trade_engine.py","src/mss/analysis/shadow_trade_journal.py","src/mss/analysis/shadow_trade_valuation.py","src/mss/analysis/smart_money_pipeline.py","src/mss/analysis/structure_engine.py","src/mss/analysis/structure_state.py","src/mss/analysis/swing_detector.py","src/mss/analysis/swing_filter.py","src/mss/analysis/swing_validator.py","src/mss/analysis/virtual_position_engine.py","src/mss/config/settings.py","src/mss/domain/analysis_result.py","src/mss/domain/candle.py","src/mss/domain/displacement.py","src/mss/domain/fair_value_gap.py","src/mss/domain/liquidity.py","src/mss/domain/market_context.py","src/mss/domain/order_block.py","src/mss/domain/pipeline_result.py","src/mss/domain/premium_discount.py","src/mss/domain/risk_profile.py","src/mss/domain/setup_score.py","src/mss/domain/swing_point.py","src/mss/domain/trade_setup.py","src/mss/domain/trade_signal.py")))
    EXPECTED_STRATEGY_COMPONENT_SHA256={
"src/mss/analysis/bos_detector.py":"72f01833b1f5bff21984c9d4bba10cbcd94db395681db3fe43cb8a3617162676",
"src/mss/analysis/choch_detector.py":"02a71e36ba507e9b70971022e80cb037ce5a3ff9fec4c569ddb93eb2a6e76eb9",
"src/mss/analysis/confluence_engine.py":"ca075db045bd991073532ee1868b2cadbec4fde086d4674423ae5456d03b9609",
"src/mss/analysis/confluence_gated_smart_money_pipeline.py":"f984643cfb63b2859c58b38aaf7a4a0fbdfffa80612cf393a14a3553504ef4df",
"src/mss/analysis/displacement_detector.py":"c0384c5a548f4716e3314a16c0876ae5e2bba48af79225a89d6bfca5f98e0a71",
"src/mss/analysis/frozen_shadow_strategy_adapter.py":"0cc57ad0e1b81eec6c58108ce4a97395b7885226159f4354a9359943f6ae319f",
"src/mss/analysis/fvg_detector.py":"d75608efdaa82c75a6b6b9b0f517818e2358fc00524a099da9b84a8b880a2b38",
"src/mss/analysis/fvg_validator.py":"ac039778cd297dd7385717ec809c12017e259b67b458cf16b1dbb13666c08c1d",
"src/mss/analysis/liquidity_detector.py":"541825930858d532fb5f0b515b7f2d69067ef9373d4ad5d5a1399d7275629e9b",
"src/mss/analysis/order_block_detector.py":"2c690199cffdc8e55c97ebf825b903d569d6283c2f3115ee33d99e6148f39c82",
"src/mss/analysis/premium_discount_engine.py":"e39c8eab4c58b41bead0ad462ce5ff610710af2c5c84365862848a638d65cd23",
"src/mss/analysis/real_swing_engine.py":"4439a6b264196cb790f26767ab7af934a5a96008d700f74662a8eb2b2ea5b8c6",
"src/mss/analysis/risk_engine.py":"270557b72b004441f439dde4b009cb303a15f9f8491b6d9b5f5588c9fedf87d4",
"src/mss/analysis/setup_scoring_engine.py":"0fcbc17e68f0c4d1ea4c72ae494a0b3ab6553f45f62ad72a1457fe8066a3f69a",
"src/mss/analysis/shadow_risk_calculator.py":"7b684367217f3cab31c138287b6c79a1727d7e5dfe10f56b6b644137fe025b79",
"src/mss/analysis/shadow_trade_engine.py":"b96a9bb797d1d4ab9ce9ae5cd68e81a1eca510c342cf290bb6060785f0b98a3c",
"src/mss/analysis/shadow_trade_journal.py":"f366f8744981f8ecaa339fee70f4dfeae36fc70a592e223c37db0a6f8cf39b08",
"src/mss/analysis/shadow_trade_valuation.py":"a8d3359e051c32a5eb515fa75468c823237813349935eebfe410fbf214f100d3",
"src/mss/analysis/smart_money_pipeline.py":"704ecd5bd41073821e4697142af649a21016a7e9dfdfd0072c18d80173bab4c0",
"src/mss/analysis/structure_engine.py":"ba854bc379dd63060aee7fb7f8a67e7034f57b7413074a9233527ba5a5ccc272",
"src/mss/analysis/structure_state.py":"166424b9f013678bbf8f4bd8a162b508de543e07b9a17afd19b3862e1610557d",
"src/mss/analysis/swing_detector.py":"6a68f9c89b8a5dbf6102c71538cc8d30757b59034762c94b03f3f4e0ce0d1d9f",
"src/mss/analysis/swing_filter.py":"c06d828d9ddbb6b8f5efb717408876eaca1f394477ef5223624f5ddd4c265e41",
"src/mss/analysis/swing_validator.py":"03b365e86b5c7062933178cb31b1db102f093ad1fed1dab02a6fc7bf8ce57133",
"src/mss/analysis/virtual_position_engine.py":"445681972752a57d92a3c3d1670e5b7ca53f708444b839f8beeb77b03ba0e26b",
"src/mss/config/settings.py":"e3e81da35a97d94c8174bc4c0922d0ccc46edfb334faecf409994d9d930f26b1",
"src/mss/domain/analysis_result.py":"d07028f6fdea9d05aa89f18ec1df72edab277549bb0f1ab5954ee2d902c619c2",
"src/mss/domain/candle.py":"3d20c425c5638a54e680a69dd9504e736c675ce9e4cd54b2656e239481893f12",
"src/mss/domain/displacement.py":"8c2c0ef84b79e66d643deda8848f495049d3764f3d6c5893a2897c4ef06e8ba3",
"src/mss/domain/fair_value_gap.py":"c4eef0bcdf0f961bd677a17abf6cecee9769d404d9b4eaa73643a54154b234b5",
"src/mss/domain/liquidity.py":"0f36e936b435cd5af3c352efd50e8e760d63561f095f2a83fec0037a3b3822c4",
"src/mss/domain/market_context.py":"1235c434e7fe3fc29b0c4d084a201c0052182f09a5d681477be0c0e4191bbe34",
"src/mss/domain/order_block.py":"be0c4ba835d544a0e76345d0e0a2f31d3743dcb507e55f8406c22aca4ea889e5",
"src/mss/domain/pipeline_result.py":"e1b3c4d324dec5887d984d9d25ef13d51eeb7cf2e49734aa5e8ba897e74fcb23",
"src/mss/domain/premium_discount.py":"43d6e7daa8e6a377a061c37c1c8c69b797904d9ce6b556f02c9e1a6bdb71348e",
"src/mss/domain/risk_profile.py":"89b97dec6cec6dbf78b94720723acc08edcf6daf6c03877ba26153a56bee8bb9",
"src/mss/domain/setup_score.py":"5d9587e45aad7ce4a80f27e0f9c99ad76961b3c3848020ae55c980e703038104",
"src/mss/domain/swing_point.py":"fa28955a2c1d06fef5e4f842f625ecaee62ff2c825f20a406bf17ede6aca2f96",
"src/mss/domain/trade_setup.py":"06f345c7a15b8b44b2cd6b8b93538b061c0004c2b0d7dfe8e23ed70746c2bd84",
"src/mss/domain/trade_signal.py":"faf2901f4a738e053fd58a56ba9ae8419af48b7fb154372ced5e16dba985782f"}
    SYMBOLS=(("BTCUSD","BITCOIN"),("ETHUSD","ETHEREUM"))

    @staticmethod
    def activation_window(merged_at_utc):
        if not isinstance(merged_at_utc,str) or not merged_at_utc.endswith("Z"): raise ValueError("mergedAt must be UTC Z")
        merged=datetime.fromisoformat(merged_at_utc[:-1]+"+00:00")
        if merged.tzinfo != timezone.utc: raise ValueError("mergedAt must be UTC")
        start=merged+timedelta(hours=24); needs_round=start.second or start.microsecond or start.minute%15
        start=start.replace(second=0,microsecond=0)
        if needs_round: start+=timedelta(minutes=15-start.minute%15)
        fmt=lambda x:x.strftime("%Y-%m-%dT%H:%M:%SZ")
        return fmt(start),fmt(start+timedelta(days=45))

    def _validate(self,g5,h6,c2,hashes):
        if g5["schema_version"]!="MSS_SPRINT92G5_CONFLUENCE_GATE_RESEARCH_CLOSURE_V1": raise RuntimeError("unexpected G5 schema")
        if h6["schema_version"]!="MSS_SPRINT92H6_IMMUTABLE_DEVELOPMENT_RESEARCH_CLOSURE_V1": raise RuntimeError("unexpected H6 schema")
        if c2["schema_version"]!="MSS_SPRINT92C2_EXTENDED_DATASET_MANIFEST_V1": raise RuntimeError("unexpected C2 schema")
        if g5["governance"]["g3_rerun_authorized"]: raise RuntimeError("G3 rerun must remain prohibited")
        if tuple(hashes)!=self.REQUIRED_STRATEGY_COMPONENT_FILES: raise RuntimeError("strategy-component identity path universe/order mismatch")
        if not all(re.fullmatch(r"[0-9a-f]{64}",v or "") for v in hashes.values()): raise RuntimeError("invalid lowercase SHA256")
        if hashes!=self.EXPECTED_STRATEGY_COMPONENT_SHA256: raise RuntimeError("strategy-component identity hash mismatch")

    def build(self,g5,h6,c2,hashes):
        self._validate(g5,h6,c2,hashes)
        return {
          "schema_version":self.VERSION,"execution_id":self.EXECUTION_ID,"baseline_commit":self.BASELINE_COMMIT,"protocol_state":self.PROTOCOL_STATE,
          "mode":"PREREGISTRATION_ONLY_NO_MT5_NO_REPLAY_NO_OUTCOME_INSPECTION_NO_PRODUCTION_CHANGE",
          "v1_supersession":{"superseded_schema_version":"MSS_SPRINT93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_PREREGISTRATION_V1","superseded_execution_id":"MSS_93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_V1","invalid_v1_boundary_utc":self.INVALID_V1_BOUNDARY,"v1_authorizes_eligible_forward_data":False,"candles_at_or_before_invalid_v1_boundary_eligible":False,"candles_collected_before_activation_manifest_eligible":False},
          "activation":{"forward_data_eligible":False,"first_eligible_candle_open_utc":None,"exclusive_experiment_end_utc":None,"activation_manifest":None,"required_precondition":"SEPARATE_PAIRED_EXECUTION_FREEZE_PR_MERGED","public_merge_metadata_required":True,"unverifiable_merge_metadata_result":self.PROTOCOL_STATE,"boundary_rule":"PUBLIC_GITHUB_MERGED_AT_UTC_PLUS_24_HOURS_ROUNDED_UP_TO_NEXT_M15_BOUNDARY","end_rule":"FIRST_ELIGIBLE_M15_CANDLE_OPEN_PLUS_EXACTLY_45_TIMES_24_HOURS_EXCLUSIVE","write_once_manifest_fields":["paired_freeze_merge_commit","paired_freeze_pr_url","paired_freeze_merged_at_utc","first_eligible_candle_open_utc","exclusive_experiment_end_utc"],"freeze_required_before_activation":["paired executor","journal schema","valuation logic","risk logic","evaluation implementation"]},
          "candidate_contract":{"baseline":"UNCHANGED_SMART_MONEY_PIPELINE","candidate":"CONFLUENCE_GATED_SMART_MONEY_PIPELINE","single_change":"ENTRY_ELIGIBLE_ONLY_WHEN_EXISTING_CONFLUENCE_ENGINE_RETURNS_VALID_DIRECTION_MATCHING_BOS","numeric_strategy_thresholds_unchanged":True,"production_pipeline_replacement":False},
          "paired_forward_shadow_contract":{"symbols":[{"canonical_symbol":c,"broker_symbol":b,"timeframe":"M15"} for c,b in self.SYMBOLS],"timebox_calendar_days":45,"extension_after_timebox":False,"no_new_entries_at_or_after_exclusive_end":True,"order_check_allowed":False,"order_send_allowed":False,"real_order_allowed":False},
          "research_evaluation_gate":{"pair_key":["canonical_symbol","decision_candle_open_utc"],"pair_population":"UNION_OF_TIMESTAMPS_WHERE_EITHER_BRANCH_OPENS_A_VIRTUAL_POSITION","no_position_branch_net_r":0.0,"retained_pair_labels":["BASELINE_ONLY","CANDIDATE_REJECTED","STATE_DIVERGENCE_CANDIDATE_ONLY"],"pair_settlement_utc":"LATER_EXIT_TIMESTAMP_OF_NON_ZERO_TRADE_MEMBERS","open_at_exclusive_end":"MARK_TO_MARKET_AT_FINAL_ELIGIBLE_M15_CLOSE_USING_FROZEN_COST_AND_VALUATION_MODEL","candidate_trade_metrics_population":"ACTUAL_CANDIDATE_POSITIONS_ONLY_EXCLUDING_ZERO_R_NO_TRADE_PAIR_MEMBERS","win_rate":"COUNT_NET_R_STRICTLY_GREATER_THAN_ZERO_DIVIDED_BY_ACTUAL_CANDIDATE_CLOSED_TRADE_COUNT_ZERO_R_IS_NON_WIN","profit_factor":"SUM_POSITIVE_NET_R_DIVIDED_BY_ABS_SUM_NEGATIVE_NET_R","profit_factor_zero_loss_behavior":{"positive_gains":"POSITIVE_INFINITY","no_positive_gains":0.0},"pooled_maximum_drawdown":"MAX_PEAK_TO_TROUGH_DECLINE_OF_CUMULATIVE_NET_R_STARTING_AT_ZERO","drawdown_order":["pair_settlement_utc","canonical_symbol","decision_candle_open_utc"],"candidate_maximum_drawdown_must_be_lte_baseline":True,"minimum_candidate_closed_trades_pooled":50,"minimum_candidate_closed_trades_per_symbol":15,"target_candidate_profit_factor":1.10,"target_candidate_win_rate":0.36,"ordinary_bootstrap":{"statistic":"PAIRED_CANDIDATE_MINUS_BASELINE_R_DIFFERENCES","stratified_by":"canonical_symbol","resamples":self.BOOTSTRAP_RESAMPLES,"seed":self.BOOTSTRAP_SEED,"per_symbol_sample_size":"ORIGINAL_PAIR_COUNT"},"moving_block_bootstrap":{"statistic":"PAIRED_CANDIDATE_MINUS_BASELINE_R_DIFFERENCES","stratified_by":"canonical_symbol","circular_blocks":True,"block_length_pair_rows":self.MOVING_BLOCK_LENGTH,"resamples":self.BOOTSTRAP_RESAMPLES,"seed":self.BOOTSTRAP_SEED,"per_symbol_sample_size":"ORIGINAL_PAIR_COUNT_BEFORE_POOLING"},"bootstrap_probability":"FRACTION_OF_RESAMPLED_POOLED_MEANS_STRICTLY_GREATER_THAN_ZERO","bootstrap_pass_probability":0.80,"unavailable_integrity_result":"INCONCLUSIVE","unavailable_conditions":["required population","ordering","valuation","sample integrity"],"tuning_or_inference_when_unavailable":False},
          "strategy_component_identity":{"identity_type":"FROZEN_STRATEGY_COMPONENT_IDENTITY_NOT_COMPLETE_PAIRED_EXECUTION_IDENTITY","baseline_commit":self.BASELINE_COMMIT,"roots":list(self.STRATEGY_COMPONENT_ROOTS),"transitive_internal_mss_path_sha256":hashes,"must_be_extended_by_write_once_activation_manifest":True,"paired_executor_present":False},
          "source_governance":{"historical_backfill":False,"development_reuse":False,"validation_reuse":False,"research_quarantine_reuse":False,"pre_protocol_true_oos_prefix_reuse":False},
          "audit":{"mt5_accessed":False,"strategy_replay_run":False,"outcomes_analyzed":False,"development_accessed":False,"validation_accessed":False,"quarantine_accessed":False,"true_oos_accessed":False,"production_behavior_changed":False,"order_check_called":False,"order_send_called":False}}
