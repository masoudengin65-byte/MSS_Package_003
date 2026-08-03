from dataclasses import dataclass
from datetime import datetime


@dataclass
class OrderBlock:

    direction: str = ""

    high: float = 0.0

    low: float = 0.0

    open: float = 0.0

    close: float = 0.0

    candle_time: datetime | None = None

    mitigated: bool = False

    valid: bool = False

    validated: bool = False

mitigation_index: int = -1