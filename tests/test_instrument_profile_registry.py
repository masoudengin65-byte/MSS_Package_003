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

EXPANDED_DEMO_PROBE_SYMBOLS = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "USDCHF",
    "NZDUSD",
    "EURJPY",
    "GBPJPY",
    "EURGBP",
    "AUDJPY",
    "CADJPY",
    "CHFJPY",
    "EURAUD",
    "EURNZD",
    "EURCAD",
    "EURCHF",
    "GBPAUD",
    "GBPCAD",
    "GBPCHF",
    "XAUUSD",
    "XAGUSD",
    "WTI",
    "COPPER",
    "NAS100",
    "US30",
    "NETH25",
    "SPN35",
    "BITCOIN",
    "ETHEREUM",
    "BITCOIN CASH",
    "SOLANA",
)


def test_expanded_demo_probe_symbols_are_registered():
    assert len(EXPANDED_DEMO_PROBE_SYMBOLS) == 32

    unsupported = tuple(
        symbol
        for symbol in EXPANDED_DEMO_PROBE_SYMBOLS
        if InstrumentProfileRegistry.get(symbol)
        is None
    )

    assert unsupported == ()


@pytest.mark.parametrize(
    (
        "symbol",
        "asset_class",
        "base_asset",
        "quote_asset",
    ),
    (
        ("AUDUSD", "FOREX", "AUD", "USD"),
        ("EURJPY", "FOREX", "EUR", "JPY"),
        ("COPPER", "COMMODITY", "COPPER", "USD"),
        ("NAS100", "INDEX", "NAS100", "USD"),
        ("NETH25", "INDEX", "NETH25", "EUR"),
        (
            "BITCOIN CASH",
            "CRYPTO",
            "BCH",
            "USD",
        ),
        ("SOLANA", "CRYPTO", "SOL", "USD"),
    ),
)
def test_expanded_instrument_profile_metadata(
    symbol,
    asset_class,
    base_asset,
    quote_asset,
):
    profile = InstrumentProfileRegistry.get(
        symbol
    )

    assert profile is not None
    assert profile.asset_class == asset_class
    assert profile.base_asset == base_asset
    assert profile.quote_asset == quote_asset


@pytest.mark.parametrize(
    "symbol",
    EXPANDED_DEMO_PROBE_SYMBOLS,
)
def test_expanded_symbols_have_both_directional_exposures(
    symbol,
):
    buy = (
        InstrumentProfileRegistry
        .directional_exposure(
            symbol=symbol,
            direction="BUY",
        )
    )
    sell = (
        InstrumentProfileRegistry
        .directional_exposure(
            symbol=symbol,
            direction="SELL",
        )
    )

    assert buy is not None
    assert sell is not None

    assert len(buy.exposure_tags) == 2
    assert len(sell.exposure_tags) == 2

    assert all(
        tag.startswith(
            ("LONG:", "SHORT:")
        )
        for tag in buy.exposure_tags
    )

    assert all(
        tag.startswith(
            ("LONG:", "SHORT:")
        )
        for tag in sell.exposure_tags
    )
