from mss.analysis.frozen_source_drift_audit import FrozenSourceDriftAudit as A


def test_drift_classification_priority():
    args=(50000,50000,'a','a','b','b','h','h')
    assert A.classify(*args)=='EXACT_REPRODUCTION'
    assert A.classify(50000,49999,'a','a','b','b','h','h')=='COUNT_DRIFT'
    assert A.classify(50000,50000,'a','x','b','b','h','h')=='BOUNDARY_DRIFT'
    assert A.classify(50000,50000,'a','a','b','b','h','x')=='CONTENT_REVISION_WITH_STABLE_BOUNDARIES'
