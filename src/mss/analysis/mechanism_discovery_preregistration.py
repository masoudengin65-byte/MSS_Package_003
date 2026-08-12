"""Preregister bounded development-only failure-mechanism discovery."""
import hashlib,json


class MechanismDiscoveryPreregistration:
    VERSION="MSS_SPRINT92F1_MECHANISM_DISCOVERY_PREREGISTRATION_V1"
    SYMBOLS=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD","BTCUSD","ETHUSD")
    @staticmethod
    def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

    def build(self,c3,e8):
        fields=set(c3['segments']['DEVELOPMENT']['trades'][0])
        required={'canonical_symbol','direction','entry_time','entry_price','stop_loss','spread','slippage','score','confidence','shadow_score','shadow_confidence','detector_states','profit','r_multiple','status'}
        return {'schema_version':self.VERSION,'mode':'PREREGISTRATION_ONLY_NO_ANALYSIS_NO_REPLAY','baseline_commit':'1b8395c',
            'research_question':'WHICH_ENTRY_AVAILABLE_MECHANISMS_EXPLAIN_FAILURE_OF_THE_UNCHANGED_STRATEGY',
            'data_scope':{'source_segment':'SPRINT_92C3_DEVELOPMENT_ONLY','symbols':list(self.SYMBOLS),'unit':'CLOSED_TRADE',
                'validation_segment_access_prohibited':True,'sprint92e_windows_access_prohibited':True,'true_future_oos_access_prohibited':True,
                'development_closed_trade_count':sum(x['closed_trades'] for x in c3['segments']['DEVELOPMENT']['per_symbol_results'])},
            'locked_hypothesis_families':[
                {'id':'H1_DIRECTION','entry_available_driver':'direction','cuts':['BUY','SELL'],'expected_pattern':'ONE_DIRECTION_CONCENTRATES_NEGATIVE_EXPECTANCY'},
                {'id':'H2_COST_BURDEN','entry_available_driver':'(spread+slippage)/abs(entry_price-stop_loss)','cuts':'POOLED_DEVELOPMENT_QUARTILES_LOCKED_BEFORE_OUTCOME_JOIN','expected_pattern':'EXPECTANCY_DECREASES_AS_COST_BURDEN_INCREASES'},
                {'id':'H3_LEGACY_SCORE','entry_available_driver':'score','cuts':'POOLED_DEVELOPMENT_QUINTILES_LOCKED_BEFORE_OUTCOME_JOIN','expected_pattern':'MEAN_R_MONOTONICALLY_INCREASES_WITH_SCORE'},
                {'id':'H4_SHADOW_SCORE','entry_available_driver':'shadow_score','cuts':'POOLED_DEVELOPMENT_QUINTILES_LOCKED_BEFORE_OUTCOME_JOIN','expected_pattern':'SHADOW_SCORE_HAS_STRONGER_MONOTONIC_ASSOCIATION_WITH_R_THAN_LEGACY_SCORE'},
                {'id':'H5_UTC_SESSION','entry_available_driver':'entry_time_utc_hour','cuts':{'ASIA':[0,8],'EUROPE':[8,16],'AMERICAS':[16,24]},'expected_pattern':'NEGATIVE_EXPECTANCY_IS_CONCENTRATED_IN_A_PREDEFINED_SESSION'}],
            'statistics':{'report_per_symbol_and_pooled':True,'minimum_subgroup_trades':30,'metrics':['count','net PnL','expectancy','mean R','profit factor','win rate'],
                'uncertainty':['ordinary bootstrap 95% interval','circular moving-block bootstrap 95% interval'],
                'multiplicity':'BENJAMINI_HOCHBERG_FDR_0.05_ACROSS_LOCKED_HYPOTHESIS_SYMBOL_TESTS','effect_sizes_required':True,
                'missing_or_small_subgroups':'REPORT_AS_INSUFFICIENT_NEVER_DROP'},
            'candidate_gate':{'maximum_mechanisms_advanced':2,'all_required':['entry-available and causal-plausible','same direction in at least 6 of 8 symbols','pooled ordinary and block bootstrap support','minimum subgroup sizes met','not driven by one asset class'],
                'if_gate_fails':'NO_STRATEGY_REVISION_ADVANCED','if_gate_passes':'WRITE_SEPARATE_IMPLEMENTATION_SPEC_BEFORE_CODE_CHANGE'},
            'prohibitions':['no threshold optimization','no symbol exclusion','no strategy code change','no validation replay','no external-history replay','no production claim'],
            'source_hashes':{'c3_payload_sha256':self.digest(c3),'e8_payload_sha256':self.digest(e8)},
            'audit':{'strategy_replay_run':False,'mechanism_outcomes_analyzed':False,'strategy_code_changed':False,'mt5_accessed':False,'true_future_oos_used':False},
            'acceptance':{'required_fields_available':required.issubset(fields),'external_validation_closed_not_confirmed':e8['final_conclusions']['unchanged_strategy_external_validation_status']=='NOT_CONFIRMED','development_only_locked':True}}
