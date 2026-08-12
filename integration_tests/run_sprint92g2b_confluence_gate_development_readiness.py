"""Create a pre-outcome G.3 readiness artifact without replay."""
import hashlib,json
from pathlib import Path
from mss.analysis.confluence_gate_development_readiness import ConfluenceGateDevelopmentReadiness
ROOT=Path(__file__).resolve().parents[1]; G1=ROOT/'reports/MSS_Sprint92G1_Confluence_Gate_Hypothesis_Preregistration.json'; G2=ROOT/'reports/MSS_Sprint92G2_Confluence_Gate_Implementation_Validation.json'; OUTPUT=ROOT/'reports/MSS_Sprint92G2b_Confluence_Gate_Development_Readiness.json'; PATHS={'candidate_pipeline':ROOT/'src/mss/analysis/confluence_gated_smart_money_pipeline.py','baseline_pipeline':ROOT/'src/mss/analysis/smart_money_pipeline.py','pipeline_result':ROOT/'src/mss/domain/pipeline_result.py'}
def main():
    protocol=json.loads(G1.read_text(encoding='utf-8')); implementation=json.loads(G2.read_text(encoding='utf-8')); builder=ConfluenceGateDevelopmentReadiness(); first=builder.build(protocol,implementation,PATHS); second=builder.build(protocol,implementation,PATHS)
    if first!=second: raise RuntimeError('deterministic rebuild failed')
    first['source_file_sha256']={'g1':hashlib.sha256(G1.read_bytes()).hexdigest(),'g2':hashlib.sha256(G2.read_bytes()).hexdigest()}; first['audit']['deterministic_rebuild']=True; output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    print('IMPLEMENTATION_READY',first['gate']['implementation_ready'],flush=True); print('G3_ALLOWED_NOW',first['gate']['g3_execution_allowed_now'],flush=True); print('REPLAY_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
