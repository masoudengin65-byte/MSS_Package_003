"""Read-only valuation coverage preflight; does not run strategy replay."""

import hashlib,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import MetaTrader5 as mt5

from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.external_historical_valuation_preflight import ExternalHistoricalValuationPreflight as Preflight
from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.domain.candle import Candle

ROOT=Path(__file__).resolve().parents[1]; FREEZE=ROOT/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.json'; PROTOCOL=ROOT/'reports/MSS_Sprint92E2_External_Historical_OOS_Preregistration.json'; OUTPUT=ROOT/'reports/MSS_Sprint92E3_Valuation_Preflight.json'
def candle(row): return Candle(time=datetime.fromtimestamp(int(row['time'])),open=float(row['open']),high=float(row['high']),low=float(row['low']),close=float(row['close']),tick_volume=int(row['tick_volume']),spread=int(row['spread']),real_volume=int(row['real_volume']))
def dt(value): return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)

def main():
    freeze=json.loads(FREEZE.read_text(encoding='utf-8')); protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    rows=freeze['original_universe_older_windows']+freeze['exploratory_universe_windows']; adapter=MT5Adapter(); ok,msg=adapter.connect()
    if not ok: raise RuntimeError(msg)
    audits=[]
    try:
      account=mt5.account_info(); account_currency=account.currency
      warmup=int(protocol['confirmatory_test']['strategy_contract']['warmup'])
      for row in rows:
        broker=row['broker_symbol']; anchor=dt(row['last_open_timestamp'])
        raw=mt5.copy_rates_from(broker,mt5.TIMEFRAME_M15,anchor,row['requested_count'])
        if raw is not None:
          raw=raw[raw['time'] <= int(anchor.timestamp())]
        if raw is None or len(raw)!=row['returned_count'] or HistoricalDepthAudit.candle_hash(raw)!=row['ohlcv_sha256']:
          raise RuntimeError(f'{broker}: frozen window mismatch')
        target=[candle(x) for x in raw[:10000]]; info=mt5.symbol_info(broker); required=Preflight.required_conversion_symbol(info.currency_profit,account_currency)
        cs=cb=cq=None; cc=None
        if required:
          mt5.symbol_select(required,True); ci=mt5.symbol_info(required)
          start=target[0].time.replace(tzinfo=timezone.utc)-timedelta(days=7); end=target[-1].time.replace(tzinfo=timezone.utc)+timedelta(minutes=15)
          cr=mt5.copy_rates_range(required,mt5.TIMEFRAME_M15,start,end)
          cs,cb,cq=required,ci.currency_base,ci.currency_profit; cc=[candle(x) for x in cr] if cr is not None else []
        audit=Preflight.audit(info.currency_profit,account_currency,target,cs,cb,cq,cc,warmup)
        audits.append({'canonical_symbol':row['canonical_symbol'],'broker_symbol':broker,'asset_class':row['asset_class'],
          'currency_profit':info.currency_profit,'account_currency':account_currency,**audit})
        print('VALUATION',broker,info.currency_profit,audit['coverage_complete'],audit.get('path'),flush=True)
    finally: adapter.shutdown()
    payload={'schema_version':'MSS_SPRINT92E3_VALUATION_PREFLIGHT_V1','mode':'VALUATION_PREFLIGHT_ONLY_NO_REPLAY',
      'freeze_sha256':hashlib.sha256(FREEZE.read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
      'symbols':audits,'gate':{'symbol_count':len(audits),'all_conversion_paths_complete':len(audits)==22 and all(x['coverage_complete'] for x in audits),
       'authoritative_replay_allowed':len(audits)==22 and all(x['coverage_complete'] for x in audits)},
      'valuation_scope':{'warmup_candles':warmup,'first_eligible_valuation_index':warmup,
        'leading_conversion_gaps_before_eligibility_are_non_actionable':True},
      'audit':{'strategy_replay_run':False,'outcomes_analyzed':False,'true_future_oos_used':False,'real_orders':False}}
    output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n'); print('GATE',payload['gate'],flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
