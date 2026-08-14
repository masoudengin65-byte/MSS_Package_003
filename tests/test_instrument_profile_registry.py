import pytest

from mss.analysis.instrument_profile_registry import (
    InstrumentProfileRegistry,
)


@pytest.mark.parametrize(
    (
        "symbol",
        "direction",
        "asset_class",
        "expected_tags",
    ),
    (
        (
            "EURUSD",
            "BUY",
            "FOREX",
            (
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
        (
            "EURUSD",
            "SELL",
            "FOREX",
            (
                "SHORT:EUR",
                "LONG:USD",
            ),
        ),
        (
            "USDJPY",
            "BUY",
            "FOREX",
            (
                "LONG:USD",
                "SHORT:JPY",
            ),
        ),
        (
            "USDJPY",
            "SELL",
            "FOREX",
            (
                "SHORT:USD",
                "LONG:JPY",
            ),
        ),
        (
            "XAUUSD",
            "BUY",
            "METALS",
            (
                "LONG:XAU",
                "SHORT:USD",
            ),
        ),
        (
            "XAUUSD",
            "SELL",
            "METALS",
            (
                "SHORT:XAU",
                "LONG:USD",
            ),
        ),
        (
            "WTI",
            "BUY",
            "ENERGY",
            (
                "LONG:WTI",
                "SHORT:USD",
            ),
        ),
        (
            "BITCOIN",
            "SELL",
            "CRYPTO",
            (
                "SHORT:BTC",
                "LONG:USD",
            ),
        ),
        (
            "ETHEREUM",
            "BUY",
            "CRYPTO",
            (
                "LONG:ETH",
                "SHORT:USD",
            ),
        ),
    ),
)
def test_directional_exposure_mapping(
    symbol,
    direction,
    asset_class,
    expected_tags,
):
    result = (
        InstrumentProfileRegistry
        .directional_exposure(
            symbol=symbol,
            direction=direction,
        )
    )

    assert result is not None
    assert result.asset_class == asset_class
    assert result.exposure_tags == expected_tags


def test_symbol_normalization_is_case_insensitive():
    result = (
        InstrumentProfileRegistry
        .directional_exposure(
            symbol="eurusd",
            direction="buy",
        )
    )

    assert result is not None
    assert result.symbol == "EURUSD"
    assert result.direction == "BUY"


def test_unknown_symbol_fails_safe():
    result = (
        InstrumentProfileRegistry
        .directional_exposure(
            symbol="UNKNOWN",
            direction="BUY",
        )
    )

    assert result is None


def test_invalid_direction_fails_safe():
    result = (
        InstrumentProfileRegistry
        .directional_exposure(
            symbol="EURUSD",
            direction="INVALID",
        )
    )

    assert result is None
