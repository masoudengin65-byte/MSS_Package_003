from datetime import datetime

from mss.data.economic_calendar_reader import EconomicCalendarReader


def test_reads_and_sorts_valid_calendar_events(tmp_path):
    calendar = tmp_path / "calendar.yaml"
    calendar.write_text(
        """
events:
  - name: Later Event
    scheduled_at: "2026-08-07T15:00:00"
    impact: medium
    currency: usd
  - name: Earlier Event
    scheduled_at: "2026-08-07T12:00:00"
    impact: HIGH
  - name: Invalid Event
    impact: HIGH
""".strip(),
        encoding="utf-8",
    )

    events = EconomicCalendarReader().read(calendar)

    assert [event.name for event in events] == ["Earlier Event", "Later Event"]
    assert events[0].scheduled_at == datetime(2026, 8, 7, 12, 0)
    assert events[1].impact == "MEDIUM"
    assert events[1].currency == "USD"


def test_missing_calendar_returns_empty_list(tmp_path):
    assert EconomicCalendarReader().read(tmp_path / "missing.yaml") == []
