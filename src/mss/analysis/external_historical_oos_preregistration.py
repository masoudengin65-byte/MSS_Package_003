"""Preregister the independent older-history replay before outcome inspection."""

import hashlib, json


class ExternalHistoricalOosPreregistration:
    VERSION="MSS_SPRINT92E2_EXTERNAL_HISTORICAL_OOS_PREREGISTRATION_V1"

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

    def build(self, freeze):
        original={row['canonical_symbol']:row for row in freeze['original_universe_older_windows']}
        exploratory={row['canonical_symbol']:row for row in freeze['exploratory_universe_windows']}
        return {'schema_version':self.VERSION,'mode':'PREREGISTRATION_ONLY_NO_REPLAY',
          'baseline_commit':'2b909f0','freeze_schema':freeze['schema_version'],'freeze_payload_sha256':self.digest(freeze),
          'confirmatory_test':{
            'symbol':'USDJPY','source_window_sha256':original['USDJPY']['ohlcv_sha256'],
            'snapshot_rule':'FIRST_10000_CHRONOLOGICAL_CANDLES_FROM_FROZEN_OLDER_WINDOW',
            'candle_count':10000,'minimum_closed_trades':100,
            'strategy_contract':{'code_commit':'06377a7','timeframe':'M15','warmup':200,'lookback':500,
              'starting_balance':10000.0,'risk_percent':1.0,'reward_risk_ratio':2.0,
              'entry':'NEXT_CANDLE_OPEN','ambiguous_exit':'STOP_LOSS_FIRST','optimization':False,'real_orders':False},
            'all_pass_requirements':['source hash and exact window match','observed expectancy > 0','observed mean R > 0',
              'profit factor > 1','ordinary bootstrap 95% expectancy and mean-R lower bounds > 0',
              'moving-block bootstrap 95% expectancy and mean-R lower bounds > 0','BUY net PnL > 0','SELL net PnL > 0',
              'maximum realized loss <= 1.25% pre-trade equity','zero lookahead, valuation, reconciliation, or integrity failures'],
            'decision_if_all_pass':'CONFIRMED_RESEARCH_CANDIDATE_REQUIRES_SEPARATE_PRODUCTION_GOVERNANCE',
            'decision_if_any_fail':'NOT_CONFIRMED_NO_PRODUCTION_CHANGE'},
          'exploratory_tests':{
            'symbols':sorted([s for s in original if s!='USDJPY']+list(exploratory)),
            'window_rule':'FIRST_10000_CHRONOLOGICAL_CANDLES_FROM_EACH_FROZEN_WINDOW',
            'report_all_symbols':True,'post_hoc_symbol_exclusion':False,'production_claims_allowed':False,
            'metrics':['closed trades','net PnL','expectancy','mean R','profit factor','win rate','maximum drawdown','risk audit','rejections']},
          'execution_policy':{'authoritative_runs':1,'inspect_prices_before_run':False,'interim_peeking':False,
            'parameter_tuning':False,'threshold_tuning':False,'symbol_selection_after_results':False,
            'failed_and_null_results_must_be_preserved':True},
          'audit':{'mt5_accessed':False,'history_downloaded':False,'strategy_replay_run':False,
            'outcomes_analyzed':False,'true_future_oos_used':False,'production_behavior_changed':False},
          'acceptance':{'freeze_has_8_original':len(original)==8,'freeze_has_14_exploratory':len(exploratory)==14,
            'all_windows_eligible':all(row['eligible_for_future_replay'] for row in original.values()) and all(row['eligible_for_future_replay'] for row in exploratory.values()),
            'usdjpy_is_only_confirmatory':True,'no_replay_or_outcome_inspection':True}}
