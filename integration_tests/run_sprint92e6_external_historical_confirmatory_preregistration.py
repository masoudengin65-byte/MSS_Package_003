"""Create E.6 protocol without accessing MT5 or second-window prices."""
import hashlib,json
from pathlib import Path
from mss.analysis.external_historical_confirmatory_preregistration import ExternalHistoricalConfirmatoryPreregistration

ROOT=Path(__file__).resolve().parents[1]; FREEZE=ROOT/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.json'; ANALYSIS=ROOT/'reports/MSS_Sprint92E5_External_Historical_Exploratory_Analysis.json'; OUTPUT=ROOT/'reports/MSS_Sprint92E6_External_Historical_Confirmatory_Preregistration.json'
def main():
    before={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in (FREEZE,ANALYSIS)}; freeze=json.loads(FREEZE.read_text(encoding='utf-8')); analysis=json.loads(ANALYSIS.read_text(encoding='utf-8')); builder=ExternalHistoricalConfirmatoryPreregistration(); first=builder.build(freeze,analysis); second=builder.build(freeze,analysis)
    if first!=second: raise RuntimeError('deterministic rebuild failed')
    first['source_hashes']['freeze_file_sha256']=before[str(FREEZE)]; first['source_hashes']['e5_file_sha256']=before[str(ANALYSIS)]; first['audit']['deterministic_rebuild']=True
    output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    if before!={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in (FREEZE,ANALYSIS)}: raise RuntimeError('protected source changed')
    print('CANDIDATES',','.join(first['selection']['symbols']),flush=True); print('CONFIDENCE',first['confirmatory_family']['per_symbol_two_sided_confidence_percent'],flush=True); print('REPLAY_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
