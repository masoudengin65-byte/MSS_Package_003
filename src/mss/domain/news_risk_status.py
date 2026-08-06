"""Economic-news trading risk status."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsRiskStatus:
    next_event: str = "NONE"
    event_time: datetime | None = None
    event_impact: str = "NONE"
    minutes_remaining: int | None = None
    trading_status: str = "ALLOWED"
    valid: bool = False
