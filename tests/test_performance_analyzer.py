from mss.analysis.performance_analyzer import PerformanceAnalyzer
from mss.domain.position import Position


def test_statistics():

    positions = [

        Position(

            profit=100,

            valid=True,

        ),

        Position(

            profit=50,

            valid=True,

        ),

        Position(

            profit=-40,

            valid=True,

        ),

        Position(

            profit=-10,

            valid=True,

        ),

        Position(

            profit=0,

            valid=True,

        ),

    ]

    stats = PerformanceAnalyzer().calculate(

        positions,

    )

    assert stats.valid

    assert stats.total_trades == 5

    assert stats.winning_trades == 2

    assert stats.losing_trades == 2

    assert stats.breakeven_trades == 1

    assert stats.gross_profit == 150

    assert stats.gross_loss == 50

    assert stats.net_profit == 100

    assert stats.win_rate == 40.0

    assert stats.profit_factor == 3.0

    assert stats.average_profit == 75

    assert stats.average_loss == 25

    assert stats.expectancy == 20


def test_empty_statistics():

    stats = PerformanceAnalyzer().calculate(

        [],

    )

    assert not stats.valid


def test_none_statistics():

    stats = PerformanceAnalyzer().calculate(

        None,

    )

    assert not stats.valid