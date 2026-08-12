"""Preregister the second-window confirmatory family before price inspection."""

import hashlib,json


class ExternalHistoricalConfirmatoryPreregistration:
    VERSION="MSS_SPRINT92E6_EXTERNAL_HISTORICAL_CONFIRMATORY_PREREGISTRATION_V1"
    CANDIDATES=("GBPUSD","BTCUSD","EURGBP","CHFJPY","XAUUSD","NAS100")

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

    def build(self,freeze,analysis):
        rows={x["canonical_symbol"]:x for x in freeze["original_universe_older_windows"]+freeze["exploratory_universe_windows"]}
        selected=tuple(analysis["evidence_tiers"]["EXPLORATORY_POSITIVE_UNCERTAIN"])
        return {"schema_version":self.VERSION,"mode":"PREREGISTRATION_ONLY_NO_PRICE_INSPECTION_NO_REPLAY","baseline_commit":"47bed7c",
            "selection":{"rule":"ALL_E5_EXPLORATORY_POSITIVE_UNCERTAIN_SYMBOLS","symbols":list(self.CANDIDATES),
                "selection_matches_frozen_e5_tier":set(selected)==set(self.CANDIDATES),"post_selection_inference_acknowledged":True},
            "confirmatory_family":{"hypothesis_count":6,"familywise_alpha":0.05,"correction":"BONFERRONI",
                "per_symbol_alpha":0.05/6,"per_symbol_two_sided_confidence_percent":100*(1-0.05/6),
                "window_rule":"CANDLES_10001_THROUGH_20000_CHRONOLOGICAL_FROM_E1_FROZEN_WINDOW",
                "candles_per_symbol":10000,"window_previously_replayed_or_analyzed":False,"minimum_closed_trades":100,
                "symbols":[{"canonical_symbol":s,"broker_symbol":rows[s]["broker_symbol"],"asset_class":rows[s]["asset_class"],
                    "full_frozen_window_sha256":rows[s]["ohlcv_sha256"],"full_frozen_window_count":rows[s]["returned_count"],
                    "slice_start_index_zero_based":10000,"slice_end_index_exclusive":20000} for s in self.CANDIDATES]},
            "strategy_contract":{"code_commit":"06377a7","timeframe":"M15","warmup":200,"lookback":500,"starting_balance":10000.0,
                "risk_percent":1.0,"reward_risk_ratio":2.0,"entry":"NEXT_CANDLE_OPEN","ambiguous_exit":"STOP_LOSS_FIRST",
                "spread_points":"HISTORICAL_CANDLE_OR_FROZEN_BROKER_METADATA","commission_per_lot":0.0,"slippage_points":1.0,"optimization":False,"real_orders":False},
            "per_symbol_all_pass_requirements":["exact full frozen source hash and exact second slice","at least 100 closed trades",
                "observed expectancy > 0","observed mean R > 0","profit factor > 1",
                "Bonferroni-adjusted ordinary bootstrap expectancy and mean-R lower bounds > 0",
                "Bonferroni-adjusted moving-block bootstrap expectancy and mean-R lower bounds > 0",
                "BUY net PnL > 0","SELL net PnL > 0","maximum realized loss <= 1.25% pre-trade equity",
                "zero lookahead, valuation, reconciliation, or integrity failures"],
            "decision_rule":{"symbol_pass":"CONFIRMED_WITHIN_SIX_SYMBOL_FAMILY_REQUIRES_SEPARATE_PRODUCTION_GOVERNANCE",
                "symbol_fail":"NOT_CONFIRMED_NO_PRODUCTION_CHANGE","family_reporting":"REPORT_ALL_SIX_WITH_NO_POST_HOC_EXCLUSION"},
            "execution_policy":{"authoritative_family_runs":1,"inspect_second_window_prices_before_run":False,"interim_peeking":False,
                "parameter_tuning":False,"threshold_tuning":False,"failed_and_null_results_preserved":True,"rerun_prohibited":True},
            "source_hashes":{"freeze_payload_sha256":self.digest(freeze),"e5_payload_sha256":self.digest(analysis)},
            "audit":{"mt5_accessed":False,"history_downloaded":False,"second_window_ohlc_inspected":False,"strategy_replay_run":False,
                "outcomes_analyzed":False,"true_future_oos_used":False,"production_behavior_changed":False}}
