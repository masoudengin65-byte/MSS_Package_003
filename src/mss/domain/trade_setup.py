"""
MSS Trade Setup
Version : 1.0
Sprint : 9.1
Compatible : v0.18
"""

from dataclasses import dataclass


@dataclass
class TradeSetup:

    direction: str = ""

    entry: float = 0.0

    stop_loss: float = 0.0

    take_profit_1: float = 0.0

    take_profit_2: float = 0.0

    risk: float = 0.0

    reward: float = 0.0

    rr: float = 0.0

    valid: bool = False

    reason: str = ""