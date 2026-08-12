"""Preregister a causal confluence-gate hypothesis from existing architecture."""
import hashlib


class ConfluenceGateHypothesisPreregistration:
    VERSION="MSS_SPRINT92G1_CONFLUENCE_GATE_HYPOTHESIS_PREREGISTRATION_V1"
    @staticmethod
    def file_hash(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    def build(self,paths):
        return {'schema_version':self.VERSION,'mode':'CAUSAL_HYPOTHESIS_PREREGISTRATION_ONLY','baseline_commit':'794cab3',
            'observed_architecture':{'historical_entry_rule':'pipeline_result.valid AND pipeline_result.bos_detected','smart_money_recommendation':'TRADE_ON_ANY_DETECTED_BOS',
                'existing_unused_confluence_contract':'DIRECTION_ALIGNED_BOS_AND_DISPLACEMENT_AND_ORDER_BLOCK_AND_FAIR_VALUE_GAP',
                'structural_gap':'HISTORICAL_ENTRY_PATH_DOES_NOT_REQUIRE_EXISTING_CONFLUENCE_ENGINE_SIGNAL'},
            'causal_hypothesis':{'id':'G1_FALSE_BREAKOUT_CONFLUENCE_GATE','claim':'NAKED_BOS_ENTRIES_INCLUDE_FALSE_BREAKOUTS; REQUIRING_EXISTING_DIRECTION_ALIGNED_CONFLUENCE_REDUCES_FALSE_ENTRIES AND IMPROVES OUT_OF_SAMPLE_MEAN_R',
                'mechanism':'DISPLACEMENT_SUPPORTS_IMPULSE; ORDER_BLOCK_AND_FVG_REQUIRE_LOCATION_AND_IMBALANCE CONSISTENT_WITH_THE_BOS_DIRECTION',
                'falsifiable':True,'not_derived_from_f2_threshold_search':True},
            'candidate_contract':{'baseline':'UNCHANGED_COMMIT_06377a7','single_change':'ENTRY_ELIGIBLE_ONLY_WHEN_EXISTING_CONFLUENCE_ENGINE_RETURNS_VALID_DIRECTION_MATCHING_BOS','unchanged':['swing detection','structure detection','BOS detection','stop placement','next-candle entry','risk 1%','reward-risk 2.0','valuation','ambiguous exit STOP_LOSS_FIRST','one-position policy'],
                'no_new_numeric_thresholds':True,'no_symbol_specific_rules':True,'no_direction_specific_rules':True},
            'development_test_protocol':{'dataset':'SPRINT_92C3_DEVELOPMENT_30000_CANDLES_PER_EIGHT_SYMBOLS','paired_baseline_required':True,'candidate_replay_count':1,'symbols':['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD','XAUUSD','BTCUSD','ETHUSD'],
                'primary_metric':'MEAN_R_DIFFERENCE_CANDIDATE_MINUS_BASELINE','secondary_metrics':['closed trades','net PnL','profit factor','expectancy','maximum drawdown','BUY net PnL','SELL net PnL'],
                'minimum_candidate_closed_trades_per_symbol':50,'minimum_pooled_candidate_closed_trades':400,
                'advance_only_if_all':['pooled mean-R difference > 0','ordinary and moving-block bootstrap 95% lower bounds for pooled mean-R difference > 0','candidate mean R > baseline in at least 6 of 8 symbols','candidate net PnL > baseline in at least 6 of 8 symbols','BUY and SELL pooled net PnL > 0','maximum realized loss <= 1.25%','zero integrity or lookahead failures'],
                'failure_decision':'REJECT_CONFLUENCE_GATE_NO_VALIDATION_ACCESS','pass_decision':'WRITE_SEPARATE_VALIDATION_PREREGISTRATION_BEFORE_ACCESS'},
            'implementation_sequence':['G2_EXPOSE_EXISTING_CONFLUENCE_SIGNAL_WITH_UNIT_TESTS','COMMIT_IMPLEMENTATION_BEFORE_OUTCOME_REPLAY','G3_RUN_ONE_DEVELOPMENT_PAIRED_REPLAY','DO_NOT_ACCESS_VALIDATION_UNLESS_G3_ALL_PASS'],
            'prohibitions':['no optimization of confluence components','no partial-component search','no threshold search','no symbol exclusion','no validation access','no external-history access','no true-OOS access','no production change'],
            'source_file_sha256':{name:self.file_hash(path) for name,path in paths.items()},
            'audit':{'outcomes_analyzed':False,'strategy_replay_run':False,'strategy_code_changed':False,'mt5_accessed':False,'validation_accessed':False,'true_future_oos_used':False}}
