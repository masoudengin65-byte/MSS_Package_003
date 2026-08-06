"""Read economic calendar events from YAML."""

from datetime import datetime
from pathlib import Path

import yaml

from mss.domain.economic_event import EconomicEvent


class EconomicCalendarReader:

    def read(self, filename) -> list[EconomicEvent]:
        path = Path(filename)

        if not path.exists():
            return []

        with path.open("r", encoding="utf-8") as stream:
            document = yaml.safe_load(stream) or {}

        events = []
        for item in document.get("events", []):
            try:
                event = EconomicEvent(
                    name=str(item["name"]),
                    scheduled_at=datetime.fromisoformat(str(item["scheduled_at"])),
                    impact=str(item["impact"]).upper(),
                    currency=str(item.get("currency", "")).upper(),
                )
            except (KeyError, TypeError, ValueError):
                continue

            events.append(event)

        return sorted(events, key=lambda event: event.scheduled_at)
