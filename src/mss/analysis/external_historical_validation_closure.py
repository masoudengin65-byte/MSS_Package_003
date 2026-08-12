"""Deterministic closure of the Sprint 92E external-history program."""
import hashlib,json


class ExternalHistoricalValidationClosure:
    VERSION="MSS_SPRINT92E8_EXTERNAL_HISTORICAL_VALIDATION_CLOSURE_V1"
    @staticmethod
    def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

    def build(self,sources):
        e4,e5,e6,e7=(sources[x] for x in ('e4','e5','e6','e7'))
        first=e4['confirmatory_usdjpy']['decision']; family=e7['family_decision']; positive=e5['evidence_tiers']['EXPLORATORY_POSITIVE_UNCERTAIN']
        return {'schema_version':self.VERSION,'mode':'EXTERNAL_HISTORY_RESEARCH_CLOSURE_ONLY','baseline_commit':'78595e6',
            'source_artifacts':{k:{'schema_version':v['schema_version'],'payload_sha256':self.digest(v)} for k,v in sources.items()},
            'evidence_summary':{'initial_confirmatory_symbol':'USDJPY','initial_confirmatory_decision':first['decision'],
                'initial_confirmatory_all_pass':first['all_pass'],'exploratory_symbol_count':21,
                'exploratory_positive_uncertain_symbols':positive,'exploratory_strong_symbols':e5['evidence_tiers']['EXPLORATORY_STRONG_NOT_CONFIRMATORY'],
                'second_window_confirmatory_family':e6['selection']['symbols'],'second_window_confirmed_symbols':family['confirmed_symbols'],
                'second_window_not_confirmed_symbols':family['not_confirmed_symbols']},
            'final_conclusions':{'confirmed_robust_positive_symbols':[],'scientific_conclusion':'NO_SYMBOL_CONFIRMED_ACROSS_PREREGISTERED_EXTERNAL_HISTORICAL_TESTS',
                'production_decision':'NO_STRATEGY_OR_SYMBOL_FILTER_CHANGE','unchanged_strategy_external_validation_status':'NOT_CONFIRMED',
                'remaining_old_history_status':'SEALED_FROM_ADDITIONAL_OUTCOME_MINING_UNLESS_A_NEW_CAUSAL_HYPOTHESIS_AND_PROTOCOL_ARE_COMMITTED_FIRST'},
            'data_exposure_ledger':{'first_10000_candles_consumed_for_all_22_symbols':True,
                'candles_10001_through_20000_consumed_for_six_e6_symbols':True,
                'candles_10001_through_20000_unconsumed_for_other_16_symbols':True,
                'candles_after_20000_not_analyzed_in_sprint92e':True,'true_future_oos_remains_sealed':True},
            'governance':{'repeat_e4_prohibited':True,'repeat_e7_prohibited':True,'parameter_tuning_on_consumed_windows_prohibited':True,
                'post_hoc_promotion_prohibited':True,'true_oos_protocol_preserved_not_executed':True,
                'recommended_next_action':'PAUSE_UNCHANGED_STRATEGY_CONFIRMATION; FORMULATE_MECHANISTIC_STRATEGY_REVISION_USING_DEVELOPMENT_DATA_ONLY_AND_PREREGISTER_BEFORE_ANY_NEW_VALIDATION'},
            'audit':{'mt5_accessed':False,'history_downloaded':False,'strategy_replay_run':False,'outcomes_recomputed':False,
                'true_future_oos_used':False,'production_behavior_changed':False},
            'acceptance':{'e4_usdjpy_not_confirmed':not first['all_pass'],'e5_has_no_strong_symbol':not e5['evidence_tiers']['EXPLORATORY_STRONG_NOT_CONFIRMATORY'],
                'e7_has_no_confirmed_symbol':not family['confirmed_symbols'],'all_six_e7_symbols_reported':len(family['not_confirmed_symbols'])==6,
                'production_change_justified':False,'true_future_oos_preserved':True}}
