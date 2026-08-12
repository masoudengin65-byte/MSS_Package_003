"""Bonferroni-adjusted inference for the preregistered E.7 replay."""

import random
from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit
from mss.analysis.external_historical_oos_replay import ExternalHistoricalOOSReplay


class ExternalHistoricalConfirmatoryReplay:
    VERSION="MSS_SPRINT92E7_EXTERNAL_HISTORICAL_CONFIRMATORY_REPLAY_V1"

    @staticmethod
    def adjusted_bootstrap(trades,method,confidence,seed=BootstrapRobustnessAudit.DEFAULT_SEED,resamples=BootstrapRobustnessAudit.DEFAULT_RESAMPLES,block_length=BootstrapRobustnessAudit.BLOCK_LENGTH,label="sample"):
        normalized=BootstrapRobustnessAudit.normalize_trades({"trades":trades}); n=len(normalized)
        if n<BootstrapRobustnessAudit.MIN_SAMPLE: return {"available":False,"sample_size":n,"reason":"INSUFFICIENT_TRADES"}
        ordered=sorted(normalized,key=lambda x:(x["entry_time"],x["exit_time"],x["trade_id"])); profits=[x["realized_pnl"] for x in ordered]; rs=[x["r_multiple"] for x in ordered]; rng=random.Random(BootstrapRobustnessAudit._derived_seed(seed,label)); ex=[]; mr=[]
        for _ in range(resamples):
            indexes=BootstrapRobustnessAudit._sample_indices(rng,n,method,block_length); ex.append(sum(profits[i] for i in indexes)/n); mr.append(sum(rs[i] for i in indexes)/n)
        return {"available":True,"method":method,"sample_size":n,"resamples":resamples,"seed":seed,"confidence_percent":confidence*100,
            "expectancy":{"point_estimate":sum(profits)/n,"interval":BootstrapRobustnessAudit.interval(ex,confidence)},
            "mean_r":{"point_estimate":sum(rs)/n,"interval":BootstrapRobustnessAudit.interval(mr,confidence)}}

    @staticmethod
    def decide(summary,trades,ordinary,block,integrity):
        buy=ExternalHistoricalOOSReplay.direction_net(trades,"BUY"); sell=ExternalHistoricalOOSReplay.direction_net(trades,"SELL")
        requirements={"minimum_100_closed_trades":summary["closed_trades"]>=100,"observed_expectancy_positive":summary["expectancy"]>0,
            "observed_mean_r_positive":summary["average_r"]>0,"profit_factor_above_one":summary["profit_factor"]>1,
            "adjusted_ordinary_expectancy_lower_positive":ordinary.get("available",False) and ordinary["expectancy"]["interval"]["lower"]>0,
            "adjusted_ordinary_mean_r_lower_positive":ordinary.get("available",False) and ordinary["mean_r"]["interval"]["lower"]>0,
            "adjusted_block_expectancy_lower_positive":block.get("available",False) and block["expectancy"]["interval"]["lower"]>0,
            "adjusted_block_mean_r_lower_positive":block.get("available",False) and block["mean_r"]["interval"]["lower"]>0,
            "buy_net_pnl_positive":buy>0,"sell_net_pnl_positive":sell>0,
            "maximum_realized_loss_within_1_25_percent":summary["risk_audit"]["maximum_realized_loss_percent"]<=1.25,
            "zero_integrity_failures":all(integrity.values())}
        passed=all(requirements.values())
        return {"all_pass":passed,"requirements":requirements,"buy_net_pnl":buy,"sell_net_pnl":sell,
            "decision":"CONFIRMED_WITHIN_SIX_SYMBOL_FAMILY_REQUIRES_SEPARATE_PRODUCTION_GOVERNANCE" if passed else "NOT_CONFIRMED_NO_PRODUCTION_CHANGE"}
