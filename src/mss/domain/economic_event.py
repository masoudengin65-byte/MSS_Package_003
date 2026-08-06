"""Economic calendar event."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EconomicEvent:
    name: str
    scheduled_at: datetime
    impact: str
    currency: str = ""
