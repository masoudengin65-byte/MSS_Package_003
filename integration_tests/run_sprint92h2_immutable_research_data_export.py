"""Export exact Development slices once; no strategy or outcome analysis."""
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import MetaTrader5 as mt5
from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.analysis.immutable_research_data_store import ImmutableResearchDataStore
ROOT=Path(__file__).resolve().parents[1]; PROTOCOL=ROOT/'reports/MSS_Sprint92H1_Immutable_Research_Data_Preregistration.json'; OUTPUT=ROOT/'reports/MSS_Sprint92H2_Immutable_Research_Data_Manifest.json'; PARENT=ROOT/'research_data/sprint92h'; STAGING=PARENT/'.staging_h2'; TARGET=PARENT/'development'
def main():
    if TARGET.exists() or STAGING.exists() or OUTPUT.exists(): raise RuntimeError('write-once export target, staging, or manifest already exists')
    protocol=json.loads(PROTOCOL.read_text(encoding='utf-8')); PARENT.mkdir(parents=True,exist_ok=True); STAGING.mkdir(); adapter=MT5Adapter(); ok,msg=adapter.connect()
    if not ok: raise RuntimeError(msg)
    manifests=[]
    try:
      for spec in protocol['dataset_scope']['symbols']:
        anchor=datetime.fromisoformat(spec['last_open_timestamp'].replace('Z','+00:00')).astimezone(timezone.utc); raw=mt5.copy_rates_from(spec['broker_symbol'],mt5.TIMEFRAME_M15,anchor,spec['candle_count'])
        if raw is None or len(raw)!=spec['candle_count'] or HistoricalDepthAudit.candle_hash(raw)!=spec['expected_ohlcv_sha256']: raise RuntimeError(f"{spec['canonical_symbol']}: exact Development source unavailable")
        path=STAGING/f"{spec['canonical_symbol']}_M15_30000.jsonl"; ImmutableResearchDataStore.write_jsonl(path,raw); verification=ImmutableResearchDataStore.verify(path,spec['candle_count'],spec['expected_ohlcv_sha256'],int(raw[0]['time']),int(raw[-1]['time']))
        if not verification['verified']: raise RuntimeError(f"{spec['canonical_symbol']}: post-write verification failed")
        manifests.append({'canonical_symbol':spec['canonical_symbol'],'broker_symbol':spec['broker_symbol'],'asset_class':spec['asset_class'],'relative_path':f"research_data/sprint92h/development/{path.name}",**verification}); print('EXPORTED',spec['canonical_symbol'],verification['file_size_bytes'],verification['file_sha256'],flush=True)
    finally: adapter.shutdown()
    if len(manifests)!=8 or not all(x['verified'] for x in manifests): raise RuntimeError('all-eight promotion gate failed')
    os.replace(STAGING,TARGET)
    payload={'schema_version':ImmutableResearchDataStore.VERSION,'mode':'IMMUTABLE_DEVELOPMENT_DATA_EXPORT','baseline_commit':'90b502a','protocol_sha256':hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),'storage_root':'research_data/sprint92h/development','symbols':manifests,'summary':{'symbol_count':len(manifests),'total_rows':sum(x['row_count'] for x in manifests),'total_size_bytes':sum(x['file_size_bytes'] for x in manifests),'all_files_verified':all(x['verified'] for x in manifests),'atomic_all_eight_promotion':True},'audit':{'authoritative_exports':1,'strategy_replay_run':False,'outcomes_analyzed':False,'validation_exported':False,'external_history_exported':False,'true_future_oos_exported':False,'real_orders_sent':False}}
    output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n'); print('SUMMARY',json.dumps(payload['summary'],sort_keys=True),flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
