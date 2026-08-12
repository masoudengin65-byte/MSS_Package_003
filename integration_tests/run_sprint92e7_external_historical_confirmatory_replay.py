"""Execute the preregistered six-symbol second-window family exactly once."""
import hashlib,json
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
import MetaTrader5 as mt5
from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.external_historical_confirmatory_replay import ExternalHistoricalConfirmatoryReplay as Confirm
from mss.analysis.external_historical_oos_replay import ExternalHistoricalOOSReplay as Report
from mss.analysis.external_historical_valuation_preflight import ExternalHistoricalValuationPreflight as Preflight
from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata,HistoricalBacktestConfig

ROOT=Path(__file__).resolve().parents[1]; FREEZE=ROOT/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.json'; PROTOCOL=ROOT/'reports/MSS_Sprint92E6_External_Historical_Confirmatory_Preregistration.json'; OUTPUT=ROOT/'reports/MSS_Sprint92E7_External_Historical_Confirmatory_Replay.json'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dt(v): return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc)
def candle(x): return Candle(time=datetime.fromtimestamp(int(x['time'])),open=float(x['open']),high=float(x['high']),low=float(x['low']),close=float(x['close']),tick_volume=int(x['tick_volume']),spread=int(x['spread']),real_volume=int(x['real_volume']))
def meta(i,c): return BacktestSymbolMetadata(account_currency=c,currency_base=i.currency_base,currency_profit=i.currency_profit,currency_margin=i.currency_margin,trade_calc_mode=int(i.trade_calc_mode),point=i.point,digits=i.digits,tick_size=i.trade_tick_size,tick_value=i.trade_tick_value,contract_size=i.trade_contract_size,volume_min=i.volume_min,volume_max=i.volume_max,volume_step=i.volume_step,spread_points=i.spread)
def config(c): return HistoricalBacktestConfig(warmup_candles=c['warmup'],analysis_lookback=c['lookback'],starting_balance=c['starting_balance'],risk_percent=c['risk_percent'],reward_risk_ratio=c['reward_risk_ratio'],spread_points=None,commission_per_lot=c['commission_per_lot'],slippage_points=c['slippage_points'],ambiguous_policy=c['ambiguous_exit'])

