from mss.analysis.genetic_optimizer import GeneticOptimizer
from mss.domain.genetic_population import GeneticChromosome


def build_population():

    c1 = GeneticChromosome()

    c1.parameters = {

        "risk": 1.0,

        "rr": 2.0,

    }

    c1.fitness = 120.0

    c2 = GeneticChromosome()

    c2.parameters = {

        "risk": 2.0,

        "rr": 3.0,

    }

    c2.fitness = 210.0

    c3 = GeneticChromosome()

    c3.parameters = {

        "risk": 0.5,

        "rr": 1.5,

    }

    c3.fitness = 90.0

    return [

        c1,

        c2,

        c3,

    ]


def test_genetic_population():

    population = GeneticOptimizer().evaluate(

        build_population(),

    )

    assert population.valid

    assert population.population_size == 3

    assert population.generation == 1

    assert population.best is not None

    assert population.best.fitness == 210.0

    assert population.best.parameters["risk"] == 2.0


def test_empty_population():

    population = GeneticOptimizer().evaluate(

        [],

    )

    assert not population.valid

    assert population.population_size == 0

    assert population.best is None


def test_none_population():

    population = GeneticOptimizer().evaluate(

        None,

    )

    assert not population.valid

    assert population.population_size == 0

    assert population.best is None