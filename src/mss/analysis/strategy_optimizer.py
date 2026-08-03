"""
MSS Strategy Optimizer
Version : 1.0
Sprint : 41.0
Compatible : v0.41
"""

from mss.domain.optimization_result import (
    OptimizationCase,
    OptimizationResult,
)


class StrategyOptimizer:

    def optimize(
        self,
        cases: list[OptimizationCase],
    ) -> OptimizationResult:

        result = OptimizationResult()

        if cases is None:

            return result

        if len(cases) == 0:

            return result

        result.cases = cases

        result.total_cases = len(cases)

        best_case = None

        best_score = float("-inf")

        for case in cases:

            #
            # Simple score:
            # Profit
            # - Drawdown
            # + Win Rate
            # + Profit Factor
            #

            case.score = (

                case.profit

                -

                case.drawdown

                +

                case.win_rate

                +

                case.profit_factor * 100.0

            )

            if case.score > best_score:

                best_score = case.score

                best_case = case

        result.best_case = best_case

        result.valid = True

        return result