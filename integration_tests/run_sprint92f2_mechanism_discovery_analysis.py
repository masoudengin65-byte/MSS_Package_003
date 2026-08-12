"""Run locked mechanism analysis on saved Development trades only."""
import hashlib,json
from pathlib import Path
from mss.analysis.mechanism_discovery_analysis import MechanismDiscoveryAnalysis
ROOT=Path(__file__).resolve().parents[1]; C3=ROOT/'reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json'; PROTOCOL=ROOT/'reports/MSS_Sprint92F1_Mechanism_Discovery_Preregistration.json'; OUTPUT=ROOT/'reports/MSS_Sprint92F2_Mechanism_Discovery_Analysis.json'
def main():
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (C3,PROTOCOL)}; c3=json.loads(C3.read_text(encoding='utf-8')); protocol=json.loads(PROTOCOL.read_text(encoding='utf-8')); payload=MechanismDiscoveryAnalysis().build(c3,protocol); payload['source_file_sha256']=before; output=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    print('ADVANCED',json.dumps(payload['advanced_mechanisms']),flush=True); print('DECISION',payload['conclusion']['decision'],flush=True); print('REPLAY_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
