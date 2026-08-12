from mss.analysis.immutable_research_data_store import ImmutableResearchDataStore as S
from mss.analysis.historical_depth_audit import HistoricalDepthAudit


def test_jsonl_roundtrip_preserves_candle_hash(tmp_path):
    rows=[{'time':1,'open':1.1,'high':1.2,'low':1.0,'close':1.15,'tick_volume':2,'spread':3,'real_volume':4}]
    path=tmp_path/'x.jsonl'; S.write_jsonl(path,rows); result=S.verify(path,1,HistoricalDepthAudit.candle_hash(rows),1,1)
    assert result['verified'] is True
    assert S.read_jsonl(path)==rows


def test_store_is_write_once(tmp_path):
    path=tmp_path/'x.jsonl'; path.write_text('')
    try: S.write_jsonl(path,[])
    except FileExistsError: pass
    else: raise AssertionError('overwrite was allowed')
