"""Close Sprint 92F after no mechanism passes the preregistered gate."""
import hashlib,json


class MechanismResearchClosure:
    VERSION="MSS_SPRINT92F3_MECHANISM_RESEARCH_CLOSURE_V1"
    @staticmethod
    def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    def build(self,protocol,analysis,e8):
        return {'schema_version':self.VERSION,'mode':'MECHANISM_RESEARCH_CLOSURE_ONLY','baseline_commit':'9b4b8a3',
            'source_artifacts':{'f1_payload_sha256':self.digest(protocol),'f2_payload_sha256':self.digest(analysis),'e8_payload_sha256':self.digest(e8)},
            'closed_branch':{'name':'UNCHANGED_STRATEGY_MECHANISM_DISCOVERY','locked_hypothesis_count':len(protocol['locked_hypothesis_families']),
                'advanced_mechanisms':analysis['advanced_mechanisms'],'decision':analysis['conclusion']['decision'],
                'scientific_conclusion':'NO_PREREGISTERED_ENTRY_AVAILABLE_MECHANISM_WAS_STABLE_ACROSS_AT_LEAST_SIX_OF_EIGHT_SYMBOLS',
                'further_threshold_search_on_consumed_development_trades':'PROHIBITED_TO_AVOID_DATA_MINING'},
            'production_governance':{'strategy_change_authorized':False,'symbol_filter_change_authorized':False,'risk_change_authorized':False,
                'production_status':'UNCHANGED','reason':'NO_EXTERNAL_CONFIRMATION_AND_NO_STABLE_DEVELOPMENT_MECHANISM'},
            'data_governance':{'development_outcomes_exposed':True,'validation_remains_closed_to_new_analysis':True,
                'external_history_exposure_ledger_preserved':True,'true_future_oos_remains_sealed':True},
            'allowed_future_work':['FORMULATE_A_NEW_CAUSAL_STRATEGY_HYPOTHESIS_FROM_MARKET_MICROSTRUCTURE_OR_EXTERNAL_THEORY','IMPLEMENT_ONLY_AFTER_A_SEPARATE_SPEC_AND_COMMIT','USE_NEW_VALIDATION_DATA_ONLY_AFTER_PREREGISTRATION'],
            'not_allowed_future_work':['REPEAT_F2_WITH_NEW_CUTPOINTS','PROMOTE_H1_DIRECTION_DESPITE_FIVE_OF_EIGHT_CONSISTENCY','REUSE_E4_OR_E7_AS_CONFIRMATORY','UNSEAL_TRUE_OOS_FOR_EXPLORATION'],
            'audit':{'strategy_replay_run':False,'outcomes_recomputed':False,'mt5_accessed':False,'strategy_code_changed':False,'true_future_oos_used':False},
            'acceptance':{'no_mechanism_advanced':not analysis['advanced_mechanisms'],'f2_decision_respected':analysis['conclusion']['decision']=='NO_STRATEGY_REVISION_ADVANCED','external_closure_respected':e8['final_conclusions']['production_decision']=='NO_STRATEGY_OR_SYMBOL_FILTER_CHANGE','production_change_justified':False}}
