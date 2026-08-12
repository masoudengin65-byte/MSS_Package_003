import json
from pathlib import Path

from mss.analysis.extended_historical_universe_freeze import ExtendedHistoricalUniverseFreeze as Freeze

def rate(t): return {'time':t,'open':1.,'high':2.,'low':.5,'close':1.5,'tick_volume':1,'spread':1,'real_volume':0}

def test_exploratory_universe_is_fixed_and_role_separate():
    assert len(Freeze.EXPLORATORY)==14
    assert {x[2] for x in Freeze.EXPLORATORY}=={'FOREX','INDEX','ENERGY'}

def test_no_overlap_boundary_is_inclusive():
    assert Freeze.no_overlap([rate(100),rate(200)],200) is True
    assert Freeze.no_overlap([rate(100),rate(201)],200) is False

def test_manifest_hash_and_quality_are_deterministic(monkeypatch):
    monkeypatch.setattr(Freeze,'COUNT',3); rates=[rate(100),rate(1000),rate(1900)]
    first=Freeze.manifest_row('X','X','X',rates,2800,'EXPLORATORY_ONLY','a')
    second=Freeze.manifest_row('X','X','X',rates,2800,'EXPLORATORY_ONLY','a')
    assert first==second
    assert first['integrity']['duplicate_timestamp_count']==0

def test_completed_manifest_has_all_windows_and_no_replay():
    path=Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92E1_Extended_Historical_Universe_Freeze.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    assert data['acceptance']=={'all_original_no_overlap':True,'all_windows_eligible':True,
        'exploratory_symbol_count':14,'original_symbol_count':8}
    assert data['audit']['strategy_replay_run'] is False
    assert all(row['returned_count']>=49970 for row in data['original_universe_older_windows'])
    assert all(row['returned_count']==50000 for row in data['exploratory_universe_windows'])
    assert next(row for row in data['original_universe_older_windows'] if row['canonical_symbol']=='USDJPY')['research_role']=='OLDER_CONFIRMATORY_CANDIDATE'
