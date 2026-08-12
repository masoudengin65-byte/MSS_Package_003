"""Close Sprint 92E using only committed artifacts; no market access."""
import hashlib,json
from pathlib import Path
from mss.analysis.external_historical_validation_closure import ExternalHistoricalValidationClosure

ROOT=Path(__file__).resolve().parents[1]; PATHS={'e1':ROOT/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.json','e2':ROOT/'reports/MSS_Sprint92E2_External_Historical_OOS_Preregistration.json','e3':ROOT/'reports/MSS_Sprint92E3_Valuation_Preflight.json','e4':ROOT/'reports/MSS_Sprint92E4_External_Historical_OOS_Replay.json','e5':ROOT/'reports/MSS_Sprint92E5_External_Historical_Exploratory_Analysis.json','e6':ROOT/'reports/MSS_Sprint92E6_External_Historical_Confirmatory_Preregistration.json','e7':ROOT/'reports/MSS_Sprint92E7_External_Historical_Confirmatory_Replay.json'}; OUTPUT=ROOT/'reports/MSS_Sprint92E8_External_Historical_Validation_Closure.json'
def main():
    before={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in PATHS.items()}; sources={k:json.loads(p.read_text(encoding='utf-8')) for k,p in PATHS.items()}; builder=ExternalHistoricalValidationClosure(); first=builder.build(sources); second=builder.build(sources)
    if first!=second: raise RuntimeError('deterministic rebuild failed')
    first['source_file_sha256']=before; first['audit']['deterministic_rebuild']=True; output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    if before!={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in PATHS.items()}: raise RuntimeError('protected source changed')
    print('CONCLUSION',first['final_conclusions']['scientific_conclusion'],flush=True); print('PRODUCTION',first['final_conclusions']['production_decision'],flush=True); print('REPLAY_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
