"""
MSS Replay Candle
Version : 1.0
Sprint : 16.0
Compatible : v0.27
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReplayCandle:

    time: datetime

    open: float

    high: float

    low: float

    close: float

    tick_volume: int = 0

    spread: int = 0

    real_volume: int = 0