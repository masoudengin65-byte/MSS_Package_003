"""Freeze older original-universe and exploratory-symbol availability without replay."""

import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import MetaTrader5 as mt5

from mss.analysis.extended_historical_universe_freeze import ExtendedHistoricalUniverseFreeze as Freeze
from mss.analysis.historical_depth_audit import HistoricalDepthAudit

ROOT=Path(__file__).resolve().parents[1]
C2=ROOT/'reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json'
OUTPUT=ROOT/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.json'
PARTIAL=ROOT/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.partial.json'

def epoch(value): return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp())

def save_partial(data):
    PARTIAL.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--batch',choices=('original','forex','other','finalize'),required=True); args=parser.parse_args()
    c2=json.loads(C2.read_text(encoding='utf-8'))
    state=json.loads(PARTIAL.read_text(encoding='utf-8')) if PARTIAL.exists() else {'original':{},'exploratory':{}}
    if args.batch=='finalize':
        original=list(state['original'].values()); exploratory=list(state['exploratory'].values())
        payload={'schema_version':'MSS_SPRINT92E1_EXTENDED_HISTORICAL_UNIVERSE_FREEZE_V1','mode':'AVAILABILITY_AND_FREEZE_ONLY',
          'original_universe_older_windows':original,'exploratory_universe_windows':exploratory,
          'audit':{'strategy_replay_run':False,'signals_or_pnl_computed':False,'true_oos_used':False,'production_behavior_changed':False},
          'acceptance':{'original_symbol_count':len(original),'exploratory_symbol_count':len(exploratory),
           'all_original_no_overlap':len(original)==8 and all(r['no_overlap_with_consumed_50000'] for r in original),
           'all_windows_eligible':len(original)==8 and len(exploratory)==14 and all(r['eligible_for_future_replay'] for r in original+exploratory)}}
        output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
        print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True); print('STRATEGY_REPLAY_RUN False',flush=True); return
    mt5.shutdown()
    if not mt5.initialize(path=r'C:\Program Files\Alpari MT5\terminal64.exe',timeout=120000): raise RuntimeError(mt5.last_error())
    try:
        for frozen in (c2['symbols'] if args.batch=='original' else []):
            canonical,broker=frozen['canonical_symbol'],frozen['broker_symbol']; mt5.symbol_select(broker,True)
            first=epoch(frozen['first_candle_open_timestamp']); anchor=datetime.fromtimestamp(first,timezone.utc)
            raw=mt5.copy_rates_from(broker,mt5.TIMEFRAME_M15,anchor,Freeze.COUNT)
            rates=[] if raw is None else [row for row in raw if int(row['time']) <= first]
            row=Freeze.manifest_row(canonical,broker,frozen['asset_class'],rates,first+900,'OLDER_CONFIRMATORY_CANDIDATE' if canonical=='USDJPY' else 'OLDER_INDEPENDENT_VALIDATION',frozen['first_candle_open_timestamp'])
            row['no_overlap_with_consumed_50000']=Freeze.no_overlap(rates,first)
            state['original'][canonical]=row; save_partial(state); print('OLDER',canonical,len(rates),row['first_open_timestamp'],flush=True)
        selected=[x for x in Freeze.EXPLORATORY if (args.batch=='forex' and x[2]=='FOREX') or (args.batch=='other' and x[2]!='FOREX')]
        for canonical,broker,asset_class in selected:
            if not mt5.symbol_select(broker,True): raise RuntimeError(f'{broker} unavailable')
            current=mt5.copy_rates_from_pos(broker,mt5.TIMEFRAME_M15,0,1); raw=mt5.copy_rates_from_pos(broker,mt5.TIMEFRAME_M15,1,Freeze.COUNT)
            rates=[] if raw is None else list(raw); boundary=int(current[0]['time'])
            row=Freeze.manifest_row(canonical,broker,asset_class,rates,boundary,'EXPLORATORY_ONLY',HistoricalDepthAudit._iso(boundary))
            state['exploratory'][canonical]=row; save_partial(state); print('EXPLORATORY',canonical,len(rates),row['first_open_timestamp'],flush=True)
    finally: mt5.shutdown()
    print('BATCH_COMPLETE',args.batch,flush=True)
if __name__=='__main__': main()
