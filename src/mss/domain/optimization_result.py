"""
MSS Optimization Result
Version : 1.0
Sprint : 41.0
Compatible : v0.41
"""

from dataclasses import dataclass, field


@dataclass
class OptimizationCase:

    parameters: dict = field(

        default_factory=dict

    )

    score: float = 0.0

    profit: float = 0.0

    drawdown: float = 0.0

    win_rate: float = 0.0

    profit_factor: float = 0.0


@dataclass
class OptimizationResult:

    cases: list[OptimizationCase] = field(

        default_factory=list

    )

    best_case: OptimizationCase | None = None

    total_cases: int = 0

    valid: bool = False