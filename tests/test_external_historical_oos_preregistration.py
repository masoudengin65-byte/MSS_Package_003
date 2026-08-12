import json
from pathlib import Path
from mss.analysis.external_historical_oos_preregistration import ExternalHistoricalOosPreregistration

def test_completed_protocol_is_locked_before_replay():
    path=Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92E2_External_Historical_OOS_Preregistration.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    assert data['schema_version']==ExternalHistoricalOosPreregistration.VERSION
    assert data['confirmatory_test']['symbol']=='USDJPY'
    assert data['confirmatory_test']['candle_count']==10000
    assert len(data['exploratory_tests']['symbols'])==21
    assert data['exploratory_tests']['production_claims_allowed'] is False
    assert data['audit']['strategy_replay_run'] is False
    assert data['audit']['outcomes_analyzed'] is False
    assert data['execution_policy']['authoritative_runs']==1
