"""
MSS Trade Order
Version : 1.0
Sprint : 9.3
Compatible : v0.20
"""

from dataclasses import dataclass


@dataclass
class TradeOrder:

    symbol: str = ""

    direction: str = ""

    volume: float = 0.0

    entry: float = 0.0

    stop_loss: float = 0.0

    take_profit_1: float = 0.0

    take_profit_2: float = 0.0

    risk_percent: float = 0.0

    rr: float = 0.0

    comment: str = ""

    valid: bool = False