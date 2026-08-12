"""Create H.1 storage protocol from committed metadata only."""
import hashlib,json
from pathlib import Path
from mss.analysis.immutable_research_data_preregistration import ImmutableResearchDataPreregistration
ROOT=Path(__file__).resolve().parents[1]; C2=ROOT/'reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json'; G4=ROOT/'reports/MSS_Sprint92G4_Frozen_Source_Drift_Audit.json'; G5=ROOT/'reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json'; OUTPUT=ROOT/'reports/MSS_Sprint92H1_Immutable_Research_Data_Preregistration.json'
def main():
    paths=(C2,G4,G5); before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}; values=[json.loads(p.read_text(encoding='utf-8')) for p in paths]; builder=ImmutableResearchDataPreregistration(); first=builder.build(*values); second=builder.build(*values)
    if first!=second: raise RuntimeError('deterministic rebuild failed')
    first['source_file_sha256']=before; first['audit']['deterministic_rebuild']=True; output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    print('SYMBOLS',first['dataset_scope']['symbol_count'],flush=True); print('TOTAL_CANDLES',first['dataset_scope']['total_candles'],flush=True); print('CANDLES_EXPORTED False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
