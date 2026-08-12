"""Deterministic write-once JSONL storage for frozen research candles."""
import hashlib,json
from pathlib import Path
from mss.analysis.historical_depth_audit import HistoricalDepthAudit


class ImmutableResearchDataStore:
    VERSION="MSS_SPRINT92H2_IMMUTABLE_RESEARCH_DATA_STORE_V1"
    FIELDS=('time','open','high','low','close','tick_volume','spread','real_volume')
    @staticmethod
    def canonical_row(row):
        return {'close':float(row['close']),'high':float(row['high']),'low':float(row['low']),'open':float(row['open']),'real_volume':int(row['real_volume']),'spread':int(row['spread']),'tick_volume':int(row['tick_volume']),'time_epoch_seconds':int(row['time'])}
    @classmethod
    def write_jsonl(cls,path,rates):
        path=Path(path)
        if path.exists(): raise FileExistsError(f'write-once target exists: {path}')
        with path.open('x',encoding='utf-8',newline='\n') as handle:
            for row in rates: handle.write(json.dumps(cls.canonical_row(row),sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
    @staticmethod
    def read_jsonl(path):
        rows=[]
        with Path(path).open('r',encoding='utf-8') as handle:
            for line in handle:
                x=json.loads(line); rows.append({'time':x['time_epoch_seconds'],'open':x['open'],'high':x['high'],'low':x['low'],'close':x['close'],'tick_volume':x['tick_volume'],'spread':x['spread'],'real_volume':x['real_volume']})
        return rows
    @classmethod
    def verify(cls,path,expected_count,expected_hash,expected_first,expected_last):
        rows=cls.read_jsonl(path); actual_hash=HistoricalDepthAudit.candle_hash(rows)
        return {'row_count':len(rows),'first_epoch':rows[0]['time'] if rows else None,'last_epoch':rows[-1]['time'] if rows else None,'ohlcv_sha256':actual_hash,'file_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'file_size_bytes':Path(path).stat().st_size,'verified':len(rows)==expected_count and actual_hash==expected_hash and (rows[0]['time'] if rows else None)==expected_first and (rows[-1]['time'] if rows else None)==expected_last}
