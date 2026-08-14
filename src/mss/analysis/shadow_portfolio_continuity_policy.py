"""Shadow portfolio continuity policy.

Sprint 92H.14.5b.1

Pure continuity decision layer:
- no MT5 calls
- no journal writes
- no execution APIs
- predecessor namespace remains read-only
- deterministic
- fail-safe
"""

from __future__ import annotations

from dataclasses import dataclass

from mss.analysis.shadow_portfolio_risk_state import (
    ShadowPortfolioSnapshot,
)


@dataclass(frozen=True)
class ShadowPortfolioContinuityResult:
    valid: bool = False
    action: str = "BLOCK"
    reason: str = ""

    current_position_count: int = 0
    predecessor_position_count: int = 0

    position_id: str = ""
    symbol: str = ""


class ShadowPortfolioContinuityPolicy:
    VERSION = (
        "MSS_SPRINT92H14_5B_1_"
        "SHADOW_PORTFOLIO_CONTINUITY_POLICY_V1"
    )

    @staticmethod
    def _same_position(
        current,
        predecessor,
    ) -> bool:

        return (
            current.position_id
            == predecessor.position_id
            and
            current.symbol
            == predecessor.symbol
            and
            current.direction
            == predecessor.direction
            and
            current.risk_percent
            == predecessor.risk_percent
            and
            current.risk_amount
            == predecessor.risk_amount
            and
            current.entry_price
            == predecessor.entry_price
            and
            current.stop_loss
            == predecessor.stop_loss
            and
            current.take_profit
            == predecessor.take_profit
            and
            current.open_broker_epoch
            == predecessor.open_broker_epoch
        )

    @classmethod
    def evaluate(
        cls,
        *,
        current_snapshot: ShadowPortfolioSnapshot,
        predecessor_snapshot: ShadowPortfolioSnapshot,
        predecessor_consumed: bool = False,
    ) -> ShadowPortfolioContinuityResult:

        if not isinstance(
            predecessor_consumed,
            bool,
        ):
            return ShadowPortfolioContinuityResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "INVALID_PREDECESSOR_"
                    "CONSUMPTION_FLAG"
                ),
            )

        if (
            current_snapshot is None
            or predecessor_snapshot is None
        ):
            return ShadowPortfolioContinuityResult(
                valid=False,
                action="BLOCK",
                reason="CONTINUITY_SNAPSHOT_REQUIRED",
            )

        if not current_snapshot.valid:
            return ShadowPortfolioContinuityResult(
                valid=False,
                action="BLOCK",
                reason="CURRENT_SNAPSHOT_INVALID",
            )

        if not predecessor_snapshot.valid:
            return ShadowPortfolioContinuityResult(
                valid=False,
                action="BLOCK",
                reason="PREDECESSOR_SNAPSHOT_INVALID",
            )

        current_positions = (
            current_snapshot.positions
        )

        predecessor_positions = (
            predecessor_snapshot.positions
        )

        current_count = len(
            current_positions
        )

        predecessor_count = len(
            predecessor_positions
        )

        # H14.5b.1 continuity remains
        # strictly single-position.
        if current_count > 1:
            return ShadowPortfolioContinuityResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "MULTIPLE_CURRENT_POSITIONS_"
                    "NOT_ALLOWED"
                ),
                current_position_count=(
                    current_count
                ),
                predecessor_position_count=(
                    predecessor_count
                ),
            )

        if predecessor_count > 1:
            return ShadowPortfolioContinuityResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "MULTIPLE_PREDECESSOR_POSITIONS_"
                    "NOT_ALLOWED"
                ),
                current_position_count=(
                    current_count
                ),
                predecessor_position_count=(
                    predecessor_count
                ),
            )

        if (
            current_count == 0
            and predecessor_count == 0
        ):
            return ShadowPortfolioContinuityResult(
                valid=True,
                action="CONTINUE",
                reason="CONTINUITY_CLEAR",
            )

        if (
            current_count == 0
            and predecessor_count == 1
        ):
            predecessor = (
                predecessor_positions[0]
            )

            if predecessor_consumed:
                return ShadowPortfolioContinuityResult(
                    valid=True,
                    action="CONTINUE",
                    reason=(
                        "PREDECESSOR_POSITION_"
                        "ALREADY_CONSUMED"
                    ),
                    current_position_count=0,
                    predecessor_position_count=1,
                    position_id=(
                        predecessor.position_id
                    ),
                    symbol=predecessor.symbol,
                )

            return ShadowPortfolioContinuityResult(
                valid=True,
                action="IMPORT_REQUIRED",
                reason=(
                    "PREDECESSOR_POSITION_"
                    "IMPORT_REQUIRED"
                ),
                current_position_count=0,
                predecessor_position_count=1,
                position_id=(
                    predecessor.position_id
                ),
                symbol=predecessor.symbol,
            )

        if (
            current_count == 1
            and predecessor_count == 0
        ):
            current = current_positions[0]

            return ShadowPortfolioContinuityResult(
                valid=True,
                action="CONTINUE",
                reason=(
                    "CURRENT_POSITION_ACTIVE"
                ),
                current_position_count=1,
                predecessor_position_count=0,
                position_id=current.position_id,
                symbol=current.symbol,
            )

        current = current_positions[0]
        predecessor = (
            predecessor_positions[0]
        )

        if cls._same_position(
            current,
            predecessor,
        ):
            return ShadowPortfolioContinuityResult(
                valid=True,
                action="CONTINUE",
                reason=(
                    "CURRENT_SUPERSEDES_"
                    "PREDECESSOR"
                ),
                current_position_count=1,
                predecessor_position_count=1,
                position_id=current.position_id,
                symbol=current.symbol,
            )

        return ShadowPortfolioContinuityResult(
            valid=False,
            action="BLOCK",
            reason=(
                "CURRENT_PREDECESSOR_"
                "POSITION_CONFLICT"
            ),
            current_position_count=1,
            predecessor_position_count=1,
        )
