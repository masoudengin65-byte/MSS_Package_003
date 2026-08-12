import json
from pathlib import Path
from mss.analysis.mechanism_research_closure import MechanismResearchClosure


def test_closure_blocks_unjustified_strategy_change():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92F3_Mechanism_Research_Closure.json').read_text(encoding='utf-8'))
    assert data['schema_version']==MechanismResearchClosure.VERSION
    assert data['acceptance']['no_mechanism_advanced'] is True
    assert data['production_governance']['strategy_change_authorized'] is False
    assert data['data_governance']['true_future_oos_remains_sealed'] is True
    assert data['audit']['strategy_replay_run'] is False
