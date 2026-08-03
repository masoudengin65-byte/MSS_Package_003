"""
MSS Monte Carlo Engine
Version : 1.0
Sprint : 42.0
Compatible : v0.42
"""

import random

from mss.domain.monte_carlo_result import (
    MonteCarloRun,
    MonteCarloResult,
)


class MonteCarloEngine:

    def simulate(
        self,
        trades: list[float],
        simulations: int = 100,
        initial_balance: float = 10000.0,
    ) -> MonteCarloResult:

        result = MonteCarloResult()

        if trades is None:

            return result

        if len(trades) == 0:

            return result

        balances = []

        drawdowns = []

        for _ in range(simulations):

            sequence = trades.copy()

            random.shuffle(sequence)

            balance = initial_balance

            peak = balance

            max_dd = 0.0

            equity_curve = [balance]

            for trade in sequence:

                balance += trade

                equity_curve.append(balance)

                if balance > peak:

                    peak = balance

                drawdown = peak - balance

                if drawdown > max_dd:

                    max_dd = drawdown

            run = MonteCarloRun()

            run.equity_curve = equity_curve

            run.final_balance = balance

            run.max_drawdown = max_dd

            result.runs.append(run)

            balances.append(balance)

            drawdowns.append(max_dd)

        result.simulations = simulations

        result.average_final_balance = (

            sum(balances)

            / len(balances)

        )

        result.best_balance = max(balances)

        result.worst_balance = min(balances)

        result.average_drawdown = (

            sum(drawdowns)

            / len(drawdowns)

        )

        result.valid = True

        return result