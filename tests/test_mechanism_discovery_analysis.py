from mss.analysis.mechanism_discovery_analysis import MechanismDiscoveryAnalysis as A


def test_metrics_and_bucket_are_deterministic():
    rows=[{'profit':2,'r_multiple':1},{'profit':-1,'r_multiple':-1}]
    assert A.metrics(rows)['expectancy']==0.5
    assert A.bucket(2,[1,2,3])==1


def test_session_is_predefined_utc_partition():
    assert A.session({'entry_time':'2020-01-01T07:59:00'})=='ASIA'
    assert A.session({'entry_time':'2020-01-01T08:00:00'})=='EUROPE'
    assert A.session({'entry_time':'2020-01-01T16:00:00'})=='AMERICAS'
