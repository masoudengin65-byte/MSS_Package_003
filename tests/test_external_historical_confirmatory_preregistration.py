import json
from pathlib import Path
from mss.analysis.external_historical_confirmatory_preregistration import ExternalHistoricalConfirmatoryPreregistration as P


def test_protocol_locks_six_candidates_and_second_slice():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92E6_External_Historical_Confirmatory_Preregistration.json').read_text(encoding='utf-8'))
    assert data['selection']['symbols']==list(P.CANDIDATES)
    assert data['confirmatory_family']['hypothesis_count']==6
    assert data['confirmatory_family']['correction']=='BONFERRONI'
    assert all(x['slice_start_index_zero_based']==10000 and x['slice_end_index_exclusive']==20000 for x in data['confirmatory_family']['symbols'])
    assert data['audit']['strategy_replay_run'] is False
    assert data['audit']['second_window_ohlc_inspected'] is False
    assert data['execution_policy']['authoritative_family_runs']==1
