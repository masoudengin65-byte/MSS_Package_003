from mss.analysis.risk_engine import RiskEngine
from mss.domain.news_risk_status import NewsRiskStatus
from mss.domain.portfolio_exposure import PortfolioExposure


def test_calculate_risk_profile():

    profile = RiskEngine().calculate(

        balance=10000,

        risk_percent=1,

        stop_distance=0.002,

    )

    assert profile.valid

    assert profile.account_balance == 10000

    assert profile.risk_percent == 1

    assert profile.risk_amount == 100

    assert profile.stop_distance == 0.002

    assert profile.lot_size == 0.5


def test_invalid_balance():

    profile = RiskEngine().calculate(

        balance=0,

        risk_percent=1,

        stop_distance=0.002,

    )

    assert not profile.valid


def test_invalid_stop_distance():

    profile = RiskEngine().calculate(

        balance=10000,

        risk_percent=1,

        stop_distance=0,

    )

    assert not profile.valid


def test_news_blocked_rejects_risk_profile():
    profile = RiskEngine().calculate(
        balance=10000,
        risk_percent=1,
        stop_distance=0.002,
        news_risk_status=NewsRiskStatus(
            next_event="US Nonfarm Payrolls",
            trading_status="BLOCKED",
            valid=True,
        ),
    )

    assert not profile.valid
    assert profile.trading_status == "BLOCKED"
    assert "US Nonfarm Payrolls" in profile.reason


def test_news_cooldown_rejects_risk_profile():
    profile = RiskEngine().calculate(
        balance=10000,
        risk_percent=1,
        stop_distance=0.002,
        news_risk_status=NewsRiskStatus(
            next_event="Interest Rate Decision",
            trading_status="COOLDOWN",
            valid=True,
        ),
    )

    assert not profile.valid
    assert profile.trading_status == "COOLDOWN"


def test_news_allowed_preserves_risk_calculation():
    profile = RiskEngine().calculate(
        balance=10000,
        risk_percent=1,
        stop_distance=0.002,
        news_risk_status=NewsRiskStatus(
            trading_status="ALLOWED",
            valid=True,
        ),
    )

    assert profile.valid
    assert profile.trading_status == "ALLOWED"


def test_high_portfolio_risk_rejects_risk_profile():
    profile = RiskEngine().calculate(
        balance=10000,
        risk_percent=1,
        stop_distance=0.002,
        portfolio_exposure=PortfolioExposure(
            portfolio_risk_score=72.5,
            risk_level="HIGH",
            valid=True,
        ),
    )

    assert not profile.valid
    assert profile.trading_status == "BLOCKED"
    assert profile.portfolio_risk_level == "HIGH"
    assert profile.portfolio_risk_score == 72.5


def test_medium_portfolio_risk_allows_risk_profile():
    profile = RiskEngine().calculate(
        balance=10000,
        risk_percent=1,
        stop_distance=0.002,
        portfolio_exposure=PortfolioExposure(
            portfolio_risk_score=48.0,
            risk_level="MEDIUM",
            valid=True,
        ),
    )

    assert profile.valid
    assert profile.portfolio_risk_level == "MEDIUM"
