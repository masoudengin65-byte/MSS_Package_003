"""Market eligibility and portfolio risk governor.

Sprint 92H.14.5

Pure decision layer:
- no order_send
- no order_check
- no MT5 write operations
- fail-safe by default
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MarketEligibilityResult:
    eligible: bool
    reason: str
    spread_price: float
    stop_distance: float
    spread_to_stop_ratio: float


@dataclass(frozen=True)
class PortfolioPosition:
    symbol: str
    asset_class: str
    risk_percent: float
    exposure_tags: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioRiskResult:
    allowed: bool
    reason: str
    total_open_risk_percent: float
    projected_total_risk_percent: float
    open_position_count: int
    projected_position_count: int


class MarketEligibilityGate:
    MAX_SPREAD_TO_STOP_RATIO = 0.20

    @classmethod
    def evaluate(
        cls,
        *,
        bid: float,
        ask: float,
        entry_price: float,
        stop_loss: float,
        symbol_tradable: bool,
        quote_fresh: bool,
    ) -> MarketEligibilityResult:

        if not symbol_tradable:
            return MarketEligibilityResult(
                False,
                "SYMBOL_NOT_TRADABLE",
                0.0,
                0.0,
                0.0,
            )

        if not quote_fresh:
            return MarketEligibilityResult(
                False,
                "QUOTE_NOT_FRESH",
                0.0,
                0.0,
                0.0,
            )

        if (
            bid <= 0
            or ask <= 0
            or ask < bid
            or entry_price <= 0
            or stop_loss <= 0
        ):
            return MarketEligibilityResult(
                False,
                "INVALID_MARKET_VALUES",
                0.0,
                0.0,
                0.0,
            )

        spread_price = ask - bid
        stop_distance = abs(
            entry_price - stop_loss
        )

        if stop_distance <= 0:
            return MarketEligibilityResult(
                False,
                "INVALID_STOP_DISTANCE",
                spread_price,
                stop_distance,
                0.0,
            )

        ratio = (
            spread_price
            / stop_distance
        )

        if (
            ratio
            > cls.MAX_SPREAD_TO_STOP_RATIO
        ):
            return MarketEligibilityResult(
                False,
                "SPREAD_TO_STOP_RATIO_TOO_HIGH",
                spread_price,
                stop_distance,
                ratio,
            )

        return MarketEligibilityResult(
            True,
            "MARKET_ELIGIBLE",
            spread_price,
            stop_distance,
            ratio,
        )


class PortfolioRiskGovernor:
    MAX_RISK_PER_TRADE_PERCENT = 1.0
    MAX_TOTAL_OPEN_RISK_PERCENT = 2.0
    MAX_SIMULTANEOUS_POSITIONS = 2
    MAX_POSITIONS_PER_ASSET_CLASS = 1

    MAX_DIRECTIONAL_EXPOSURE_COUNT = 1

    @staticmethod
    def _normalize_exposure_tags(
        tags: Iterable[str],
    ) -> tuple[str, ...]:

        normalized = []

        for raw in tags:
            tag = str(raw).strip().upper()

            if not tag:
                continue

            if ":" not in tag:
                raise ValueError(
                    "EXPOSURE_TAG_MUST_BE_DIRECTIONAL"
                )

            direction, asset = tag.split(
                ":",
                1,
            )

            if direction not in (
                "LONG",
                "SHORT",
            ):
                raise ValueError(
                    "INVALID_EXPOSURE_DIRECTION"
                )

            if not asset:
                raise ValueError(
                    "INVALID_EXPOSURE_ASSET"
                )

            normalized.append(
                f"{direction}:{asset}"
            )

        return tuple(normalized)

    @classmethod
    def evaluate(
        cls,
        *,
        candidate_symbol: str,
        candidate_asset_class: str,
        candidate_risk_percent: float,
        candidate_exposure_tags: Iterable[str],
        open_positions: Iterable[
            PortfolioPosition
        ],
    ) -> PortfolioRiskResult:

        positions = tuple(
            open_positions
        )

        try:
            candidate_tags = (
                cls._normalize_exposure_tags(
                    candidate_exposure_tags
                )
            )
        except ValueError:
            return PortfolioRiskResult(
                False,
                "INVALID_DIRECTIONAL_EXPOSURE",
                sum(
                    float(
                        position.risk_percent
                    )
                    for position in positions
                ),
                0.0,
                len(positions),
                len(positions) + 1,
            )

        total_open_risk = sum(
            float(
                position.risk_percent
            )
            for position in positions
        )

        projected_risk = (
            total_open_risk
            + float(
                candidate_risk_percent
            )
        )

        projected_count = (
            len(positions) + 1
        )

        if (
            candidate_risk_percent <= 0
            or candidate_risk_percent
            >
            cls.MAX_RISK_PER_TRADE_PERCENT
        ):
            return PortfolioRiskResult(
                False,
                "RISK_PER_TRADE_LIMIT",
                total_open_risk,
                projected_risk,
                len(positions),
                projected_count,
            )

        if any(
            position.symbol
            == candidate_symbol
            for position in positions
        ):
            return PortfolioRiskResult(
                False,
                "DUPLICATE_SYMBOL_POSITION",
                total_open_risk,
                projected_risk,
                len(positions),
                projected_count,
            )

        if (
            projected_count
            >
            cls.MAX_SIMULTANEOUS_POSITIONS
        ):
            return PortfolioRiskResult(
                False,
                "MAX_SIMULTANEOUS_POSITIONS",
                total_open_risk,
                projected_risk,
                len(positions),
                projected_count,
            )

        if (
            projected_risk
            >
            cls.MAX_TOTAL_OPEN_RISK_PERCENT
        ):
            return PortfolioRiskResult(
                False,
                "MAX_TOTAL_OPEN_RISK",
                total_open_risk,
                projected_risk,
                len(positions),
                projected_count,
            )

        same_class_count = sum(
            1
            for position in positions
            if position.asset_class
            == candidate_asset_class
        )

        if (
            same_class_count + 1
            >
            cls.MAX_POSITIONS_PER_ASSET_CLASS
        ):
            return PortfolioRiskResult(
                False,
                "ASSET_CLASS_CONCENTRATION",
                total_open_risk,
                projected_risk,
                len(positions),
                projected_count,
            )

        exposure_counts = {}

        for position in positions:
            try:
                position_tags = (
                    cls._normalize_exposure_tags(
                        position.exposure_tags
                    )
                )
            except ValueError:
                return PortfolioRiskResult(
                    False,
                    "INVALID_EXISTING_DIRECTIONAL_EXPOSURE",
                    total_open_risk,
                    projected_risk,
                    len(positions),
                    projected_count,
                )

            for tag in position_tags:
                exposure_counts[tag] = (
                    exposure_counts.get(
                        tag,
                        0,
                    )
                    + 1
                )

        for tag in candidate_tags:
            projected_tag_count = (
                exposure_counts.get(
                    tag,
                    0,
                )
                + 1
            )

            if (
                projected_tag_count
                >
                cls.MAX_DIRECTIONAL_EXPOSURE_COUNT
            ):
                return PortfolioRiskResult(
                    False,
                    "DIRECTIONAL_EXPOSURE_CONCENTRATION",
                    total_open_risk,
                    projected_risk,
                    len(positions),
                    projected_count,
                )

        return PortfolioRiskResult(
            True,
            "PORTFOLIO_RISK_ALLOWED",
            total_open_risk,
            projected_risk,
            len(positions),
            projected_count,
        )
