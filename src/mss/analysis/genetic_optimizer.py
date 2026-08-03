"""
MSS Genetic Optimizer
Version : 1.0
Sprint : 44.0
Compatible : v0.44
"""

from mss.domain.genetic_population import (
    GeneticChromosome,
    GeneticPopulation,
)


class GeneticOptimizer:

    def evaluate(
        self,
        chromosomes: list[GeneticChromosome],
    ) -> GeneticPopulation:

        population = GeneticPopulation()

        if chromosomes is None:

            return population

        if len(chromosomes) == 0:

            return population

        population.chromosomes = chromosomes

        population.population_size = len(

            chromosomes

        )

        best = None

        best_fitness = float("-inf")

        for chromosome in chromosomes:

            if chromosome.fitness > best_fitness:

                best_fitness = chromosome.fitness

                best = chromosome

        population.best = best

        population.generation = 1

        population.valid = True

        return population