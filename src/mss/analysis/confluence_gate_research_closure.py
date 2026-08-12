"""Close Sprint 92G without converting an operational failure into evidence."""
import hashlib,json


class ConfluenceGateResearchClosure:
    VERSION="MSS_SPRINT92G5_CONFLUENCE_GATE_RESEARCH_CLOSURE_V1"
    @staticmethod
    def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    def build(self,g1,g2,g3,g4):
        return {'schema_version':self.VERSION,'mode':'CONFLUENCE_GATE_RESEARCH_CLOSURE_ONLY','baseline_commit':'208dfcb',
            'source_artifacts':{name:{'schema_version':value['schema_version'],'payload_sha256':self.digest(value)} for name,value in {'g1':g1,'g2':g2,'g3':g3,'g4':g4}.items()},
            'hypothesis_status':{'id':g1['causal_hypothesis']['id'],'status':'NOT_EVALUATED_DUE_TO_AUTHORITATIVE_SOURCE_INTEGRITY_FAILURE',
                'statistically_rejected':False,'statistically_confirmed':False,'candidate_outcomes_interpretable':False,
                'reason':'G3_STOPPED_BEFORE_COMPLETE_EIGHT_SYMBOL_EVALUATION_AND_PARTIAL_OUTCOMES_WERE_NOT_REPORTED'},
            'source_diagnosis':{'full_window_exact_symbols':g4['summary']['exact_full_reproduction_count'],
                'full_window_drifted_symbols':g4['summary']['drifted_symbols'],'development_slice_exact_symbols':g4['summary']['development_slice_reproduction_count'],
                'interpretation':'BROKER_REVISED_POST_DEVELOPMENT_CONTENT_FOR_THREE_SYMBOLS_WHILE_ALL_EIGHT_DEVELOPMENT_SLICES_REMAIN_HASH_EXACT'},
            'governance':{'g3_rerun_authorized':False,'validation_access_authorized':False,'production_change_authorized':False,
                'candidate_pipeline_status':'RESEARCH_ONLY_UNVALIDATED','baseline_production_status':'UNCHANGED',
                'future_retest_requires':'NEW_HYPOTHESIS_VERSION_AND_NEW_PREREGISTERED_EXECUTION_ID; MUST NOT BE_LABELLED_G3_RERUN'},
            'data_governance':{'partial_g3_outcomes_used':False,'validation_remains_sealed':True,'external_history_remains_out_of_scope':True,'true_future_oos_remains_sealed':True},
            'allowed_next_actions':['ARCHIVE_G1_CANDIDATE_AS_UNEVALUATED','DESIGN_SOURCE_IMMUTABILITY_STORAGE_BEFORE_ANY_NEW_STRATEGY_EXPERIMENT','ONLY_THEN_PREREGISTER_A_DISTINCT_FUTURE_EXPERIMENT'],
            'audit':{'strategy_replay_run':False,'outcomes_recomputed':False,'mt5_accessed':False,'validation_accessed':False,'true_future_oos_used':False,'production_behavior_changed':False},
            'acceptance':{'g3_failure_preserved':g3['status']=='RUN_FAILED_SOURCE_MISMATCH','g3_rerun_remains_prohibited':g3['rerun_prohibited'] and not g4['summary']['g3_rerun_allowed'],'development_drift_diagnosed':g4['summary']['development_slice_reproduction_count']==8,'no_false_scientific_rejection':True}}
