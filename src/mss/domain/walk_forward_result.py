"""
MSS Walk Forward Result
Version : 1.0
Sprint : 39.0
Compatible : v0.31
"""

from dataclasses import dataclass, field

from mss.domain.trade_statistics import TradeStatistics


@dataclass
class WalkForwardResult:

    #
    # Windows
    #
    training_windows: int = 0

    testing_windows: int = 0

    #
    # Results
    #
    reports: list[TradeStatistics] = field(

        default_factory=list

    )

    #
    # Overall
    #
    average_profit: float = 0.0

    average_win_rate: float = 0.0

    average_profit_factor: float = 0.0

    average_drawdown: float = 0.0

    valid: bool = False