from dataclasses import dataclass
from datetime import datetime


@dataclass
class FairValueGap:

    direction: str = ""

    high: float = 0.0

    low: float = 0.0

    candle_time: datetime | None = None

    filled: bool = False

    valid: bool = False