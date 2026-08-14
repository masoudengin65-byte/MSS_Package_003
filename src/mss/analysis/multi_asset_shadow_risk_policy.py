"""Composed multi-asset shadow entry risk policy.

Sprint 92H.14.5

Pure decision layer:
- no MT5 calls
- no order_send
- no order_check
- deterministic candidate selection
- fail-safe by default
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mss.analysis.instrument_profile_registry import (
    InstrumentProfileRegistry,
)
from mss.analysis.multi_symbol_candidate_arbitrator import (
    CandidateArbitrationResult,
    DeterministicCandidateArbitrator,
    ShadowEntryCandidate,
)
from mss.analysis.portfolio_risk_governor import (
    MarketEligibilityGate,
    PortfolioPosition,
    PortfolioRiskGovernor,
)


@dataclass(frozen=True)
class ShadowRiskCandidateInput:
    symbol: str
    direction: str
    bid: float
    ask: float
    entry_price: float
    stop_loss: float
    symbol_tradable: bool
    quote_fresh: bool
    risk_percent: float


@dataclass(frozen=True)
class ShadowRiskCandidateEvaluation:
    symbol: str
    direction: str
    eligible: bool
    reason: str
    asset_class: str | None
    exposure_tags: tuple[str, ...]
    spread_to_stop_ratio: float


@dataclass(frozen=True)
class MultiAssetRiskPolicyResult:
    allowed: bool
    selected_symbol: str | None
    reason: str
    evaluations: tuple[
        ShadowRiskCandidateEvaluation,
        ...
    ]
    arbitration: CandidateArbitrationResult


class MultiAssetShadowRiskPolicy:
    @classmethod
    def evaluate(
        cls,
        *,
        candidates: Iterable[
            ShadowRiskCandidateInput
        ],
        open_positions: Iterable[
            PortfolioPosition
        ],
        symbol_priority: Iterable[str],
    ) -> MultiAssetRiskPolicyResult:

        candidate_list = tuple(
            candidates
        )

        positions = tuple(
            open_positions
        )

        evaluations = []

        arbitration_candidates = []

        for candidate in candidate_list:
            symbol = (
                str(candidate.symbol)
                .strip()
                .upper()
            )

            direction = (
                str(candidate.direction)
                .strip()
                .upper()
            )

            exposure = (
                InstrumentProfileRegistry
                .directional_exposure(
                    symbol=symbol,
                    direction=direction,
                )
            )

            if exposure is None:
                evaluation = (
                    ShadowRiskCandidateEvaluation(
                        symbol=symbol,
                        direction=direction,
                        eligible=False,
                        reason=(
                            "UNSUPPORTED_INSTRUMENT_OR_DIRECTION"
                        ),
                        asset_class=None,
                        exposure_tags=(),
                        spread_to_stop_ratio=0.0,
                    )
                )

                evaluations.append(
                    evaluation
                )

                arbitration_candidates.append(
                    ShadowEntryCandidate(
                        symbol=symbol,
                        eligible=False,
                        reason=evaluation.reason,
                    )
                )

                continue

            market = (
                MarketEligibilityGate.evaluate(
                    bid=candidate.bid,
                    ask=candidate.ask,
                    entry_price=candidate.entry_price,
                    stop_loss=candidate.stop_loss,
                    symbol_tradable=(
                        candidate.symbol_tradable
                    ),
                    quote_fresh=(
                        candidate.quote_fresh
                    ),
                )
            )

            if not market.eligible:
                evaluation = (
                    ShadowRiskCandidateEvaluation(
                        symbol=symbol,
                        direction=direction,
                        eligible=False,
                        reason=market.reason,
                        asset_class=(
                            exposure.asset_class
                        ),
                        exposure_tags=(
                            exposure.exposure_tags
                        ),
                        spread_to_stop_ratio=(
                            market.spread_to_stop_ratio
                        ),
                    )
                )

                evaluations.append(
                    evaluation
                )

                arbitration_candidates.append(
                    ShadowEntryCandidate(
                        symbol=symbol,
                        eligible=False,
                        reason=evaluation.reason,
                    )
                )

                continue

            portfolio = (
                PortfolioRiskGovernor.evaluate(
                    candidate_symbol=symbol,
                    candidate_asset_class=(
                        exposure.asset_class
                    ),
                    candidate_risk_percent=(
                        candidate.risk_percent
                    ),
                    candidate_exposure_tags=(
                        exposure.exposure_tags
                    ),
                    open_positions=positions,
                )
            )

            evaluation = (
                ShadowRiskCandidateEvaluation(
                    symbol=symbol,
                    direction=direction,
                    eligible=portfolio.allowed,
                    reason=portfolio.reason,
                    asset_class=(
                        exposure.asset_class
                    ),
                    exposure_tags=(
                        exposure.exposure_tags
                    ),
                    spread_to_stop_ratio=(
                        market.spread_to_stop_ratio
                    ),
                )
            )

            evaluations.append(
                evaluation
            )

            arbitration_candidates.append(
                ShadowEntryCandidate(
                    symbol=symbol,
                    eligible=portfolio.allowed,
                    reason=portfolio.reason,
                )
            )

        arbitration = (
            DeterministicCandidateArbitrator
            .select(
                candidates=(
                    arbitration_candidates
                ),
                symbol_priority=(
                    symbol_priority
                ),
            )
        )

        return MultiAssetRiskPolicyResult(
            allowed=arbitration.allowed,
            selected_symbol=(
                arbitration.selected_symbol
            ),
            reason=arbitration.reason,
            evaluations=tuple(
                evaluations
            ),
            arbitration=arbitration,
        )
