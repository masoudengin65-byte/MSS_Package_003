import json
from pathlib import Path
from mss.analysis.confluence_gate_hypothesis_preregistration import ConfluenceGateHypothesisPreregistration


def test_g1_is_single_change_and_outcome_blind():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92G1_Confluence_Gate_Hypothesis_Preregistration.json').read_text(encoding='utf-8'))
    assert data['schema_version']==ConfluenceGateHypothesisPreregistration.VERSION
    assert data['candidate_contract']['no_new_numeric_thresholds'] is True
    assert data['development_test_protocol']['candidate_replay_count']==1
    assert len(data['development_test_protocol']['symbols'])==8
    assert data['audit']['outcomes_analyzed'] is False
    assert data['audit']['strategy_code_changed'] is False
    assert data['audit']['validation_accessed'] is False
