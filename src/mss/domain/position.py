"""
MSS Position
Version : 1.0
Sprint : 10.0
Compatible : v0.21
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:

    ticket: int = 0

    symbol: str = ""

    direction: str = ""

    volume: float = 0.0

    entry_price: float = 0.0

    stop_loss: float = 0.0

    take_profit: float = 0.0

    open_time: datetime | None = None

    close_time: datetime | None = None

    close_price: float = 0.0

    profit: float = 0.0

    swap: float = 0.0

    commission: float = 0.0

    status: str = "OPEN"

    valid: bool = False