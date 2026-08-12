import json
from pathlib import Path
from mss.analysis.confluence_gate_development_evaluation import ConfluenceGateDevelopmentEvaluation as E


def test_bootstrap_difference_is_deterministic_and_positive():
    c=[{'status':'CLOSED','r_multiple':1} for _ in range(20)]; b=[{'status':'CLOSED','r_multiple':0} for _ in range(20)]
    a=E.bootstrap_difference(c,b,'ordinary',100); again=E.bootstrap_difference(c,b,'ordinary',100)
    assert a==again
    assert a['ci_95']['lower']==1


def test_empty_candidate_is_explicitly_unavailable():
    assert E.bootstrap_difference([], [{'status':'CLOSED','r_multiple':0}], 'ordinary')['available'] is False


def test_failed_authoritative_run_is_preserved_and_blocks_validation():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92G3_Confluence_Gate_Development_Evaluation.json').read_text(encoding='utf-8'))
    assert data['status']=='RUN_FAILED_SOURCE_MISMATCH'
    assert data['authoritative_candidate_replay_count']==1
    assert data['rerun_prohibited'] is True
    assert data['decision']['result']=='REJECT_CONFLUENCE_GATE_NO_VALIDATION_ACCESS'
    assert data['audit']['validation_accessed'] is False
