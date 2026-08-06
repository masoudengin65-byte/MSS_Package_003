from datetime import datetime, time, timedelta

from mss.analysis.kill_zone_monitor import KillZoneMonitor


def test_active_kill_zone_status_and_remaining_time():
    monitor = KillZoneMonitor(
        schedules={
            "LONDON_OPEN": {"start": "08:00", "end": "11:00"},
        }
    )

    status = monitor.evaluate(datetime(2026, 1, 1, 9, 30))

    assert status.valid
    assert status.current_session == "LONDON"
    assert status.active_kill_zone == "LONDON_OPEN"
    assert status.remaining_time == timedelta(hours=1, minutes=30)
    assert status.active


def test_inactive_kill_zone_status():
    status = KillZoneMonitor().evaluate(datetime(2026, 1, 1, 22, 0))

    assert status.valid
    assert status.current_session == "NONE"
    assert status.active_kill_zone == "NONE"
    assert status.remaining_time is None
    assert not status.active


def test_missing_broker_time_is_invalid():
    status = KillZoneMonitor().evaluate(None)

    assert not status.valid
    assert not status.active


def test_reads_kill_zone_schedules_from_configuration(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
trading:
  kill_zones:
    LONDON_OPEN:
      start: "09:00"
      end: "11:30"
""".strip(),
        encoding="utf-8",
    )

    monitor = KillZoneMonitor.from_config(config)

    assert monitor.kill_zone_engine.LONDON_OPEN_START == time(9, 0)
    assert monitor.kill_zone_engine.LONDON_OPEN_END == time(11, 30)


def test_original_detector_defaults_are_not_changed():
    configured = KillZoneMonitor(
        schedules={
            "LONDON_OPEN": {"start": "09:00", "end": "11:00"},
        }
    )
    default = KillZoneMonitor()

    assert configured.kill_zone_engine.LONDON_OPEN_START == time(9, 0)
    assert default.kill_zone_engine.LONDON_OPEN_START == time(7, 0)
