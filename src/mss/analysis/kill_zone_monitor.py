"""Configuration-driven session and kill-zone monitoring."""

from datetime import datetime, time, timedelta
from pathlib import Path

import yaml

from mss.analysis.kill_zone_engine import KillZoneEngine
from mss.analysis.session_engine import SessionEngine
from mss.domain.kill_zone_status import KillZoneStatus


class KillZoneMonitor:

    _SCHEDULE_ATTRIBUTES = {
        "LONDON_OPEN": ("LONDON_OPEN_START", "LONDON_OPEN_END"),
        "NEWYORK_OPEN": ("NEWYORK_OPEN_START", "NEWYORK_OPEN_END"),
        "NEWYORK_CLOSE": ("NEWYORK_CLOSE_START", "NEWYORK_CLOSE_END"),
    }

    def __init__(self, schedules=None):
        self.session_engine = SessionEngine()
        self.kill_zone_engine = KillZoneEngine()
        self._configure(schedules or {})

    @classmethod
    def from_config(cls, filename="config/config.yaml"):
        path = Path(filename)

        with path.open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}

        schedules = config.get("trading", {}).get("kill_zones", {})
        return cls(schedules=schedules)

    def evaluate(self, broker_time: datetime | None) -> KillZoneStatus:
        status = KillZoneStatus(broker_time=broker_time)

        if broker_time is None:
            return status

        session = self.session_engine.detect(broker_time)
        zone = self.kill_zone_engine.detect(broker_time)

        status.current_session = session.name or "NONE"
        status.active_kill_zone = zone.name or "NONE"
        status.active = zone.active
        status.valid = True

        if zone.active and zone.end is not None:
            end = datetime.combine(broker_time.date(), zone.end)

            if zone.end <= zone.start:
                end += timedelta(days=1)

            status.remaining_time = max(
                end - broker_time,
                timedelta(0),
            )

        return status

    def _configure(self, schedules):
        for name, values in schedules.items():
            attributes = self._SCHEDULE_ATTRIBUTES.get(name.upper())

            if attributes is None:
                continue

            start = self._parse_time(values.get("start"))
            end = self._parse_time(values.get("end"))

            if start is not None:
                setattr(self.kill_zone_engine, attributes[0], start)

            if end is not None:
                setattr(self.kill_zone_engine, attributes[1], end)

    @staticmethod
    def _parse_time(value) -> time | None:
        if isinstance(value, time):
            return value

        if not isinstance(value, str):
            return None

        try:
            return time.fromisoformat(value)
        except ValueError:
            return None
