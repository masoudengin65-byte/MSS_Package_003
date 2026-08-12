import json
from pathlib import Path
from mss.analysis.confluence_gate_research_closure import ConfluenceGateResearchClosure


def test_closure_does_not_turn_operational_failure_into_rejection():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json').read_text(encoding='utf-8'))
    assert data['schema_version']==ConfluenceGateResearchClosure.VERSION
    assert data['hypothesis_status']['statistically_rejected'] is False
    assert data['hypothesis_status']['statistically_confirmed'] is False
    assert data['governance']['g3_rerun_authorized'] is False
    assert data['governance']['validation_access_authorized'] is False
    assert data['audit']['strategy_replay_run'] is False
