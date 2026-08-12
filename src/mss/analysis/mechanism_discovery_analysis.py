"""Bounded development-only mechanism analysis for Sprint 92F.2."""
import math
import numpy as np
from statistics import median
from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit as B


class MechanismDiscoveryAnalysis:
    VERSION="MSS_SPRINT92F2_MECHANISM_DISCOVERY_ANALYSIS_V1"
    SYMBOLS=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD","BTCUSD","ETHUSD")
    @staticmethod
    def closed(trades): return [x for x in trades if x['status']=='CLOSED']
    @staticmethod
    def metrics(rows):
        p=[float(x['profit']) for x in rows]; r=[float(x['r_multiple']) for x in rows]; gp=sum(x for x in p if x>0); gl=-sum(x for x in p if x<0)
        return {'count':len(rows),'net_pnl':round(sum(p),2),'expectancy':sum(p)/len(p) if p else None,'mean_r':sum(r)/len(r) if r else None,'median_r':median(r) if r else None,'profit_factor':gp/gl if gl else None,'win_rate':sum(x>0 for x in p)/len(p) if p else None,'sufficient':len(rows)>=30}
    @staticmethod
    def quantile_edges(values,bins):
        s=sorted(float(x) for x in values); return [s[math.ceil(i*len(s)/bins)-1] for i in range(1,bins)]
    @staticmethod
    def bucket(value,edges): return sum(float(value)>edge for edge in edges)
    @staticmethod
    def cost(row): return (float(row['spread'])+float(row['slippage']))/abs(float(row['entry_price'])-float(row['stop_loss']))
    @staticmethod
    def session(row):
        hour=int(str(row['entry_time'])[11:13]); return 'ASIA' if hour<8 else 'EUROPE' if hour<16 else 'AMERICAS'
    @staticmethod
    def spearman_bin_means(groups):
        means=[g['mean_r'] for g in groups]
        if any(x is None for x in means) or len(set(means))<2:return 0.0
        n=len(means); ranks={v:i for i,v in enumerate(sorted(means))}; d=sum((i-ranks[v])**2 for i,v in enumerate(means)); return 1-6*d/(n*(n*n-1))
    @staticmethod
    def bootstrap_contrast(rows,left,right,label,resamples=10000):
        ordered=sorted(rows,key=lambda x:(x['entry_time'],x['canonical_symbol'],x['trade_id'])); n=len(ordered)
        values=np.asarray([float(x['r_multiple']) for x in ordered]); left_mask=np.asarray([left(x) for x in ordered]); right_mask=np.asarray([right(x) for x in ordered])
        def run(method):
            rng=np.random.default_rng(B._derived_seed(B.DEFAULT_SEED,label+method)); vals=[]; batch=250
            for start in range(0,resamples,batch):
                size=min(batch,resamples-start)
                if method=='ordinary': idx=rng.integers(0,n,size=(size,n))
                else:
                    blocks=math.ceil(n/B.BLOCK_LENGTH); starts=rng.integers(0,n,size=(size,blocks)); offsets=np.arange(B.BLOCK_LENGTH); idx=((starts[:,:,None]+offsets)%n).reshape(size,-1)[:,:n]
                lm=left_mask[idx]; rm=right_mask[idx]; sampled=values[idx]; lc=lm.sum(axis=1); rc=rm.sum(axis=1); valid=(lc>0)&(rc>0)
                contrasts=(sampled*lm).sum(axis=1)/np.maximum(lc,1)-(sampled*rm).sum(axis=1)/np.maximum(rc,1); vals.extend(contrasts[valid].tolist())
            return {'method':method,'valid_samples':len(vals),'ci_95':B.interval(vals,.95),'point_positive_probability':sum(x>0 for x in vals)/len(vals) if vals else None}
        return {'ordinary':run('ordinary'),'moving_block':run('moving_block_circular')}
    def grouped(self,rows,key,labels): return [{'group':label,**self.metrics([x for x in rows if key(x)==i])} for i,label in enumerate(labels)]
    def build(self,c3,protocol):
        trades=self.closed(c3['segments']['DEVELOPMENT']['trades']); cost_edges=self.quantile_edges([self.cost(x) for x in trades],4); legacy_edges=self.quantile_edges([x['score'] for x in trades],5); shadow_edges=self.quantile_edges([x['shadow_score'] for x in trades],5)
        by_symbol={s:[x for x in trades if x['canonical_symbol']==s] for s in self.SYMBOLS}
        direction={s:{d:self.metrics([x for x in rows if x['direction']==d]) for d in ('BUY','SELL')} for s,rows in by_symbol.items()}; pooled_direction={d:self.metrics([x for x in trades if x['direction']==d]) for d in ('BUY','SELL')}
        cost={s:self.grouped(rows,lambda x:self.bucket(self.cost(x),cost_edges),['Q1_LOW','Q2','Q3','Q4_HIGH']) for s,rows in by_symbol.items()}; legacy={s:self.grouped(rows,lambda x:self.bucket(x['score'],legacy_edges),['Q1','Q2','Q3','Q4','Q5']) for s,rows in by_symbol.items()}; shadow={s:self.grouped(rows,lambda x:self.bucket(x['shadow_score'],shadow_edges),['Q1','Q2','Q3','Q4','Q5']) for s,rows in by_symbol.items()}; sessions={s:{g:self.metrics([x for x in rows if self.session(x)==g]) for g in ('ASIA','EUROPE','AMERICAS')} for s,rows in by_symbol.items()}
        pooled_cost=self.grouped(trades,lambda x:self.bucket(self.cost(x),cost_edges),['Q1_LOW','Q2','Q3','Q4_HIGH']); pooled_legacy=self.grouped(trades,lambda x:self.bucket(x['score'],legacy_edges),['Q1','Q2','Q3','Q4','Q5']); pooled_shadow=self.grouped(trades,lambda x:self.bucket(x['shadow_score'],shadow_edges),['Q1','Q2','Q3','Q4','Q5']); pooled_sessions={g:self.metrics([x for x in trades if self.session(x)==g]) for g in ('ASIA','EUROPE','AMERICAS')}
        h1_sign=1 if pooled_direction['BUY']['mean_r']>pooled_direction['SELL']['mean_r'] else -1; h1_cons=sum((v['BUY']['mean_r']-v['SELL']['mean_r'])*h1_sign>0 for v in direction.values()); h1_boot=self.bootstrap_contrast(trades,lambda x:(x['direction']=='BUY')==(h1_sign>0),lambda x:(x['direction']=='SELL')==(h1_sign>0),'H1')
        h2_cons=sum(v[0]['mean_r']>v[-1]['mean_r'] for v in cost.values()); h2_boot=self.bootstrap_contrast(trades,lambda x:self.bucket(self.cost(x),cost_edges)==0,lambda x:self.bucket(self.cost(x),cost_edges)==3,'H2')
        h3_cons=sum(self.spearman_bin_means(v)>0 for v in legacy.values()); h3_boot=self.bootstrap_contrast(trades,lambda x:self.bucket(x['score'],legacy_edges)==4,lambda x:self.bucket(x['score'],legacy_edges)==0,'H3')
        h4_cons=sum(self.spearman_bin_means(shadow[s])>self.spearman_bin_means(legacy[s]) for s in self.SYMBOLS); h4_boot=self.bootstrap_contrast(trades,lambda x:self.bucket(x['shadow_score'],shadow_edges)==4,lambda x:self.bucket(x['shadow_score'],shadow_edges)==0,'H4')
        worst=min(pooled_sessions,key=lambda g:pooled_sessions[g]['mean_r']); h5_cons=sum(min(v,key=lambda g:v[g]['mean_r'])==worst for v in sessions.values()); h5_boot=self.bootstrap_contrast(trades,lambda x:self.session(x)!=worst,lambda x:self.session(x)==worst,'H5')
        candidates=[]
        for ident,consistent,boot,plausible in [('H1_DIRECTION',h1_cons,h1_boot,True),('H2_COST_BURDEN',h2_cons,h2_boot,True),('H3_LEGACY_SCORE',h3_cons,h3_boot,True),('H4_SHADOW_SCORE',h4_cons,h4_boot,True),('H5_UTC_SESSION',h5_cons,h5_boot,True)]:
            supported=consistent>=6 and plausible and boot['ordinary']['ci_95']['lower']>0 and boot['moving_block']['ci_95']['lower']>0
            candidates.append({'hypothesis_id':ident,'consistent_symbols':consistent,'bootstrap_contrast':boot,'gate_pass':supported})
        advanced=[x['hypothesis_id'] for x in candidates if x['gate_pass']][:2]
        keys=[(x['canonical_symbol'],x['trade_id']) for x in trades]
        return {'schema_version':self.VERSION,'mode':'DEVELOPMENT_ONLY_MECHANISM_ANALYSIS','baseline_commit':'a792ea3','source':{'c3_payload_sha256':protocol['source_hashes']['c3_payload_sha256'],'protocol_schema':protocol['schema_version']},'data_quality':{'closed_trade_count':len(trades),'expected_closed_trade_count':protocol['data_scope']['development_closed_trade_count'],'unique_symbol_trade_keys':len(set(keys))==len(keys),'missing_required_value_count':sum(any(x.get(k) is None for k in ('profit','r_multiple','score','shadow_score','entry_time','entry_price','stop_loss')) for x in trades),'symbols_present':sorted(by_symbol),'validation_rows_used':0},'locked_cutpoints':{'cost_burden_quartiles':cost_edges,'legacy_score_quintiles':legacy_edges,'shadow_score_quintiles':shadow_edges},'results':{'H1_DIRECTION':{'pooled':pooled_direction,'per_symbol':direction},'H2_COST_BURDEN':{'pooled':pooled_cost,'per_symbol':cost},'H3_LEGACY_SCORE':{'pooled':pooled_legacy,'per_symbol':legacy},'H4_SHADOW_SCORE':{'pooled':pooled_shadow,'per_symbol':shadow},'H5_UTC_SESSION':{'pooled':pooled_sessions,'per_symbol':sessions,'pooled_worst_session':worst}},'candidate_gate_results':candidates,'advanced_mechanisms':advanced,'conclusion':{'mechanisms_advanced_count':len(advanced),'strategy_revision_allowed':bool(advanced),'decision':'WRITE_SEPARATE_IMPLEMENTATION_SPEC_BEFORE_CODE_CHANGE' if advanced else 'NO_STRATEGY_REVISION_ADVANCED'},'audit':{'strategy_replay_run':False,'validation_accessed':False,'external_history_accessed':False,'true_future_oos_used':False,'strategy_code_changed':False,'post_hoc_symbol_exclusion':False}}
