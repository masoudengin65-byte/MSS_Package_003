"""Economic calendar risk gate for trade execution."""

from datetime import datetime, timedelta
from pathlib import Path

import yaml

from mss.data.economic_calendar_reader import EconomicCalendarReader
from mss.domain.news_risk_status import NewsRiskStatus


class NewsRiskFilter:

    def __init__(
        self,
        impact_levels=None,
        blocked_impacts=None,
        block_before_minutes=30,
        cooldown_after_minutes=15,
    ):
        self.impact_levels = {
            value.upper() for value in (impact_levels or ["HIGH", "MEDIUM", "LOW"])
        }
        self.blocked_impacts = {
            value.upper() for value in (blocked_impacts or ["HIGH"])
        }
        self.block_before_minutes = max(0, int(block_before_minutes))
        self.cooldown_after_minutes = max(0, int(cooldown_after_minutes))

    @classmethod
    def from_config(cls, filename="config/config.yaml"):
        path = Path(filename)
        with path.open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}

        settings = config.get("news_risk", {})
        calendar_file = settings.get(
            "calendar_file",
            "config/economic_calendar.yaml",
        )
        events = EconomicCalendarReader().read(calendar_file)
        news_filter = cls(
            impact_levels=settings.get("impact_levels"),
            blocked_impacts=settings.get("blocked_impacts"),
            block_before_minutes=settings.get("block_before_minutes", 30),
            cooldown_after_minutes=settings.get("cooldown_after_minutes", 15),
        )
        return news_filter, events

    def evaluate(self, current_time: datetime | None, events) -> NewsRiskStatus:
        status = NewsRiskStatus()

        if current_time is None:
            return status

        eligible = sorted(
            (
                event
                for event in (events or [])
                if event.impact.upper() in self.impact_levels
            ),
            key=lambda event: event.scheduled_at,
        )
        status.valid = True

        cooldown_event = self._cooldown_event(current_time, eligible)
        if cooldown_event is not None:
            cooldown_end = cooldown_event.scheduled_at + timedelta(
                minutes=self.cooldown_after_minutes
            )
            status.next_event = cooldown_event.name
            status.event_time = cooldown_event.scheduled_at
            status.event_impact = cooldown_event.impact
            status.minutes_remaining = self._minutes_until(
                current_time,
                cooldown_end,
            )
            status.trading_status = "COOLDOWN"
            return status

        upcoming = next(
            (event for event in eligible if event.scheduled_at >= current_time),
            None,
        )
        if upcoming is None:
            return status

        status.next_event = upcoming.name
        status.event_time = upcoming.scheduled_at
        status.event_impact = upcoming.impact
        status.minutes_remaining = self._minutes_until(
            current_time,
            upcoming.scheduled_at,
        )

        if (
            upcoming.impact.upper() in self.blocked_impacts
            and status.minutes_remaining <= self.block_before_minutes
        ):
            status.trading_status = "BLOCKED"

        return status

    def _cooldown_event(self, current_time, events):
        candidates = [
            event
            for event in events
            if event.impact.upper() in self.blocked_impacts
            and event.scheduled_at < current_time
            and current_time
            < event.scheduled_at + timedelta(minutes=self.cooldown_after_minutes)
        ]
        return candidates[-1] if candidates else None

    @staticmethod
    def _minutes_until(start, end) -> int:
        return max(0, int((end - start).total_seconds() // 60))
