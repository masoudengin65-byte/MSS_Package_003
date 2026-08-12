"""Execute the preregistered Sprint 92E external replay exactly once."""

import hashlib,json
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.external_historical_oos_replay import ExternalHistoricalOOSReplay
from mss.analysis.external_historical_valuation_preflight import ExternalHistoricalValuationPreflight
from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata,HistoricalBacktestConfig

ROOT=Path(__file__).resolve().parents[1]; FREEZE=ROOT/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.json'; PROTOCOL=ROOT/'reports/MSS_Sprint92E2_External_Historical_OOS_Preregistration.json'; PREFLIGHT=ROOT/'reports/MSS_Sprint92E3_Valuation_Preflight.json'; OUTPUT=ROOT/'reports/MSS_Sprint92E4_External_Historical_OOS_Replay.json'
def dt(value): return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
def candle(row): return Candle(time=datetime.fromtimestamp(int(row['time'])),open=float(row['open']),high=float(row['high']),low=float(row['low']),close=float(row['close']),tick_volume=int(row['tick_volume']),spread=int(row['spread']),real_volume=int(row['real_volume']))
def metadata(info,currency): return BacktestSymbolMetadata(account_currency=currency,currency_base=info.currency_base,currency_profit=info.currency_profit,currency_margin=info.currency_margin,trade_calc_mode=int(info.trade_calc_mode),point=info.point,digits=info.digits,tick_size=info.trade_tick_size,tick_value=info.trade_tick_value,contract_size=info.trade_contract_size,volume_min=info.volume_min,volume_max=info.volume_max,volume_step=info.volume_step,spread_points=info.spread)
def config(contract): return HistoricalBacktestConfig(warmup_candles=contract['warmup'],analysis_lookback=contract['lookback'],starting_balance=contract['starting_balance'],risk_percent=contract['risk_percent'],reward_risk_ratio=contract['reward_risk_ratio'],spread_points=None,commission_per_lot=0.0,slippage_points=1.0,ambiguous_policy=contract['ambiguous_exit'])
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if OUTPUT.exists(): raise RuntimeError('AUTHORITATIVE_RUN_ALREADY_RECORDED; rerun prohibited')
    freeze=json.loads(FREEZE.read_text(encoding='utf-8')); protocol=json.loads(PROTOCOL.read_text(encoding='utf-8')); preflight=json.loads(PREFLIGHT.read_text(encoding='utf-8'))
    if not preflight['gate']['authoritative_replay_allowed']: raise RuntimeError('valuation preflight gate closed')
    expected_freeze=protocol['freeze_file_sha256']; expected_preflight='5bb558c809619344fac5443d1d3e4a2468f47e55675f923aca695e6d2a69281d'
    if sha(FREEZE)!=expected_freeze or sha(PREFLIGHT)!=expected_preflight: raise RuntimeError('preregistered inputs changed')
    OUTPUT.write_text(json.dumps({'schema_version':ExternalHistoricalOOSReplay.VERSION,'status':'RUN_STARTED','authoritative_run_number':1,'rerun_prohibited':True},indent=2)+'\n',encoding='utf-8',newline='\n')
    rows=freeze['original_universe_older_windows']+freeze['exploratory_universe_windows']; contract=protocol['confirmatory_test']['strategy_contract']; cfg=config(contract); adapter=MT5Adapter(); ok,msg=adapter.connect()
    if not ok: raise RuntimeError(msg)
    report=ExternalHistoricalOOSReplay(); summaries=[]; all_trades=[]; source_audits=[]
    try:
      account=mt5.account_info()
      for row in rows:
        broker=row['broker_symbol']; anchor=dt(row['last_open_timestamp']); raw=mt5.copy_rates_from(broker,mt5.TIMEFRAME_M15,anchor,row['requested_count'])
        if raw is not None: raw=raw[raw['time']<=int(anchor.timestamp())]
        full_ok=raw is not None and len(raw)==row['returned_count'] and HistoricalDepthAudit.candle_hash(raw)==row['ohlcv_sha256']
        if not full_ok: raise RuntimeError(f'{broker}: frozen source mismatch')
        history=[candle(x) for x in raw[:10000]]; info=mt5.symbol_info(broker); meta=metadata(info,account.currency); conversion=None
        required=ExternalHistoricalValuationPreflight.required_conversion_symbol(info.currency_profit,account.currency)
        if required:
          mt5.symbol_select(required,True); ci=mt5.symbol_info(required); start=history[0].time.replace(tzinfo=timezone.utc)-timedelta(days=7); end=history[-1].time.replace(tzinfo=timezone.utc)+timedelta(minutes=15); cr=mt5.copy_rates_range(required,mt5.TIMEFRAME_M15,start,end)
          conversion=ExternalHistoricalValuationPreflight.series(required,ci.currency_base,ci.currency_profit,[candle(x) for x in cr])
        print('AUTHORITATIVE_SYMBOL_RUN',row['canonical_symbol'],flush=True)
        result=HistoricalBacktestEngine().run(row['canonical_symbol'],'M15',history,cfg,meta,conversion)
        summary=report.summary(row['canonical_symbol'],broker,row['asset_class'],history,result,cfg); trades=report.trade_rows(row['canonical_symbol'],broker,row['asset_class'],result.trades)
        summaries.append(summary); all_trades.extend(trades); source_audits.append({'canonical_symbol':row['canonical_symbol'],'full_frozen_hash_verified':True,'target_sha256':summary['source_sha256']})
    finally: adapter.shutdown()
    by_symbol={x['canonical_symbol']:x for x in summaries}; usd_trades=[x for x in all_trades if x['canonical_symbol']=='USDJPY']; ordinary=report.bootstrap(usd_trades,'ordinary'); block=report.bootstrap(usd_trades,'moving_block_circular')
    integrity={'all_22_full_frozen_hashes_verified':len(source_audits)==22 and all(x['full_frozen_hash_verified'] for x in source_audits),'usdjpy_full_source_matches_preregistration':next(x for x in rows if x['canonical_symbol']=='USDJPY')['ohlcv_sha256']==protocol['confirmatory_test']['source_window_sha256'],'no_conversion_unavailable_rejections':sum(x['rejection_reasons'].get('HISTORICAL_CONVERSION_UNAVAILABLE',0) for x in summaries)==0,'no_valuation_unavailable_trades':not any(x['status']=='VALUATION_UNAVAILABLE' for x in all_trades),'no_future_conversion':not any((x.get('entry_conversion_time') and x['entry_conversion_time']>x['entry_time']) or (x.get('exit_conversion_time') and x['exit_conversion_time']>x['exit_time']) for x in all_trades)}
    confirmation=report.confirmation(by_symbol['USDJPY'],usd_trades,ordinary,block,integrity)
    payload={'schema_version':report.VERSION,'status':'RUN_COMPLETED','mode':'PREREGISTERED_EXTERNAL_HISTORICAL_OOS','authoritative_run_number':1,'rerun_prohibited':True,'baseline_commit':'f0082fd','configuration':{**asdict(cfg),'timeframe':'M15','independent_symbol_accounts':True},'input_hashes':{'freeze':sha(FREEZE),'protocol':sha(PROTOCOL),'valuation_preflight':sha(PREFLIGHT)},'source_audit':source_audits,'per_symbol_results':summaries,'trades':all_trades,'confirmatory_usdjpy':{'ordinary_bootstrap':ordinary,'moving_block_bootstrap':block,'integrity':integrity,'decision':confirmation},'exploratory_symbols':protocol['exploratory_tests']['symbols'],'audit':{'strategy_replay_count':1,'symbol_runs':22,'parameter_tuning':False,'interim_peeking':False,'true_future_oos_used':False,'real_orders_sent':False}}
    output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False,default=str)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    for row in summaries: print('RESULT',row['canonical_symbol'],row['closed_trades'],row['net_profit'],row['profit_factor'],flush=True)
    print('CONFIRMATORY_DECISION',confirmation['decision'],flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
