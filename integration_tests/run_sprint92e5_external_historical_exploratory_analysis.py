"""Analyze the frozen E.4 result without rerunning the strategy."""
import hashlib,json
from pathlib import Path
from mss.analysis.external_historical_exploratory_analysis import ExternalHistoricalExploratoryAnalysis

ROOT=Path(__file__).resolve().parents[1]; REPLAY=ROOT/'reports/MSS_Sprint92E4_External_Historical_OOS_Replay.json'; PROTOCOL=ROOT/'reports/MSS_Sprint92E2_External_Historical_OOS_Preregistration.json'; OUTPUT=ROOT/'reports/MSS_Sprint92E5_External_Historical_Exploratory_Analysis.json'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    replay=json.loads(REPLAY.read_text(encoding='utf-8')); protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    if replay['status']!='RUN_COMPLETED' or replay['audit']['strategy_replay_count']!=1: raise RuntimeError('authoritative source invalid')
    payload=ExternalHistoricalExploratoryAnalysis().build(replay,protocol,sha(REPLAY),sha(PROTOCOL))
    output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    print('TIERS',json.dumps(payload['evidence_tiers'],sort_keys=True),flush=True); print('CONCLUSION',json.dumps(payload['conclusion'],sort_keys=True),flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
