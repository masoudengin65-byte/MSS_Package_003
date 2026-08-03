"""
MSS Replay Result
Version : 2.0
Sprint : 27.0
Compatible : v0.30
"""

from dataclasses import dataclass, field

from mss.domain.analysis_result import AnalysisResult
from mss.domain.trade_order import TradeOrder
from mss.domain.position import Position


@dataclass
class ReplayResult:

    processed_candles: int = 0

    generated_signals: int = 0

    executed_trades: int = 0

    elapsed_seconds: float = 0.0

    completed: bool = False

    #
    # Integration Results
    #

    analyses: list[AnalysisResult] = field(
        default_factory=list
    )

    orders: list[TradeOrder] = field(
        default_factory=list
    )

    positions: list[Position] = field(
        default_factory=list
    )