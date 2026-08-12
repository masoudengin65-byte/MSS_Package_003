"""Lock G.1 from source structure without outcome access."""
import hashlib,json
from pathlib import Path
from mss.analysis.confluence_gate_hypothesis_preregistration import ConfluenceGateHypothesisPreregistration
ROOT=Path(__file__).resolve().parents[1]; OUTPUT=ROOT/'reports/MSS_Sprint92G1_Confluence_Gate_Hypothesis_Preregistration.json'; PATHS={'historical_backtest_engine':ROOT/'src/mss/analysis/historical_backtest_engine.py','smart_money_pipeline':ROOT/'src/mss/analysis/smart_money_pipeline.py','confluence_engine':ROOT/'src/mss/analysis/confluence_engine.py','f3_closure':ROOT/'reports/MSS_Sprint92F3_Mechanism_Research_Closure.json'}
def main():
    before={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in PATHS.items()}; builder=ConfluenceGateHypothesisPreregistration(); first=builder.build(PATHS); second=builder.build(PATHS)
    if first!=second or first['source_file_sha256']!=before: raise RuntimeError('source or deterministic build failure')
    first['audit']['deterministic_rebuild']=True; output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    print('HYPOTHESIS',first['causal_hypothesis']['id'],flush=True); print('SINGLE_CHANGE',first['candidate_contract']['single_change'],flush=True); print('REPLAY_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
