import json
from pathlib import Path
from mss.analysis.confluence_gate_development_readiness import ConfluenceGateDevelopmentReadiness


def test_ready_implementation_still_blocks_uncommitted_g3():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92G2b_Confluence_Gate_Development_Readiness.json').read_text(encoding='utf-8'))
    assert data['schema_version']==ConfluenceGateDevelopmentReadiness.VERSION
    assert data['gate']['implementation_ready'] is True
    assert data['gate']['g3_execution_allowed_now'] is False
    assert data['future_g3_execution_contract']['authoritative_candidate_runs']==1
    assert data['audit']['strategy_replay_run'] is False
    assert data['audit']['commit_created'] is False
