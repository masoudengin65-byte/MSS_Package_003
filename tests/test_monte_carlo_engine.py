from mss.analysis.monte_carlo_engine import MonteCarloEngine


def build_trades():

    return [

        120.0,
        -60.0,
        150.0,
        -40.0,
        90.0,
        -30.0,
        180.0,
        -70.0,
        110.0,
        -20.0,

    ]


def test_monte_carlo_simulation():

    result = MonteCarloEngine().simulate(

        build_trades(),

        simulations=50,

        initial_balance=10000.0,

    )

    assert result.valid

    assert result.simulations == 50

    assert len(result.runs) == 50

    assert result.best_balance >= result.worst_balance

    assert result.average_final_balance > 10000.0


def test_empty_trade_list():

    result = MonteCarloEngine().simulate(

        [],

    )

    assert not result.valid

    assert result.simulations == 0

    assert len(result.runs) == 0


def test_none_trade_list():

    result = MonteCarloEngine().simulate(

        None,

    )

    assert not result.valid

    assert result.simulations == 0

    assert len(result.runs) == 0