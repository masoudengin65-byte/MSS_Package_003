"""Run the G.1 candidate once on frozen Development only."""
import hashlib,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import MetaTrader5 as mt5
from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.confluence_gate_development_evaluation import ConfluenceGateDevelopmentEvaluation
from mss.analysis.confluence_gated_smart_money_pipeline import ConfluenceGatedSmartMoneyPipeline
from mss.analysis.external_historical_oos_replay import ExternalHistoricalOOSReplay as Report
from mss.analysis.external_historical_valuation_preflight import ExternalHistoricalValuationPreflight as Preflight
from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata,HistoricalBacktestConfig
ROOT=Path(__file__).resolve().parents[1]; MANIFEST=ROOT/'reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json'; BASELINE=ROOT/'reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json'; PROTOCOL=ROOT/'reports/MSS_Sprint92G1_Confluence_Gate_Hypothesis_Preregistration.json'; OUTPUT=ROOT/'reports/MSS_Sprint92G3_Confluence_Gate_Development_Evaluation.json'
CLASSES={'EURUSD':'FOREX','GBPUSD':'FOREX','USDJPY':'FOREX','AUDUSD':'FOREX','USDCAD':'FOREX','XAUUSD':'METAL','BTCUSD':'CRYPTO','ETHUSD':'CRYPTO'}
def candle(x): return Candle(time=datetime.fromtimestamp(int(x['time'])),open=float(x['open']),high=float(x['high']),low=float(x['low']),close=float(x['close']),tick_volume=int(x['tick_volume']),spread=int(x['spread']),real_volume=int(x['real_volume']))
def meta(i,c): return BacktestSymbolMetadata(account_currency=c,currency_base=i.currency_base,currency_profit=i.currency_profit,currency_margin=i.currency_margin,trade_calc_mode=int(i.trade_calc_mode),point=i.point,digits=i.digits,tick_size=i.trade_tick_size,tick_value=i.trade_tick_value,contract_size=i.trade_contract_size,volume_min=i.volume_min,volume_max=i.volume_max,volume_step=i.volume_step,spread_points=i.spread)
def config(): return HistoricalBacktestConfig(warmup_candles=200,analysis_lookback=500,starting_balance=10000,risk_percent=1,reward_risk_ratio=2,spread_points=None,commission_per_lot=0,slippage_points=1,ambiguous_policy='STOP_LOSS_FIRST')
def main():
    if OUTPUT.exists(): raise RuntimeError('AUTHORITATIVE_G3_ALREADY_RECORDED; rerun prohibited')
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8')); baseline=json.loads(BASELINE.read_text(encoding='utf-8')); protocol=json.loads(PROTOCOL.read_text(encoding='utf-8')); rows={x['canonical_symbol']:x for x in manifest['symbols']}
    OUTPUT.write_text(json.dumps({'schema_version':ConfluenceGateDevelopmentEvaluation.VERSION,'status':'RUN_STARTED','authoritative_candidate_replay_count':1,'rerun_prohibited':True},indent=2)+'\n',encoding='utf-8',newline='\n')
    adapter=MT5Adapter(); ok,msg=adapter.connect()
    if not ok: raise RuntimeError(msg)
    summaries=[]; trades=[]; source_ok=True
    try:
      account=mt5.account_info()
      for symbol in protocol['development_test_protocol']['symbols']:
        frozen=rows[symbol]; broker=frozen['broker_symbol']; anchor=datetime.fromisoformat(frozen['freeze_anchor_timestamp'].replace('Z','+00:00')).astimezone(timezone.utc); raw=mt5.copy_rates_from(broker,mt5.TIMEFRAME_M15,anchor,50000)
        if raw is None or len(raw)!=50000 or HistoricalDepthAudit.candle_hash(raw)!=frozen['full_dataset_sha256']: raise RuntimeError(f'{symbol}: source mismatch')
        history=[candle(x) for x in raw[:30000]]; info=mt5.symbol_info(broker); metadata=meta(info,account.currency); conversion=None; required=Preflight.required_conversion_symbol(info.currency_profit,account.currency)
        if required:
          mt5.symbol_select(required,True); ci=mt5.symbol_info(required); cr=mt5.copy_rates_range(required,mt5.TIMEFRAME_M15,history[0].time.replace(tzinfo=timezone.utc)-timedelta(days=7),history[-1].time.replace(tzinfo=timezone.utc)+timedelta(minutes=15)); conversion=Preflight.series(required,ci.currency_base,ci.currency_profit,[candle(x) for x in cr])
        print('AUTHORITATIVE_G3_SYMBOL',symbol,flush=True); result=HistoricalBacktestEngine(ConfluenceGatedSmartMoneyPipeline()).run(symbol,'M15',history,config(),metadata,conversion); summary=Report.summary(symbol,broker,CLASSES[symbol],history,result,config()); row_trades=Report.trade_rows(symbol,broker,CLASSES[symbol],result.trades); summaries.append(summary); trades.extend(row_trades)
    finally: adapter.shutdown()
    integrity={'all_eight_source_hashes_verified':source_ok and len(summaries)==8,'all_source_slices_30000':all(x['source_candles']==30000 for x in summaries),'no_conversion_unavailable_rejections':sum(x['rejection_reasons'].get('HISTORICAL_CONVERSION_UNAVAILABLE',0) for x in summaries)==0,'no_valuation_unavailable_trades':not any(x['status']=='VALUATION_UNAVAILABLE' for x in trades),'no_future_conversion':not any((x.get('entry_conversion_time') and x['entry_conversion_time']>x['entry_time']) or (x.get('exit_conversion_time') and x['exit_conversion_time']>x['exit_time']) for x in trades)}
    payload=ConfluenceGateDevelopmentEvaluation().build(summaries,trades,baseline,protocol,integrity); payload['status']='RUN_COMPLETED'; payload['input_file_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (MANIFEST,BASELINE,PROTOCOL)}; output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False,default=str)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    for x in payload['baseline_comparison']: print('RESULT',x['canonical_symbol'],x['candidate_closed_trades'],x['mean_r_difference'],x['net_pnl_difference'],flush=True)
    print('DECISION',payload['decision']['result'],flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
