"""Combined broker-time session and kill-zone status."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class KillZoneStatus:
    broker_time: datetime | None = None
    current_session: str = "NONE"
    active_kill_zone: str = "NONE"
    remaining_time: timedelta | None = None
    active: bool = False
    valid: bool = False
