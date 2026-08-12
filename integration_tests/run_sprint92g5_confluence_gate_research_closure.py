"""Create G.5 closure from committed artifacts only."""
import hashlib,json
from pathlib import Path
from mss.analysis.confluence_gate_research_closure import ConfluenceGateResearchClosure
ROOT=Path(__file__).resolve().parents[1]; PATHS={'g1':ROOT/'reports/MSS_Sprint92G1_Confluence_Gate_Hypothesis_Preregistration.json','g2':ROOT/'reports/MSS_Sprint92G2_Confluence_Gate_Implementation_Validation.json','g3':ROOT/'reports/MSS_Sprint92G3_Confluence_Gate_Development_Evaluation.json','g4':ROOT/'reports/MSS_Sprint92G4_Frozen_Source_Drift_Audit.json'}; OUTPUT=ROOT/'reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json'
def main():
    before={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in PATHS.items()}; values={k:json.loads(p.read_text(encoding='utf-8')) for k,p in PATHS.items()}; builder=ConfluenceGateResearchClosure(); first=builder.build(**values); second=builder.build(**values)
    if first!=second: raise RuntimeError('deterministic rebuild failed')
    first['source_file_sha256']=before; first['audit']['deterministic_rebuild']=True; output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    print('HYPOTHESIS_STATUS',first['hypothesis_status']['status'],flush=True); print('G3_RERUN',first['governance']['g3_rerun_authorized'],flush=True); print('REPLAY_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
