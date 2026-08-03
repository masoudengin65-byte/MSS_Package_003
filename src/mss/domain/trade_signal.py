"""
MSS Trade Signal
Version : 1.0
Sprint : 8
Compatible : v0.17
"""

from dataclasses import dataclass


@dataclass
class TradeSignal:

    signal: str = "WAIT"

    confidence: float = 0.0

    reason: str = ""

    valid: bool = False

    entry: float = 0.0

    stop_loss: float = 0.0

    take_profit: float = 0.0