def main():
    if OUTPUT.exists(): raise RuntimeError('AUTHORITATIVE_FAMILY_RUN_ALREADY_RECORDED; rerun prohibited')
    freeze=json.loads(FREEZE.read_text(encoding='utf-8')); protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    if sha(PROTOCOL)!='bf036784b1a1d9a553b38a97a67c7b3a0ba09ef6bd8c15ba2876ae5cd092483f': raise RuntimeError('committed protocol changed')
    OUTPUT.write_text(json.dumps({'schema_version':Confirm.VERSION,'status':'RUN_STARTED','authoritative_family_run_number':1,'rerun_prohibited':True},indent=2)+'\n',encoding='utf-8',newline='\n')
    rows={x['canonical_symbol']:x for x in freeze['original_universe_older_windows']+freeze['exploratory_universe_windows']}; cfg=config(protocol['strategy_contract']); confidence=protocol['confirmatory_family']['per_symbol_two_sided_confidence_percent']/100; adapter=MT5Adapter(); ok,msg=adapter.connect()
    if not ok: raise RuntimeError(msg)
    summaries=[]; all_trades=[]; decisions=[]; sources=[]
    try:
      account=mt5.account_info()
      for spec in protocol['confirmatory_family']['symbols']:
        symbol=spec['canonical_symbol']; row=rows[symbol]; broker=row['broker_symbol']; anchor=dt(row['last_open_timestamp']); raw=mt5.copy_rates_from(broker,mt5.TIMEFRAME_M15,anchor,row['requested_count'])
        if raw is not None: raw=raw[raw['time']<=int(anchor.timestamp())]
        if raw is None or len(raw)!=row['returned_count'] or HistoricalDepthAudit.candle_hash(raw)!=row['ohlcv_sha256']: raise RuntimeError(f'{symbol}: frozen source mismatch')
        history=[candle(x) for x in raw[10000:20000]]; info=mt5.symbol_info(broker); metadata=meta(info,account.currency); conversion=None; required=Preflight.required_conversion_symbol(info.currency_profit,account.currency)
        if required:
          mt5.symbol_select(required,True); ci=mt5.symbol_info(required); cr=mt5.copy_rates_range(required,mt5.TIMEFRAME_M15,history[0].time.replace(tzinfo=timezone.utc)-timedelta(days=7),history[-1].time.replace(tzinfo=timezone.utc)+timedelta(minutes=15)); conversion=Preflight.series(required,ci.currency_base,ci.currency_profit,[candle(x) for x in cr])
        print('AUTHORITATIVE_CONFIRMATORY_RUN',symbol,flush=True); result=HistoricalBacktestEngine().run(symbol,'M15',history,cfg,metadata,conversion); summary=Report.summary(symbol,broker,row['asset_class'],history,result,cfg); trades=Report.trade_rows(symbol,broker,row['asset_class'],result.trades)
        integrity={'full_frozen_hash_verified':True,'exact_second_slice_count':len(history)==10000,'no_conversion_unavailable_rejections':summary['rejection_reasons'].get('HISTORICAL_CONVERSION_UNAVAILABLE',0)==0,'no_valuation_unavailable_trades':not any(x['status']=='VALUATION_UNAVAILABLE' for x in trades),'no_future_conversion':not any((x.get('entry_conversion_time') and x['entry_conversion_time']>x['entry_time']) or (x.get('exit_conversion_time') and x['exit_conversion_time']>x['exit_time']) for x in trades)}
        ordinary=Confirm.adjusted_bootstrap(trades,'ordinary',confidence,label=f'E7:{symbol}:ordinary'); block=Confirm.adjusted_bootstrap(trades,'moving_block_circular',confidence,label=f'E7:{symbol}:block'); decision=Confirm.decide(summary,trades,ordinary,block,integrity)
        summaries.append(summary); all_trades.extend(trades); decisions.append({'canonical_symbol':symbol,'integrity':integrity,'ordinary_bootstrap':ordinary,'moving_block_bootstrap':block,**decision}); sources.append({'canonical_symbol':symbol,'full_frozen_hash_verified':True,'second_slice_sha256':summary['source_sha256'],'data_start':summary['data_start'],'data_end':summary['data_end']})
    finally: adapter.shutdown()
    payload={'schema_version':Confirm.VERSION,'status':'RUN_COMPLETED','mode':'PREREGISTERED_BONFERRONI_CONFIRMATORY_FAMILY','authoritative_family_run_number':1,'rerun_prohibited':True,'baseline_commit':'04f260f','configuration':{**asdict(cfg),'timeframe':'M15','confidence_percent':confidence*100},'input_hashes':{'freeze':sha(FREEZE),'protocol':sha(PROTOCOL)},'source_audit':sources,'per_symbol_results':summaries,'trades':all_trades,'confirmatory_decisions':decisions,'family_decision':{'confirmed_symbols':[x['canonical_symbol'] for x in decisions if x['all_pass']],'not_confirmed_symbols':[x['canonical_symbol'] for x in decisions if not x['all_pass']],'production_change_justified':False,'separate_production_governance_required':True},'audit':{'strategy_replay_count':1,'symbol_runs':6,'interim_peeking':False,'parameter_tuning':False,'true_future_oos_used':False,'real_orders_sent':False}}
    output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False,default=str)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    for s,d in zip(summaries,decisions): print('RESULT',s['canonical_symbol'],s['closed_trades'],s['net_profit'],s['profit_factor'],d['decision'],flush=True)
    print('FAMILY',json.dumps(payload['family_decision'],sort_keys=True),flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
