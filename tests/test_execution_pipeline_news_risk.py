from types import SimpleNamespace

from mss.analysis.execution_pipeline import ExecutionPipeline
from mss.domain.news_risk_status import NewsRiskStatus


def test_blocked_news_prevents_execution():
    setup = SimpleNamespace(
        valid=True,
        entry=1.1000,
        stop_loss=1.0950,
    )
    news_risk = NewsRiskStatus(
        next_event="US Nonfarm Payrolls",
        event_impact="HIGH",
        minutes_remaining=10,
        trading_status="BLOCKED",
        valid=True,
    )

    order, position = ExecutionPipeline().execute(
        symbol="EURUSD",
        trade_setup=setup,
        account_balance=10000,
        risk_percent=1,
        news_risk_status=news_risk,
    )

    assert not order.valid
    assert not position.valid
