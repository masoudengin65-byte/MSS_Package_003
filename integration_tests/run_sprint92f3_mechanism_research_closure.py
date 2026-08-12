"""Create the F.3 closure from committed reports only."""
import hashlib,json
from pathlib import Path
from mss.analysis.mechanism_research_closure import MechanismResearchClosure
ROOT=Path(__file__).resolve().parents[1]; F1=ROOT/'reports/MSS_Sprint92F1_Mechanism_Discovery_Preregistration.json'; F2=ROOT/'reports/MSS_Sprint92F2_Mechanism_Discovery_Analysis.json'; E8=ROOT/'reports/MSS_Sprint92E8_External_Historical_Validation_Closure.json'; OUTPUT=ROOT/'reports/MSS_Sprint92F3_Mechanism_Research_Closure.json'
def main():
    paths=(F1,F2,E8); before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}; values=[json.loads(p.read_text(encoding='utf-8')) for p in paths]; builder=MechanismResearchClosure(); first=builder.build(*values); second=builder.build(*values)
    if first!=second: raise RuntimeError('deterministic rebuild failed')
    first['source_file_sha256']=before; first['audit']['deterministic_rebuild']=True; output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    print('DECISION',first['closed_branch']['decision'],flush=True); print('PRODUCTION',first['production_governance']['production_status'],flush=True); print('REPLAY_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
