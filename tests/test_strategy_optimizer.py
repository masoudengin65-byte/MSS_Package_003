from mss.analysis.strategy_optimizer import StrategyOptimizer
from mss.domain.optimization_result import OptimizationCase


def build_cases():

    case1 = OptimizationCase()

    case1.parameters = {

        "risk": 1.0,

        "rr": 2.0,

    }

    case1.profit = 1000

    case1.drawdown = 100

    case1.win_rate = 60

    case1.profit_factor = 2.0

    case2 = OptimizationCase()

    case2.parameters = {

        "risk": 2.0,

        "rr": 3.0,

    }

    case2.profit = 1800

    case2.drawdown = 200

    case2.win_rate = 72

    case2.profit_factor = 2.8

    case3 = OptimizationCase()

    case3.parameters = {

        "risk": 0.5,

        "rr": 1.5,

    }

    case3.profit = 700

    case3.drawdown = 80

    case3.win_rate = 55

    case3.profit_factor = 1.7

    return [

        case1,

        case2,

        case3,

    ]


def test_optimizer_best_case():

    result = StrategyOptimizer().optimize(

        build_cases(),

    )

    assert result.valid

    assert result.total_cases == 3

    assert result.best_case is not None

    assert result.best_case.parameters["risk"] == 2.0


def test_optimizer_empty():

    result = StrategyOptimizer().optimize(

        [],

    )

    assert not result.valid

    assert result.total_cases == 0


def test_optimizer_none():

    result = StrategyOptimizer().optimize(

        None,

    )

    assert not result.valid

    assert result.best_case is None