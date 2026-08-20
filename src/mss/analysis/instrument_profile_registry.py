"""Instrument profiles for multi-asset shadow risk control.

Sprint 92H.14.5

Pure mapping layer:
- no MT5 writes
- deterministic
- fail-safe for unsupported symbols
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentProfile:
    symbol: str
    asset_class: str
    base_asset: str
    quote_asset: str


@dataclass(frozen=True)
class DirectionalExposureProfile:
    symbol: str
    direction: str
    asset_class: str
    exposure_tags: tuple[str, ...]


class InstrumentProfileRegistry:
    _PROFILES = {
        # Forex
        "EURUSD": InstrumentProfile(
            symbol="EURUSD",
            asset_class="FOREX",
            base_asset="EUR",
            quote_asset="USD",
        ),
        "GBPUSD": InstrumentProfile(
            symbol="GBPUSD",
            asset_class="FOREX",
            base_asset="GBP",
            quote_asset="USD",
        ),
        "USDJPY": InstrumentProfile(
            symbol="USDJPY",
            asset_class="FOREX",
            base_asset="USD",
            quote_asset="JPY",
        ),
        "AUDUSD": InstrumentProfile(
            symbol="AUDUSD",
            asset_class="FOREX",
            base_asset="AUD",
            quote_asset="USD",
        ),
        "USDCAD": InstrumentProfile(
            symbol="USDCAD",
            asset_class="FOREX",
            base_asset="USD",
            quote_asset="CAD",
        ),
        "USDCHF": InstrumentProfile(
            symbol="USDCHF",
            asset_class="FOREX",
            base_asset="USD",
            quote_asset="CHF",
        ),
        "NZDUSD": InstrumentProfile(
            symbol="NZDUSD",
            asset_class="FOREX",
            base_asset="NZD",
            quote_asset="USD",
        ),
        "EURJPY": InstrumentProfile(
            symbol="EURJPY",
            asset_class="FOREX",
            base_asset="EUR",
            quote_asset="JPY",
        ),
        "GBPJPY": InstrumentProfile(
            symbol="GBPJPY",
            asset_class="FOREX",
            base_asset="GBP",
            quote_asset="JPY",
        ),
        "EURGBP": InstrumentProfile(
            symbol="EURGBP",
            asset_class="FOREX",
            base_asset="EUR",
            quote_asset="GBP",
        ),
        "AUDJPY": InstrumentProfile(
            symbol="AUDJPY",
            asset_class="FOREX",
            base_asset="AUD",
            quote_asset="JPY",
        ),
        "CADJPY": InstrumentProfile(
            symbol="CADJPY",
            asset_class="FOREX",
            base_asset="CAD",
            quote_asset="JPY",
        ),
        "CHFJPY": InstrumentProfile(
            symbol="CHFJPY",
            asset_class="FOREX",
            base_asset="CHF",
            quote_asset="JPY",
        ),
        "EURAUD": InstrumentProfile(
            symbol="EURAUD",
            asset_class="FOREX",
            base_asset="EUR",
            quote_asset="AUD",
        ),
        "EURNZD": InstrumentProfile(
            symbol="EURNZD",
            asset_class="FOREX",
            base_asset="EUR",
            quote_asset="NZD",
        ),
        "EURCAD": InstrumentProfile(
            symbol="EURCAD",
            asset_class="FOREX",
            base_asset="EUR",
            quote_asset="CAD",
        ),
        "EURCHF": InstrumentProfile(
            symbol="EURCHF",
            asset_class="FOREX",
            base_asset="EUR",
            quote_asset="CHF",
        ),
        "GBPAUD": InstrumentProfile(
            symbol="GBPAUD",
            asset_class="FOREX",
            base_asset="GBP",
            quote_asset="AUD",
        ),
        "GBPCAD": InstrumentProfile(
            symbol="GBPCAD",
            asset_class="FOREX",
            base_asset="GBP",
            quote_asset="CAD",
        ),
        "GBPCHF": InstrumentProfile(
            symbol="GBPCHF",
            asset_class="FOREX",
            base_asset="GBP",
            quote_asset="CHF",
        ),

        # Metals / energy / commodity
        "XAUUSD": InstrumentProfile(
            symbol="XAUUSD",
            asset_class="METALS",
            base_asset="XAU",
            quote_asset="USD",
        ),
        "XAGUSD": InstrumentProfile(
            symbol="XAGUSD",
            asset_class="METALS",
            base_asset="XAG",
            quote_asset="USD",
        ),
        "WTI": InstrumentProfile(
            symbol="WTI",
            asset_class="ENERGY",
            base_asset="WTI",
            quote_asset="USD",
        ),
        "COPPER": InstrumentProfile(
            symbol="COPPER",
            asset_class="COMMODITY",
            base_asset="COPPER",
            quote_asset="USD",
        ),

        # Equity indices
        "NAS100": InstrumentProfile(
            symbol="NAS100",
            asset_class="INDEX",
            base_asset="NAS100",
            quote_asset="USD",
        ),
        "US30": InstrumentProfile(
            symbol="US30",
            asset_class="INDEX",
            base_asset="US30",
            quote_asset="USD",
        ),
        "NETH25": InstrumentProfile(
            symbol="NETH25",
            asset_class="INDEX",
            base_asset="NETH25",
            quote_asset="EUR",
        ),
        "SPN35": InstrumentProfile(
            symbol="SPN35",
            asset_class="INDEX",
            base_asset="SPN35",
            quote_asset="EUR",
        ),

        # Crypto
        "BITCOIN": InstrumentProfile(
            symbol="BITCOIN",
            asset_class="CRYPTO",
            base_asset="BTC",
            quote_asset="USD",
        ),
        "ETHEREUM": InstrumentProfile(
            symbol="ETHEREUM",
            asset_class="CRYPTO",
            base_asset="ETH",
            quote_asset="USD",
        ),
        "BITCOIN CASH": InstrumentProfile(
            symbol="BITCOIN CASH",
            asset_class="CRYPTO",
            base_asset="BCH",
            quote_asset="USD",
        ),
        "SOLANA": InstrumentProfile(
            symbol="SOLANA",
            asset_class="CRYPTO",
            base_asset="SOL",
            quote_asset="USD",
        ),
    }

    @staticmethod
    def normalize_symbol(
        symbol: str,
    ) -> str:
        return str(symbol).strip().upper()

    @classmethod
    def get(
        cls,
        symbol: str,
    ) -> InstrumentProfile | None:
        normalized = cls.normalize_symbol(
            symbol
        )

        return cls._PROFILES.get(
            normalized
        )

    @classmethod
    def directional_exposure(
        cls,
        *,
        symbol: str,
        direction: str,
    ) -> DirectionalExposureProfile | None:

        profile = cls.get(
            symbol
        )

        if profile is None:
            return None

        normalized_direction = (
            str(direction)
            .strip()
            .upper()
        )

        if normalized_direction == "BUY":
            tags = (
                f"LONG:{profile.base_asset}",
                f"SHORT:{profile.quote_asset}",
            )

        elif normalized_direction == "SELL":
            tags = (
                f"SHORT:{profile.base_asset}",
                f"LONG:{profile.quote_asset}",
            )

        else:
            return None

        return DirectionalExposureProfile(
            symbol=profile.symbol,
            direction=normalized_direction,
            asset_class=profile.asset_class,
            exposure_tags=tags,
        )
