"""Post-run analysis of all preregistered exploratory symbols; no replay."""

from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit


class ExternalHistoricalExploratoryAnalysis:
    VERSION="MSS_SPRINT92E5_EXTERNAL_HISTORICAL_EXPLORATORY_ANALYSIS_V1"

    @staticmethod
    def net(trades,direction):
        return round(sum(float(x["profit"]) for x in trades if x["status"]=="CLOSED" and x["direction"]==direction),2)

    @staticmethod
    def lower(result,metric):
        return result["bootstrap_metrics"][metric]["ci_95"]["lower"] if result.get("available") else None

    def analyze_symbol(self,summary,trades):
        normalized=BootstrapRobustnessAudit.normalize_trades({"trades":trades})
        audit=BootstrapRobustnessAudit()
        ordinary=audit.bootstrap(normalized,label=f"E5:{summary['canonical_symbol']}:ordinary",method="ordinary")
        block=audit.bootstrap(normalized,label=f"E5:{summary['canonical_symbol']}:block",method="moving_block_circular")
        buy=self.net(trades,"BUY"); sell=self.net(trades,"SELL")
        strong=(summary["closed_trades"]>=100 and summary["expectancy"]>0 and summary["average_r"]>0 and summary["profit_factor"]>1
            and self.lower(ordinary,"expectancy")>0 and self.lower(ordinary,"mean_r")>0
            and self.lower(block,"expectancy")>0 and self.lower(block,"mean_r")>0
            and buy>0 and sell>0 and summary["risk_audit"]["maximum_realized_loss_percent"]<=1.25)
        if strong: tier="EXPLORATORY_STRONG_NOT_CONFIRMATORY"
        elif summary["net_profit"]>0 and summary["expectancy"]>0 and summary["average_r"]>0 and summary["profit_factor"]>1: tier="EXPLORATORY_POSITIVE_UNCERTAIN"
        else: tier="EXPLORATORY_NEGATIVE_OR_NULL"
        return {"canonical_symbol":summary["canonical_symbol"],"asset_class":summary["asset_class"],"closed_trades":summary["closed_trades"],
            "net_profit":summary["net_profit"],"expectancy":summary["expectancy"],"average_r":summary["average_r"],
            "profit_factor":summary["profit_factor"],"win_rate_percent":summary["win_rate_percent"],
            "maximum_drawdown_percent":summary["maximum_drawdown_percent"],"buy_net_pnl":buy,"sell_net_pnl":sell,
            "ordinary_expectancy_ci95_lower":self.lower(ordinary,"expectancy"),"ordinary_mean_r_ci95_lower":self.lower(ordinary,"mean_r"),
            "block_expectancy_ci95_lower":self.lower(block,"expectancy"),"block_mean_r_ci95_lower":self.lower(block,"mean_r"),
            "maximum_realized_loss_percent":summary["risk_audit"]["maximum_realized_loss_percent"],"evidence_tier":tier,
            "ordinary_bootstrap":ordinary,"moving_block_bootstrap":block}

    def build(self,replay,protocol,replay_sha256,protocol_sha256):
        exploratory=set(protocol["exploratory_tests"]["symbols"]); summaries={x["canonical_symbol"]:x for x in replay["per_symbol_results"]}
        rows=[]
        for symbol in sorted(exploratory):
            trades=[x for x in replay["trades"] if x["canonical_symbol"]==symbol]
            rows.append(self.analyze_symbol(summaries[symbol],trades))
        ranked=sorted(rows,key=lambda x:(x["net_profit"],x["profit_factor"]),reverse=True)
        tiers={name:[x["canonical_symbol"] for x in ranked if x["evidence_tier"]==name] for name in ("EXPLORATORY_STRONG_NOT_CONFIRMATORY","EXPLORATORY_POSITIVE_UNCERTAIN","EXPLORATORY_NEGATIVE_OR_NULL")}
        return {"schema_version":self.VERSION,"mode":"POST_RUN_FROZEN_RESULTS_ANALYSIS_ONLY","source":{"replay_sha256":replay_sha256,"protocol_sha256":protocol_sha256,"authoritative_replay_count_added":0},
            "scope":{"symbol_count":len(rows),"confirmatory_usdjpy_excluded":True,"post_hoc_symbol_exclusion":False,"production_claims_allowed":False},
            "evidence_tiers":tiers,"ranking_by_net_profit":[x["canonical_symbol"] for x in ranked],"symbols":ranked,
            "conclusion":{"strong_count":len(tiers["EXPLORATORY_STRONG_NOT_CONFIRMATORY"]),"positive_uncertain_count":len(tiers["EXPLORATORY_POSITIVE_UNCERTAIN"]),"negative_or_null_count":len(tiers["EXPLORATORY_NEGATIVE_OR_NULL"]),
                "production_change_justified":False,"next_action":"PREREGISTER_ANY_CONFIRMATORY_FOLLOWUP_ON_A_NEW_UNEXPOSED_WINDOW"},
            "audit":{"strategy_replay_run":False,"outcomes_recomputed":False,"all_21_symbols_reported":len(rows)==21,"true_future_oos_used":False,"parameter_tuning":False}}
