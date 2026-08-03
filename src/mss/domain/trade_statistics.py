"""
MSS Trade Statistics
Version : 2.0
Sprint : 33.0
Compatible : v0.31
"""

from dataclasses import dataclass, field


@dataclass
class TradeStatistics:

    total_trades: int = 0

    winning_trades: int = 0

    losing_trades: int = 0

    breakeven_trades: int = 0

    gross_profit: float = 0.0

    gross_loss: float = 0.0

    net_profit: float = 0.0

    win_rate: float = 0.0

    profit_factor: float = 0.0

    average_profit: float = 0.0

    average_loss: float = 0.0

    expectancy: float = 0.0

    max_drawdown: float = 0.0

    equity_curve: list[float] = field(default_factory=list)

    balance_curve: list[float] = field(default_factory=list)

    valid: bool = False