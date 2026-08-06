from datetime import datetime

from mss.analysis.news_risk_filter import NewsRiskFilter
from mss.domain.economic_event import EconomicEvent


EVENT_TIME = datetime(2026, 8, 7, 16, 0)


def event(impact="HIGH"):
    return EconomicEvent(
        name="US Nonfarm Payrolls",
        scheduled_at=EVENT_TIME,
        impact=impact,
        currency="USD",
    )


def test_allowed_before_news_window():
    status = NewsRiskFilter().evaluate(
        datetime(2026, 8, 7, 15, 0),
        [event()],
    )

    assert status.next_event == "US Nonfarm Payrolls"
    assert status.event_impact == "HIGH"
    assert status.minutes_remaining == 60
    assert status.trading_status == "ALLOWED"


def test_high_impact_event_blocks_trading():
    status = NewsRiskFilter(block_before_minutes=30).evaluate(
        datetime(2026, 8, 7, 15, 40),
        [event()],
    )

    assert status.minutes_remaining == 20
    assert status.trading_status == "BLOCKED"


def test_post_event_cooldown():
    status = NewsRiskFilter(cooldown_after_minutes=15).evaluate(
        datetime(2026, 8, 7, 16, 5),
        [event()],
    )

    assert status.minutes_remaining == 10
    assert status.trading_status == "COOLDOWN"


def test_configurable_impact_does_not_block_medium():
    status = NewsRiskFilter(blocked_impacts=["HIGH"]).evaluate(
        datetime(2026, 8, 7, 15, 50),
        [event("MEDIUM")],
    )

    assert status.event_impact == "MEDIUM"
    assert status.trading_status == "ALLOWED"


def test_disabled_impact_level_is_ignored():
    status = NewsRiskFilter(impact_levels=["HIGH"]).evaluate(
        datetime(2026, 8, 7, 15, 50),
        [event("LOW")],
    )

    assert status.next_event == "NONE"
    assert status.trading_status == "ALLOWED"
