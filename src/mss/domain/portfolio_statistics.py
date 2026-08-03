"""
MSS Portfolio Statistics
Version : 1.0
Sprint : 38.0
Compatible : v0.31
"""

from dataclasses import dataclass, field

from mss.domain.trade_statistics import TradeStatistics


@dataclass
class PortfolioStatistics:

    #
    # Portfolio
    #
    symbols: list[str] = field(

        default_factory=list

    )

    #
    # Statistics
    #
    reports: dict[str, TradeStatistics] = field(

        default_factory=dict

    )

    #
    # Overall
    #
    total_symbols: int = 0

    total_trades: int = 0

    total_profit: float = 0.0

    total_loss: float = 0.0

    net_profit: float = 0.0

    average_win_rate: float = 0.0

    average_profit_factor: float = 0.0

    valid: bool = False