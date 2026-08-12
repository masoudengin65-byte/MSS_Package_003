"""Reporting and preregistered decision logic for Sprint 92E.4."""

from dataclasses import asdict

from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit
from mss.analysis.multi_asset_historical_replay_v2 import MultiAssetHistoricalReplayV2


class ExternalHistoricalOOSReplay:
    VERSION = "MSS_SPRINT92E4_EXTERNAL_HISTORICAL_OOS_REPLAY_V1"

    @staticmethod
    def trade_rows(symbol, broker, asset_class, trades):
        rows=[]
        for trade in trades:
            row=asdict(trade)
            row.pop("shadow_score_result",None); row.pop("context_snapshot",None)
            row.update(canonical_symbol=symbol,broker_symbol=broker,asset_class=asset_class)
            for key in ("signal_time","entry_time","exit_time","entry_conversion_time","exit_conversion_time"):
                row[key]=row[key].isoformat() if row.get(key) else None
            rows.append(row)
        return rows

    @staticmethod
    def direction_net(trades, direction):
        return round(sum(float(row["profit"]) for row in trades if row["status"]=="CLOSED" and row["direction"]==direction),2)

    def confirmation(self, summary, trades, ordinary, block, integrity):
        risk=summary["risk_audit"]
        requirements={
            "minimum_100_closed_trades":summary["closed_trades"]>=100,
            "observed_expectancy_positive":summary["expectancy"]>0,
            "observed_mean_r_positive":summary["average_r"]>0,
            "profit_factor_above_one":summary["profit_factor"]>1,
            "ordinary_expectancy_ci95_lower_positive":ordinary.get("available",False) and ordinary["bootstrap_metrics"]["expectancy"]["ci_95"]["lower"]>0,
            "ordinary_mean_r_ci95_lower_positive":ordinary.get("available",False) and ordinary["bootstrap_metrics"]["mean_r"]["ci_95"]["lower"]>0,
            "block_expectancy_ci95_lower_positive":block.get("available",False) and block["bootstrap_metrics"]["expectancy"]["ci_95"]["lower"]>0,
            "block_mean_r_ci95_lower_positive":block.get("available",False) and block["bootstrap_metrics"]["mean_r"]["ci_95"]["lower"]>0,
            "buy_net_pnl_positive":self.direction_net(trades,"BUY")>0,
            "sell_net_pnl_positive":self.direction_net(trades,"SELL")>0,
            "maximum_realized_loss_within_1_25_percent":risk["maximum_realized_loss_percent"]<=1.25,
            "zero_integrity_failures":all(integrity.values()),
        }
        passed=all(requirements.values())
        return {"requirements":requirements,"all_pass":passed,
            "decision":"CONFIRMED_RESEARCH_CANDIDATE_REQUIRES_SEPARATE_PRODUCTION_GOVERNANCE" if passed else "NOT_CONFIRMED_NO_PRODUCTION_CHANGE",
            "buy_net_pnl":self.direction_net(trades,"BUY"),"sell_net_pnl":self.direction_net(trades,"SELL")}

    @staticmethod
    def bootstrap(trades, method):
        normalized=BootstrapRobustnessAudit.normalize_trades({"trades":trades})
        return BootstrapRobustnessAudit().bootstrap(normalized,label=f"USDJPY_EXTERNAL_OOS_{method}",method=method)

    @staticmethod
    def summary(symbol, broker, asset_class, history, result, config):
        closed=[trade for trade in result.trades if trade.status=="CLOSED"]
        helper=MultiAssetHistoricalReplayV2()
        return {"canonical_symbol":symbol,"broker_symbol":broker,"asset_class":asset_class,
            "source_candles":len(history),"source_sha256":helper.source_hash(history),
            "data_start":history[0].time.isoformat(),"data_end":history[-1].time.isoformat(),
            "decisions":result.diagnostics.decisions_generated,"buy_signals":result.diagnostics.buy_signals,
            "sell_signals":result.diagnostics.sell_signals,"wait_results":result.diagnostics.wait_results,
            "opened_trades":result.diagnostics.opened_trades,"closed_trades":result.diagnostics.closed_trades,
            "unresolved_trades":result.diagnostics.unresolved_trades,"rejected_trades":result.diagnostics.rejected_trades,
            "rejection_reasons":dict(sorted(result.diagnostics.rejection_reasons.items())),
            **helper.metrics(result,closed,config.starting_balance),
            "risk_audit":helper.risk(closed,config.starting_balance,config.risk_percent)}
