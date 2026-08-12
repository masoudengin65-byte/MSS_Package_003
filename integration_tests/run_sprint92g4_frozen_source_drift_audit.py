"""Read-only hash/boundary audit; never runs strategy or reports raw prices."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import MetaTrader5 as mt5
from mss.adapters.mt5.adapter import MT5Adapter
from mss.analysis.frozen_source_drift_audit import FrozenSourceDriftAudit
from mss.analysis.historical_depth_audit import HistoricalDepthAudit
ROOT=Path(__file__).resolve().parents[1]; MANIFEST=ROOT/'reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json'; FAILURE=ROOT/'reports/MSS_Sprint92G3_Confluence_Gate_Development_Evaluation.json'; OUTPUT=ROOT/'reports/MSS_Sprint92G4_Frozen_Source_Drift_Audit.json'
def iso(epoch): return datetime.fromtimestamp(int(epoch),timezone.utc).isoformat().replace('+00:00','Z')
def main():
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8')); failure=json.loads(FAILURE.read_text(encoding='utf-8')); adapter=MT5Adapter(); ok,msg=adapter.connect()
    if not ok: raise RuntimeError(msg)
    rows=[]
    try:
      for expected in manifest['symbols']:
        anchor=datetime.fromisoformat(expected['freeze_anchor_timestamp'].replace('Z','+00:00')).astimezone(timezone.utc); raw=mt5.copy_rates_from(expected['broker_symbol'],mt5.TIMEFRAME_M15,anchor,expected['frozen_candle_count']); count=0 if raw is None else len(raw); actual_hash=None if raw is None else HistoricalDepthAudit.candle_hash(raw); first=None if not count else iso(raw[0]['time']); last=None if not count else iso(raw[-1]['time']); status=FrozenSourceDriftAudit.classify(expected['frozen_candle_count'],count,expected['first_candle_open_timestamp'],first,expected['last_candle_open_timestamp'],last,expected['full_dataset_sha256'],actual_hash)
        dev_hash=None if raw is None or len(raw)<30000 else HistoricalDepthAudit.candle_hash(raw[:30000]); expected_dev=next(x['ohlcv_sha256'] for x in expected['slices'] if x['slice']=='DEVELOPMENT')
        rows.append({'canonical_symbol':expected['canonical_symbol'],'broker_symbol':expected['broker_symbol'],'status':status,'expected_count':expected['frozen_candle_count'],'actual_count':count,'expected_first':expected['first_candle_open_timestamp'],'actual_first':first,'expected_last':expected['last_candle_open_timestamp'],'actual_last':last,'expected_full_sha256':expected['full_dataset_sha256'],'actual_full_sha256':actual_hash,'expected_development_sha256':expected_dev,'actual_development_sha256':dev_hash,'development_slice_reproduced':dev_hash==expected_dev})
        print('SOURCE',expected['canonical_symbol'],status,'DEV_MATCH',dev_hash==expected_dev,flush=True)
    finally: adapter.shutdown()
    payload={'schema_version':FrozenSourceDriftAudit.VERSION,'mode':'READ_ONLY_HASH_BOUNDARY_AUDIT_NO_RAW_PRICES','baseline_commit':'fb09cb1','g3_failure_status':failure['status'],'manifest_sha256':hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),'symbols':rows,'summary':{'exact_full_reproduction_count':sum(x['status']=='EXACT_REPRODUCTION' for x in rows),'development_slice_reproduction_count':sum(x['development_slice_reproduced'] for x in rows),'drifted_symbols':[x['canonical_symbol'] for x in rows if x['status']!='EXACT_REPRODUCTION'],'g3_rerun_allowed':False,'validation_access_allowed':False},'audit':{'strategy_replay_run':False,'outcomes_analyzed':False,'raw_ohlc_persisted':False,'validation_accessed':False,'external_history_accessed':False,'true_future_oos_used':False,'real_orders_sent':False}}
    output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n'); print('SUMMARY',json.dumps(payload['summary'],sort_keys=True),flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
