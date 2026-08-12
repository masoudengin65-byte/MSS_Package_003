"""Evaluate the preregistered G.1 candidate against frozen Development baseline."""
import math
import numpy as np
from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit as B


class ConfluenceGateDevelopmentEvaluation:
    VERSION="MSS_SPRINT92G3_CONFLUENCE_GATE_DEVELOPMENT_EVALUATION_V1"

    @staticmethod
    def bootstrap_difference(candidate,baseline,method,resamples=10000,label='G3'):
        c=np.asarray([float(x['r_multiple']) for x in candidate if x['status']=='CLOSED']); b=np.asarray([float(x['r_multiple']) for x in baseline if x['status']=='CLOSED'])
        if not len(c) or not len(b): return {'available':False,'reason':'EMPTY_SAMPLE','candidate_count':len(c),'baseline_count':len(b)}
        rng=np.random.default_rng(B._derived_seed(B.DEFAULT_SEED,label+method)); values=[]; batch=500
        for start in range(0,resamples,batch):
            size=min(batch,resamples-start)
            if method=='ordinary': ci=rng.integers(0,len(c),size=(size,len(c))); bi=rng.integers(0,len(b),size=(size,len(b)))
            else:
                def block_idx(n):
                    blocks=math.ceil(n/B.BLOCK_LENGTH); starts=rng.integers(0,n,size=(size,blocks)); return ((starts[:,:,None]+np.arange(B.BLOCK_LENGTH))%n).reshape(size,-1)[:,:n]
                ci=block_idx(len(c)); bi=block_idx(len(b))
            values.extend((c[ci].mean(axis=1)-b[bi].mean(axis=1)).tolist())
        return {'available':True,'method':method,'resamples':resamples,'candidate_count':len(c),'baseline_count':len(b),
            'point_difference':float(c.mean()-b.mean()),'ci_95':B.interval(values,.95),'probability_above_zero':sum(x>0 for x in values)/len(values)}

    def build(self,summaries,trades,baseline,protocol,integrity):
        baseline_rows={x['canonical_symbol']:x for x in baseline['segments']['DEVELOPMENT']['per_symbol_results']}; candidate_rows={x['canonical_symbol']:x for x in summaries}; baseline_trades=baseline['segments']['DEVELOPMENT']['trades']; symbols=protocol['development_test_protocol']['symbols']
        comparisons=[]
        for symbol in symbols:
            c=candidate_rows[symbol]; b=baseline_rows[symbol]
            comparisons.append({'canonical_symbol':symbol,'candidate_closed_trades':c['closed_trades'],'baseline_closed_trades':b['closed_trades'],
                'candidate_mean_r':c['average_r'],'baseline_mean_r':b['average_r'],'mean_r_difference':c['average_r']-b['average_r'],
                'candidate_net_pnl':c['net_profit'],'baseline_net_pnl':b['net_profit'],'net_pnl_difference':c['net_profit']-b['net_profit'],
                'candidate_profit_factor':c['profit_factor'],'baseline_profit_factor':b['profit_factor']})
        ordinary=self.bootstrap_difference(trades,baseline_trades,'ordinary',label='G3_POOLED_'); block=self.bootstrap_difference(trades,baseline_trades,'moving_block_circular',label='G3_POOLED_')
        closed=[x for x in trades if x['status']=='CLOSED']; buy=sum(float(x['profit']) for x in closed if x['direction']=='BUY'); sell=sum(float(x['profit']) for x in closed if x['direction']=='SELL'); pooled_count=len(closed)
        requirements={'minimum_50_candidate_trades_each_symbol':all(x['candidate_closed_trades']>=50 for x in comparisons),'minimum_400_pooled_candidate_trades':pooled_count>=400,
            'pooled_mean_r_difference_positive':ordinary.get('point_difference',0)>0,'ordinary_ci95_lower_positive':ordinary.get('available',False) and ordinary['ci_95']['lower']>0,
            'moving_block_ci95_lower_positive':block.get('available',False) and block['ci_95']['lower']>0,
            'mean_r_improves_at_least_6_symbols':sum(x['mean_r_difference']>0 for x in comparisons)>=6,
            'net_pnl_improves_at_least_6_symbols':sum(x['net_pnl_difference']>0 for x in comparisons)>=6,
            'pooled_buy_net_pnl_positive':buy>0,'pooled_sell_net_pnl_positive':sell>0,
            'maximum_realized_loss_within_1_25_percent':max((x['risk_audit']['maximum_realized_loss_percent'] for x in summaries),default=0)<=1.25,
            'zero_integrity_failures':all(integrity.values())}
        passed=all(requirements.values())
        return {'schema_version':self.VERSION,'mode':'PREREGISTERED_DEVELOPMENT_ONLY_CANDIDATE_EVALUATION','baseline_commit':'ea1c08c',
            'per_symbol_results':summaries,'baseline_comparison':comparisons,'candidate_trades':trades,
            'pooled_inference':{'ordinary_bootstrap':ordinary,'moving_block_bootstrap':block,'candidate_closed_trades':pooled_count,'buy_net_pnl':round(buy,2),'sell_net_pnl':round(sell,2)},
            'integrity':integrity,'decision':{'requirements':requirements,'all_pass':passed,'result':'WRITE_SEPARATE_VALIDATION_PREREGISTRATION_BEFORE_ACCESS' if passed else 'REJECT_CONFLUENCE_GATE_NO_VALIDATION_ACCESS'},
            'audit':{'authoritative_candidate_replay_count':1,'symbol_runs':8,'validation_accessed':False,'external_history_accessed':False,'true_future_oos_used':False,'parameter_optimization':False,'real_orders_sent':False}}
