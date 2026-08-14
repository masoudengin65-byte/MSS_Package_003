"""Aggregate Shadow portfolio risk across symbol journals.

Sprint 92H.14.5b

Pure deterministic aggregation layer:
- no MT5 calls
- no execution APIs
- verifies every journal through recovery
- validates journal/symbol ownership
- rejects duplicate sources
- rejects True-OOS paths
- produces one portfolio snapshot
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mss.analysis.instrument_profile_registry import (
    InstrumentProfileRegistry,
)
from mss.analysis.shadow_portfolio_risk_recovery import (
    ShadowPortfolioRiskRecovery,
)
from mss.analysis.shadow_portfolio_risk_state import (
    ShadowPortfolioRiskState,
    ShadowPortfolioSnapshot,
)


@dataclass(frozen=True)
class ShadowPortfolioJournalSource:
    symbol: str
    journal_path: str


@dataclass(frozen=True)
class ShadowPortfolioAggregateResult:
    valid: bool = False
    reason: str = ""

    source_count: int = 0
    recovered_source_count: int = 0
    open_position_count: int = 0

    failed_symbol: str = ""
    failed_reason: str = ""

    snapshot: ShadowPortfolioSnapshot | None = None


class ShadowPortfolioRiskAggregator:
    """
    Deterministically aggregate portfolio risk state
    from independent per-symbol Shadow journals.
    """

    VERSION = (
        "MSS_SPRINT92H14_5B_"
        "SHADOW_PORTFOLIO_RISK_AGGREGATOR_V1"
    )

    _PROHIBITED_PATH_FRAGMENTS = (
        "sprint92h_true_oos",
        "true_oos_v2",
        "/true_oos/",
    )

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        return (
            str(symbol)
            .strip()
            .upper()
        )

    @classmethod
    def _normalize_path(
        cls,
        journal_path: str,
    ) -> tuple[str, str] | None:

        raw = str(
            journal_path
        ).strip()

        if not raw:
            return None

        try:
            resolved = str(
                Path(raw).resolve()
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
        ):
            return None

        comparison_key = (
            resolved
            .replace("\\", "/")
            .lower()
        )

        if any(
            fragment
            in comparison_key
            for fragment
            in cls._PROHIBITED_PATH_FRAGMENTS
        ):
            return None

        return (
            resolved,
            comparison_key,
        )

    @classmethod
    def recover(
        cls,
        *,
        sources: Iterable[
            ShadowPortfolioJournalSource
        ],
    ) -> ShadowPortfolioAggregateResult:

        source_list = tuple(
            sources
        )

        if not source_list:
            return (
                ShadowPortfolioAggregateResult(
                    valid=False,
                    reason="NO_JOURNAL_SOURCES",
                )
            )

        prepared_sources = []

        seen_symbols = set()
        seen_paths = set()

        for source in source_list:
            symbol = cls._normalize_symbol(
                source.symbol
            )

            if not symbol:
                return (
                    ShadowPortfolioAggregateResult(
                        valid=False,
                        reason=(
                            "INVALID_SOURCE_SYMBOL"
                        ),
                        source_count=len(
                            source_list
                        ),
                    )
                )

            if (
                InstrumentProfileRegistry
                .get(symbol)
                is None
            ):
                return (
                    ShadowPortfolioAggregateResult(
                        valid=False,
                        reason=(
                            "UNSUPPORTED_SOURCE_SYMBOL"
                        ),
                        source_count=len(
                            source_list
                        ),
                        failed_symbol=symbol,
                    )
                )

            if symbol in seen_symbols:
                return (
                    ShadowPortfolioAggregateResult(
                        valid=False,
                        reason=(
                            "DUPLICATE_SOURCE_SYMBOL"
                        ),
                        source_count=len(
                            source_list
                        ),
                        failed_symbol=symbol,
                    )
                )

            normalized_path = (
                cls._normalize_path(
                    source.journal_path
                )
            )

            if normalized_path is None:
                return (
                    ShadowPortfolioAggregateResult(
                        valid=False,
                        reason=(
                            "INVALID_OR_PROHIBITED_"
                            "JOURNAL_PATH"
                        ),
                        source_count=len(
                            source_list
                        ),
                        failed_symbol=symbol,
                    )
                )

            (
                resolved_path,
                path_key,
            ) = normalized_path

            if path_key in seen_paths:
                return (
                    ShadowPortfolioAggregateResult(
                        valid=False,
                        reason=(
                            "DUPLICATE_JOURNAL_PATH"
                        ),
                        source_count=len(
                            source_list
                        ),
                        failed_symbol=symbol,
                    )
                )

            seen_symbols.add(
                symbol
            )

            seen_paths.add(
                path_key
            )

            prepared_sources.append(
                (
                    symbol,
                    resolved_path,
                )
            )

        # Deterministic aggregation order,
        # independent of caller ordering.
        prepared_sources.sort(
            key=lambda item: (
                item[0],
                item[1].lower(),
            )
        )

        combined_positions = []

        recovered_count = 0

        for (
            expected_symbol,
            journal_path,
        ) in prepared_sources:

            recovery = (
                ShadowPortfolioRiskRecovery
                .recover(
                    journal_path
                )
            )

            if not recovery.valid:
                return (
                    ShadowPortfolioAggregateResult(
                        valid=False,
                        reason=(
                            "JOURNAL_RECOVERY_FAILED"
                        ),
                        source_count=len(
                            prepared_sources
                        ),
                        recovered_source_count=(
                            recovered_count
                        ),
                        open_position_count=len(
                            combined_positions
                        ),
                        failed_symbol=(
                            expected_symbol
                        ),
                        failed_reason=(
                            recovery.reason
                        ),
                    )
                )

            recovered_count += 1

            if recovery.snapshot is None:
                return (
                    ShadowPortfolioAggregateResult(
                        valid=False,
                        reason=(
                            "RECOVERY_SNAPSHOT_MISSING"
                        ),
                        source_count=len(
                            prepared_sources
                        ),
                        recovered_source_count=(
                            recovered_count
                        ),
                        open_position_count=len(
                            combined_positions
                        ),
                        failed_symbol=(
                            expected_symbol
                        ),
                    )
                )

            for position in (
                recovery.snapshot.positions
            ):
                if (
                    position.symbol
                    != expected_symbol
                ):
                    return (
                        ShadowPortfolioAggregateResult(
                            valid=False,
                            reason=(
                                "JOURNAL_SYMBOL_MISMATCH"
                            ),
                            source_count=len(
                                prepared_sources
                            ),
                            recovered_source_count=(
                                recovered_count
                            ),
                            open_position_count=len(
                                combined_positions
                            ),
                            failed_symbol=(
                                expected_symbol
                            ),
                            failed_reason=(
                                position.symbol
                            ),
                        )
                    )

                combined_positions.append(
                    position
                )

        snapshot = (
            ShadowPortfolioRiskState
            .snapshot(
                positions=tuple(
                    combined_positions
                )
            )
        )

        if not snapshot.valid:
            return (
                ShadowPortfolioAggregateResult(
                    valid=False,
                    reason=(
                        snapshot.reason
                    ),
                    source_count=len(
                        prepared_sources
                    ),
                    recovered_source_count=(
                        recovered_count
                    ),
                    open_position_count=len(
                        combined_positions
                    ),
                    snapshot=snapshot,
                )
            )

        return (
            ShadowPortfolioAggregateResult(
                valid=True,
                reason=(
                    "PORTFOLIO_RISK_STATE_"
                    "AGGREGATED"
                ),
                source_count=len(
                    prepared_sources
                ),
                recovered_source_count=(
                    recovered_count
                ),
                open_position_count=len(
                    snapshot.positions
                ),
                snapshot=snapshot,
            )
        )
