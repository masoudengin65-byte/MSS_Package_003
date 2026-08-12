"""Create the bounded development-only mechanism protocol without analysis."""
import hashlib,json
from pathlib import Path
from mss.analysis.mechanism_discovery_preregistration import MechanismDiscoveryPreregistration
ROOT=Path(__file__).resolve().parents[1]; C3=ROOT/'reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json'; E8=ROOT/'reports/MSS_Sprint92E8_External_Historical_Validation_Closure.json'; OUTPUT=ROOT/'reports/MSS_Sprint92F1_Mechanism_Discovery_Preregistration.json'
def main():
    paths=(C3,E8); before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}; c3=json.loads(C3.read_text(encoding='utf-8')); e8=json.loads(E8.read_text(encoding='utf-8')); builder=MechanismDiscoveryPreregistration(); first=builder.build(c3,e8); second=builder.build(c3,e8)
    if first!=second: raise RuntimeError('deterministic rebuild failed')
    first['source_file_sha256']=before; first['audit']['deterministic_rebuild']=True; output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    if before!={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}: raise RuntimeError('protected source changed')
    print('HYPOTHESES',len(first['locked_hypothesis_families']),flush=True); print('DEVELOPMENT_TRADES',first['data_scope']['development_closed_trade_count'],flush=True); print('ANALYSIS_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
