"""Portfolio shadow position state and risk accounting.

Sprint 92H.14.5b

Pure state layer:
- no MT5 calls
- no order_send
- no order_check
- deterministic
- fail-safe
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mss.analysis.instrument_profile_registry import (
    InstrumentProfileRegistry,
)
from mss.analysis.portfolio_risk_governor import (
    PortfolioPosition,
)


@dataclass(frozen=True)
class ShadowPortfolioPositionState:
    position_id: str
    journal_path: str
    symbol: str
    direction: str

    risk_percent: float
    risk_amount: float

    asset_class: str
    exposure_tags: tuple[str, ...]

    entry_price: float
    stop_loss: float
    take_profit: float

    open_broker_epoch: int


@dataclass(frozen=True)
class ShadowPortfolioSnapshot:
    valid: bool
    reason: str

    positions: tuple[
        ShadowPortfolioPositionState,
        ...
    ]

    total_risk_percent: float
    total_risk_amount: float


class ShadowPortfolioRiskState:
    @classmethod
    def build_position(
        cls,
        *,
        position_id: str,
        journal_path: str,
        symbol: str,
        direction: str,
        risk_percent: float,
        risk_amount: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        open_broker_epoch: int,
    ) -> ShadowPortfolioPositionState | None:

        position_id = str(
            position_id
        ).strip()

        journal_path = str(
            journal_path
        ).strip()

        symbol = str(
            symbol
        ).strip().upper()

        direction = str(
            direction
        ).strip().upper()

        if not position_id:
            return None

        if not journal_path:
            return None

        normalized_journal_path = (
            journal_path
            .replace("\\", "/")
            .lower()
        )

        prohibited_fragments = (
            "sprint92h_true_oos",
            "true_oos_v2",
            "/true_oos/",
        )

        if any(
            fragment
            in normalized_journal_path
            for fragment
            in prohibited_fragments
        ):
            return None

        if (
            risk_percent <= 0
            or risk_amount <= 0
        ):
            return None

        if (
            entry_price <= 0
            or stop_loss <= 0
            or take_profit <= 0
            or open_broker_epoch <= 0
        ):
            return None

        exposure = (
            InstrumentProfileRegistry
            .directional_exposure(
                symbol=symbol,
                direction=direction,
            )
        )

        if exposure is None:
            return None

        if direction == "BUY":
            if not (
                stop_loss
                < entry_price
                < take_profit
            ):
                return None

        elif direction == "SELL":
            if not (
                take_profit
                < entry_price
                < stop_loss
            ):
                return None

        else:
            return None

        return ShadowPortfolioPositionState(
            position_id=position_id,
            journal_path=journal_path,
            symbol=symbol,
            direction=direction,
            risk_percent=float(
                risk_percent
            ),
            risk_amount=float(
                risk_amount
            ),
            asset_class=(
                exposure.asset_class
            ),
            exposure_tags=(
                exposure.exposure_tags
            ),
            entry_price=float(
                entry_price
            ),
            stop_loss=float(
                stop_loss
            ),
            take_profit=float(
                take_profit
            ),
            open_broker_epoch=int(
                open_broker_epoch
            ),
        )

    @classmethod
    def snapshot(
        cls,
        *,
        positions: Iterable[
            ShadowPortfolioPositionState
        ],
    ) -> ShadowPortfolioSnapshot:

        position_list = tuple(
            positions
        )

        ids = tuple(
            position.position_id
            for position in position_list
        )

        if len(ids) != len(set(ids)):
            return ShadowPortfolioSnapshot(
                valid=False,
                reason=(
                    "DUPLICATE_POSITION_ID"
                ),
                positions=position_list,
                total_risk_percent=0.0,
                total_risk_amount=0.0,
            )

        symbols = tuple(
            position.symbol
            for position in position_list
        )

        if (
            len(symbols)
            != len(set(symbols))
        ):
            return ShadowPortfolioSnapshot(
                valid=False,
                reason=(
                    "DUPLICATE_SYMBOL_POSITION"
                ),
                positions=position_list,
                total_risk_percent=0.0,
                total_risk_amount=0.0,
            )

        total_risk_percent = sum(
            float(
                position.risk_percent
            )
            for position in position_list
        )

        total_risk_amount = sum(
            float(
                position.risk_amount
            )
            for position in position_list
        )

        return ShadowPortfolioSnapshot(
            valid=True,
            reason=(
                "PORTFOLIO_SNAPSHOT_VALID"
            ),
            positions=position_list,
            total_risk_percent=(
                total_risk_percent
            ),
            total_risk_amount=(
                total_risk_amount
            ),
        )

    @staticmethod
    def governor_positions(
        snapshot: ShadowPortfolioSnapshot,
    ) -> tuple[
        PortfolioPosition,
        ...
    ]:

        if not snapshot.valid:
            return ()

        return tuple(
            PortfolioPosition(
                symbol=position.symbol,
                asset_class=(
                    position.asset_class
                ),
                risk_percent=(
                    position.risk_percent
                ),
                exposure_tags=(
                    position.exposure_tags
                ),
            )
            for position in snapshot.positions
        )
