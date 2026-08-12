from mss.analysis.external_historical_exploratory_analysis import ExternalHistoricalExploratoryAnalysis as A


def test_net_filters_status_and_direction():
    rows=[{"status":"CLOSED","direction":"BUY","profit":4},{"status":"OPEN","direction":"BUY","profit":9},{"status":"CLOSED","direction":"SELL","profit":-2}]
    assert A.net(rows,"BUY")==4
    assert A.net(rows,"SELL")==-2


def test_lower_returns_none_when_unavailable():
    assert A.lower({"available":False},"expectancy") is None
