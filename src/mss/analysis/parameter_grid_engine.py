"""
MSS Parameter Grid Engine
Version : 1.0
Sprint : 43.0
Compatible : v0.43
"""

from itertools import product

from mss.domain.parameter_grid import (
    ParameterGrid,
    ParameterRange,
)


class ParameterGridEngine:

    def build(
        self,
        ranges: list[ParameterRange],
    ) -> ParameterGrid:

        grid = ParameterGrid()

        if ranges is None:

            return grid

        if len(ranges) == 0:

            return grid

        grid.ranges = ranges

        values = []

        #
        # Build value list for every parameter
        #
        for parameter in ranges:

            parameter_values = []

            value = parameter.start

            while value <= parameter.stop + 1e-9:

                parameter_values.append(

                    round(

                        value,

                        10,

                    )

                )

                value += parameter.step

            values.append(

                parameter_values

            )

        #
        # Cartesian Product
        #
        for combination in product(*values):

            item = {}

            for index, parameter in enumerate(ranges):

                item[parameter.name] = combination[index]

            grid.combinations.append(

                item

            )

        grid.total_combinations = len(

            grid.combinations

        )

        grid.valid = True

        return grid