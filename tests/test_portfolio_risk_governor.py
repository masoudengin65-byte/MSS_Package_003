import pytest

from mss.analysis.portfolio_risk_governor import (
    MarketEligibilityGate,
    PortfolioPosition,
    PortfolioRiskGovernor,
)


def test_market_eligibility_allows_reasonable_spread():
    result = MarketEligibilityGate.evaluate(
        bid=100.0,
        ask=100.1,
        entry_price=100.0,
        stop_loss=99.0,
        symbol_tradable=True,
        quote_fresh=True,
    )

    assert result.eligible is True
    assert result.reason == "MARKET_ELIGIBLE"
    assert result.spread_to_stop_ratio == pytest.approx(0.1)


def test_market_eligibility_blocks_high_spread_to_stop():
    result = MarketEligibilityGate.evaluate(
        bid=100.0,
        ask=100.5,
        entry_price=100.0,
        stop_loss=99.0,
        symbol_tradable=True,
        quote_fresh=True,
    )

    assert result.eligible is False
    assert (
        result.reason
        == "SPREAD_TO_STOP_RATIO_TOO_HIGH"
    )


def test_market_eligibility_blocks_stale_quote():
    result = MarketEligibilityGate.evaluate(
        bid=100.0,
        ask=100.1,
        entry_price=100.0,
        stop_loss=99.0,
        symbol_tradable=True,
        quote_fresh=False,
    )

    assert result.eligible is False
    assert result.reason == "QUOTE_NOT_FRESH"


def test_portfolio_allows_first_trade():
    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="EURUSD",
        candidate_asset_class="FOREX",
        candidate_risk_percent=1.0,
        candidate_exposure_tags=(
            "LONG:EUR",
            "SHORT:USD",
        ),
        open_positions=(),
    )

    assert result.allowed is True
    assert result.reason == "PORTFOLIO_RISK_ALLOWED"


def test_portfolio_blocks_risk_above_one_percent():
    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="EURUSD",
        candidate_asset_class="FOREX",
        candidate_risk_percent=1.1,
        candidate_exposure_tags=(
            "LONG:EUR",
            "SHORT:USD",
        ),
        open_positions=(),
    )

    assert result.allowed is False
    assert result.reason == "RISK_PER_TRADE_LIMIT"


def test_portfolio_blocks_duplicate_symbol():
    positions = (
        PortfolioPosition(
            symbol="EURUSD",
            asset_class="FOREX",
            risk_percent=1.0,
            exposure_tags=(
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
    )

    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="EURUSD",
        candidate_asset_class="FOREX",
        candidate_risk_percent=1.0,
        candidate_exposure_tags=(
            "LONG:EUR",
            "SHORT:USD",
        ),
        open_positions=positions,
    )

    assert result.allowed is False
    assert result.reason == "DUPLICATE_SYMBOL_POSITION"


def test_portfolio_blocks_same_asset_class_concentration():
    positions = (
        PortfolioPosition(
            symbol="EURUSD",
            asset_class="FOREX",
            risk_percent=1.0,
            exposure_tags=(
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
    )

    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="GBPUSD",
        candidate_asset_class="FOREX",
        candidate_risk_percent=1.0,
        candidate_exposure_tags=(
            "LONG:GBP",
            "SHORT:USD",
        ),
        open_positions=positions,
    )

    assert result.allowed is False
    assert result.reason == "ASSET_CLASS_CONCENTRATION"


def test_portfolio_allows_cross_asset_second_trade():
    positions = (
        PortfolioPosition(
            symbol="EURUSD",
            asset_class="FOREX",
            risk_percent=1.0,
            exposure_tags=(
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
    )

    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="XAUUSD",
        candidate_asset_class="METALS",
        candidate_risk_percent=1.0,
        candidate_exposure_tags=(
            "LONG:XAU",
            "LONG:USD",
        ),
        open_positions=positions,
    )

    assert result.allowed is True
    assert result.projected_total_risk_percent == 2.0
    assert result.projected_position_count == 2


def test_portfolio_blocks_directional_usd_concentration():
    positions = (
        PortfolioPosition(
            symbol="EURUSD",
            asset_class="FOREX",
            risk_percent=0.5,
            exposure_tags=(
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
    )

    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="XAUUSD",
        candidate_asset_class="METALS",
        candidate_risk_percent=0.5,
        candidate_exposure_tags=(
            "LONG:XAU",
            "SHORT:USD",
        ),
        open_positions=positions,
    )

    assert result.allowed is False
    assert (
        result.reason
        == "DIRECTIONAL_EXPOSURE_CONCENTRATION"
    )


def test_portfolio_allows_opposite_usd_direction():
    positions = (
        PortfolioPosition(
            symbol="EURUSD",
            asset_class="FOREX",
            risk_percent=0.5,
            exposure_tags=(
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
    )

    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="XAUUSD",
        candidate_asset_class="METALS",
        candidate_risk_percent=0.5,
        candidate_exposure_tags=(
            "SHORT:XAU",
            "LONG:USD",
        ),
        open_positions=positions,
    )

    assert result.allowed is True


def test_portfolio_blocks_invalid_non_directional_tag():
    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="EURUSD",
        candidate_asset_class="FOREX",
        candidate_risk_percent=1.0,
        candidate_exposure_tags=(
            "EUR",
            "USD",
        ),
        open_positions=(),
    )

    assert result.allowed is False
    assert (
        result.reason
        == "INVALID_DIRECTIONAL_EXPOSURE"
    )


def test_portfolio_blocks_third_position():
    positions = (
        PortfolioPosition(
            symbol="EURUSD",
            asset_class="FOREX",
            risk_percent=0.5,
            exposure_tags=(
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
        PortfolioPosition(
            symbol="XAUUSD",
            asset_class="METALS",
            risk_percent=0.5,
            exposure_tags=(
                "LONG:XAU",
                "LONG:USD",
            ),
        ),
    )

    result = PortfolioRiskGovernor.evaluate(
        candidate_symbol="BITCOIN",
        candidate_asset_class="CRYPTO",
        candidate_risk_percent=0.5,
        candidate_exposure_tags=(
            "LONG:BTC",
            "SHORT:USD",
        ),
        open_positions=positions,
    )

    assert result.allowed is False
    assert result.reason == "MAX_SIMULTANEOUS_POSITIONS"
