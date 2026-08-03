"""
MSS Backtest Result
Version : 1.0
Sprint : 12.0
Compatible : v0.23
"""

from dataclasses import dataclass
from dataclasses import field

from mss.domain.trade_statistics import TradeStatistics


@dataclass
class BacktestResult:

    statistics: TradeStatistics = field(

        default_factory=TradeStatistics,

    )

    processed_candles: int = 0

    generated_signals: int = 0

    executed_trades: int = 0

    execution_time: float = 0.0

    valid: bool = False