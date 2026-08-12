import json
from pathlib import Path
from mss.analysis.mechanism_discovery_preregistration import MechanismDiscoveryPreregistration


def test_protocol_is_bounded_and_development_only():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92F1_Mechanism_Discovery_Preregistration.json').read_text(encoding='utf-8'))
    assert data['schema_version']==MechanismDiscoveryPreregistration.VERSION
    assert len(data['locked_hypothesis_families'])==5
    assert data['candidate_gate']['maximum_mechanisms_advanced']==2
    assert data['data_scope']['validation_segment_access_prohibited'] is True
    assert data['audit']['mechanism_outcomes_analyzed'] is False
    assert data['audit']['strategy_replay_run'] is False
    assert data['acceptance']['required_fields_available'] is True
