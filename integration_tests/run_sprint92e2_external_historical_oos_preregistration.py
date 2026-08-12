import hashlib,json
from pathlib import Path
from mss.analysis.external_historical_oos_preregistration import ExternalHistoricalOosPreregistration

ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.json'; OUTPUT=ROOT/'reports/MSS_Sprint92E2_External_Historical_OOS_Preregistration.json'
def main():
    before=hashlib.sha256(SOURCE.read_bytes()).hexdigest(); freeze=json.loads(SOURCE.read_text(encoding='utf-8')); builder=ExternalHistoricalOosPreregistration()
    first,second=builder.build(freeze),builder.build(freeze)
    if first!=second: raise RuntimeError('Deterministic rebuild failed')
    first['audit']['deterministic_rebuild']=True; first['freeze_file_sha256']=before
    output=json.dumps(first,indent=2,sort_keys=True,allow_nan=False)+'\n'; OUTPUT.write_text(output,encoding='utf-8',newline='\n')
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=before: raise RuntimeError('Freeze changed')
    print('CONFIRMATORY USDJPY',flush=True); print('EXPLORATORY_COUNT',len(first['exploratory_tests']['symbols']),flush=True)
    print('STRATEGY_REPLAY_RUN False',flush=True); print('JSON_SHA256',hashlib.sha256(output.encode()).hexdigest(),flush=True)
if __name__=='__main__': main()
