from mss.analysis.backtest_engine import BacktestEngine
from mss.domain.position import Position


def test_backtest_engine():

    positions = [

        Position(

            profit=100,

            valid=True,

        ),

        Position(

            profit=-40,

            valid=True,

        ),

        Position(

            profit=60,

            valid=True,

        ),

    ]

    result = BacktestEngine().run(

        positions,

    )

    assert result.valid

    assert result.executed_trades == 3

    assert result.generated_signals == 3

    assert result.statistics.total_trades == 3

    assert result.statistics.net_profit == 120

    assert result.execution_time >= 0


def test_empty_backtest():

    result = BacktestEngine().run(

        [],

    )

    assert not result.valid


def test_none_backtest():

    result = BacktestEngine().run(

        None,

    )

    assert not result.valid