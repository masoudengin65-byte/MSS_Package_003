"""
MSS Monte Carlo Result
Version : 1.0
Sprint : 42.0
Compatible : v0.42
"""

from dataclasses import dataclass, field


@dataclass
class MonteCarloRun:

    equity_curve: list[float] = field(

        default_factory=list

    )

    final_balance: float = 0.0

    max_drawdown: float = 0.0


@dataclass
class MonteCarloResult:

    runs: list[MonteCarloRun] = field(

        default_factory=list

    )

    simulations: int = 0

    average_final_balance: float = 0.0

    best_balance: float = 0.0

    worst_balance: float = 0.0

    average_drawdown: float = 0.0

    valid: bool = False