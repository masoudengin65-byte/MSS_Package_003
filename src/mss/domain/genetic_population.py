"""
MSS Genetic Population
Version : 1.0
Sprint : 44.0
Compatible : v0.44
"""

from dataclasses import dataclass, field


@dataclass
class GeneticChromosome:

    parameters: dict = field(

        default_factory=dict

    )

    fitness: float = 0.0


@dataclass
class GeneticPopulation:

    chromosomes: list[GeneticChromosome] = field(

        default_factory=list

    )

    generation: int = 0

    population_size: int = 0

    best: GeneticChromosome | None = None

    valid: bool = False