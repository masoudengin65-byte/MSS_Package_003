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
