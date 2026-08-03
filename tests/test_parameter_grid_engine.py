from mss.analysis.parameter_grid_engine import ParameterGridEngine
from mss.domain.parameter_grid import ParameterRange


def build_ranges():

    risk = ParameterRange()

    risk.name = "risk"

    risk.start = 1.0

    risk.stop = 3.0

    risk.step = 1.0

    rr = ParameterRange()

    rr.name = "rr"

    rr.start = 2.0

    rr.stop = 3.0

    rr.step = 1.0

    return [

        risk,

        rr,

    ]


def test_parameter_grid():

    grid = ParameterGridEngine().build(

        build_ranges(),

    )

    assert grid.valid

    assert grid.total_combinations == 6

    assert len(grid.combinations) == 6

    assert grid.combinations[0] == {

        "risk": 1.0,

        "rr": 2.0,

    }

    assert grid.combinations[-1] == {

        "risk": 3.0,

        "rr": 3.0,

    }


def test_empty_grid():

    grid = ParameterGridEngine().build(

        [],

    )

    assert not grid.valid

    assert grid.total_combinations == 0


def test_none_grid():

    grid = ParameterGridEngine().build(

        None,

    )

    assert not grid.valid

    assert grid.total_combinations == 0