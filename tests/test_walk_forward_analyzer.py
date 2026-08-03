from mss.analysis.walk_forward_analyzer import WalkForwardAnalyzer
from mss.domain.trade_statistics import TradeStatistics


def build_reports():

    report1 = TradeStatistics()

    report1.net_profit = 1000
    report1.win_rate = 70.0
    report1.profit_factor = 2.5
    report1.max_drawdown = 120

    report2 = TradeStatistics()

    report2.net_profit = 500
    report2.win_rate = 60.0
    report2.profit_factor = 1.8
    report2.max_drawdown = 90

    report3 = TradeStatistics()

    report3.net_profit = 1500
    report3.win_rate = 80.0
    report3.profit_factor = 3.2
    report3.max_drawdown = 150

    return [

        report1,

        report2,

        report3,

    ]


def test_walk_forward():

    result = WalkForwardAnalyzer().calculate(

        build_reports(),

    )

    assert result.valid

    assert result.training_windows == 3

    assert result.testing_windows == 3

    assert result.average_profit == 1000

    assert round(result.average_win_rate, 2) == 70.00


def test_empty_walk_forward():

    result = WalkForwardAnalyzer().calculate(

        [],

    )

    assert not result.valid

    assert result.training_windows == 0


def test_none_walk_forward():

    result = WalkForwardAnalyzer().calculate(

        None,

    )

    assert not result.valid

    assert result.testing_windows == 0