"""
MSS Trade Journal Entry
Version : 1.0
Sprint : 13.0
Compatible : v0.24
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TradeJournalEntry:

    ticket: int = 0

    symbol: str = ""

    direction: str = ""

    volume: float = 0.0

    entry_price: float = 0.0

    exit_price: float = 0.0

    stop_loss: float = 0.0

    take_profit: float = 0.0

    profit: float = 0.0

    commission: float = 0.0

    swap: float = 0.0

    open_time: datetime | None = None

    close_time: datetime | None = None

    strategy: str = ""

    timeframe: str = ""

    comment: str = ""

    valid: bool = False