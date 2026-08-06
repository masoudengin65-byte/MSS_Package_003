from mss.analysis.portfolio_exposure_engine import PortfolioExposureEngine
from mss.domain.position import Position


def position(symbol, direction="BUY", volume=1.0, status="OPEN"):
    return Position(
        symbol=symbol,
        direction=direction,
        volume=volume,
        status=status,
        valid=True,
    )


def test_single_open_paper_trade_has_low_risk():
    result = PortfolioExposureEngine().calculate(
        [position("EURUSD", volume=0.5)]
    )

    assert result.valid
    assert result.open_positions == 1
    assert result.portfolio_exposure == 0.5
    assert result.currency_exposure == {"EUR": 0.5, "USD": -0.5}
    assert result.asset_exposure == {"EURUSD": 0.5}
    assert result.correlation_level == "LOW"
    assert result.risk_level == "LOW"


def test_two_shared_currency_trades_have_medium_portfolio_risk():
    result = PortfolioExposureEngine().calculate(
        [position("EURUSD"), position("GBPUSD")]
    )

    assert result.correlation_percent == 100.0
    assert result.correlation_level == "HIGH"
    assert result.portfolio_risk_score == 52.0
    assert result.risk_level == "MEDIUM"


def test_three_correlated_trades_have_high_portfolio_risk():
    result = PortfolioExposureEngine().calculate(
        [
            position("EURUSD"),
            position("GBPUSD"),
            position("AUDUSD"),
        ]
    )

    assert result.correlation_level == "HIGH"
    assert result.portfolio_risk_score == 64.67
    assert result.risk_level == "HIGH"


def test_opposing_currency_legs_are_not_positive_correlation():
    result = PortfolioExposureEngine().calculate(
        [position("EURUSD"), position("USDJPY")]
    )

    assert result.correlation_percent == 0.0
    assert result.correlation_level == "LOW"


def test_closed_and_invalid_positions_are_ignored():
    invalid = position("AUDUSD")
    invalid.valid = False

    result = PortfolioExposureEngine().calculate(
        [position("EURUSD", status="CLOSED"), invalid]
    )

    assert result.open_positions == 0
    assert result.portfolio_exposure == 0.0
    assert result.risk_level == "LOW"
