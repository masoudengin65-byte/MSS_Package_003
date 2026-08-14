"""Deterministic multi-symbol candidate arbitration.

Sprint 92H.14.5

Pure decision layer.

The selected candidate must depend only on the frozen
symbol priority and candidate eligibility, never on
thread completion order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ShadowEntryCandidate:
    symbol: str
    eligible: bool
    reason: str = ""


@dataclass(frozen=True)
class CandidateArbitrationResult:
    selected_symbol: str | None
    allowed: bool
    reason: str
    eligible_symbols: tuple[str, ...]


class DeterministicCandidateArbitrator:
    @classmethod
    def select(
        cls,
        *,
        candidates: Iterable[
            ShadowEntryCandidate
        ],
        symbol_priority: Iterable[str],
    ) -> CandidateArbitrationResult:

        candidate_list = tuple(
            candidates
        )

        priority = tuple(
            str(symbol).upper()
            for symbol in symbol_priority
        )

        if not priority:
            return CandidateArbitrationResult(
                selected_symbol=None,
                allowed=False,
                reason="EMPTY_SYMBOL_PRIORITY",
                eligible_symbols=(),
            )

        if len(priority) != len(set(priority)):
            return CandidateArbitrationResult(
                selected_symbol=None,
                allowed=False,
                reason="DUPLICATE_SYMBOL_PRIORITY",
                eligible_symbols=(),
            )

        by_symbol = {}

        for candidate in candidate_list:
            symbol = str(
                candidate.symbol
            ).upper()

            if symbol in by_symbol:
                return CandidateArbitrationResult(
                    selected_symbol=None,
                    allowed=False,
                    reason="DUPLICATE_CANDIDATE_SYMBOL",
                    eligible_symbols=(),
                )

            by_symbol[symbol] = candidate

        eligible_symbols = tuple(
            symbol
            for symbol in priority
            if (
                symbol in by_symbol
                and by_symbol[
                    symbol
                ].eligible
            )
        )

        unknown_eligible = tuple(
            sorted(
                symbol
                for symbol, candidate
                in by_symbol.items()
                if (
                    candidate.eligible
                    and symbol not in priority
                )
            )
        )

        if unknown_eligible:
            return CandidateArbitrationResult(
                selected_symbol=None,
                allowed=False,
                reason="ELIGIBLE_SYMBOL_NOT_IN_PRIORITY",
                eligible_symbols=eligible_symbols,
            )

        if not eligible_symbols:
            return CandidateArbitrationResult(
                selected_symbol=None,
                allowed=False,
                reason="NO_ELIGIBLE_CANDIDATE",
                eligible_symbols=(),
            )

        return CandidateArbitrationResult(
            selected_symbol=eligible_symbols[0],
            allowed=True,
            reason="DETERMINISTIC_CANDIDATE_SELECTED",
            eligible_symbols=eligible_symbols,
        )
