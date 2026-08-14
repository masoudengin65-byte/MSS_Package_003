"""Recover portfolio risk state from Shadow journal.

Sprint 92H.14.5b

Pure recovery layer:
- verifies journal integrity first
- reconstructs open-position risk state
- no MT5 calls
- fail-safe on malformed events
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mss.analysis.shadow_portfolio_risk_state import (
    ShadowPortfolioPositionState,
    ShadowPortfolioRiskState,
    ShadowPortfolioSnapshot,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


@dataclass(frozen=True)
class ShadowPortfolioRiskRecoveryResult:
    valid: bool = False
    reason: str = ""

    event_count: int = 0
    open_position_count: int = 0

    snapshot: ShadowPortfolioSnapshot | None = None


class ShadowPortfolioRiskRecovery:
    VERSION = (
        "MSS_SPRINT92H14_5B_"
        "SHADOW_PORTFOLIO_RISK_RECOVERY_V1"
    )

    @staticmethod
    def _read_events(
        path: Path,
    ) -> list[dict]:

        if not path.exists():
            return []

        events = []

        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line in handle:
                line = line.strip()

                if not line:
                    continue

                events.append(
                    json.loads(line)
                )

        return events

    @classmethod
    def recover(
        cls,
        path,
    ) -> ShadowPortfolioRiskRecoveryResult:

        path = Path(path)

        try:
            verification = (
                ShadowTradeJournal.verify(
                    path
                )
            )

        except (
            RuntimeError,
            OSError,
            TypeError,
            ValueError,
        ):
            return (
                ShadowPortfolioRiskRecoveryResult(
                    valid=False,
                    reason=(
                        "SHADOW_JOURNAL_"
                        "INTEGRITY_FAILURE"
                    ),
                )
            )

        if not verification["valid"]:
            return (
                ShadowPortfolioRiskRecoveryResult(
                    valid=False,
                    reason=(
                        "SHADOW_JOURNAL_"
                        "INTEGRITY_FAILURE"
                    ),
                    event_count=(
                        verification.get(
                            "event_count",
                            0,
                        )
                    ),
                )
            )

        try:
            events = cls._read_events(
                path
            )

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return (
                ShadowPortfolioRiskRecoveryResult(
                    valid=False,
                    reason=(
                        "SHADOW_JOURNAL_READ_FAILURE"
                    ),
                )
            )

        positions: dict[
            str,
            ShadowPortfolioPositionState,
        ] = {}

        for event in events:
            event_type = str(
                event.get(
                    "event_type",
                    "",
                )
            )

            position_id = str(
                event.get(
                    "position_id",
                    "",
                )
            ).strip()

            if not position_id:
                return (
                    ShadowPortfolioRiskRecoveryResult(
                        valid=False,
                        reason=(
                            "INVALID_POSITION_ID"
                        ),
                        event_count=len(
                            events
                        ),
                    )
                )

            if event_type == "POSITION_OPENED":
                payload = event.get(
                    "payload",
                    {},
                )

                try:
                    state = (
                        ShadowPortfolioRiskState
                        .build_position(
                            position_id=(
                                position_id
                            ),
                            journal_path=str(
                                path.resolve()
                            ),
                            symbol=str(
                                payload[
                                    "symbol"
                                ]
                            ),
                            direction=str(
                                payload[
                                    "direction"
                                ]
                            ),
                            risk_percent=float(
                                payload[
                                    "risk_percent"
                                ]
                            ),
                            risk_amount=float(
                                payload[
                                    "risk_amount"
                                ]
                            ),
                            entry_price=float(
                                payload[
                                    "entry_price"
                                ]
                            ),
                            stop_loss=float(
                                payload[
                                    "stop_loss"
                                ]
                            ),
                            take_profit=float(
                                payload[
                                    "take_profit"
                                ]
                            ),
                            open_broker_epoch=int(
                                event[
                                    "broker_epoch"
                                ]
                            ),
                        )
                    )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    return (
                        ShadowPortfolioRiskRecoveryResult(
                            valid=False,
                            reason=(
                                "INVALID_POSITION_"
                                "OPEN_RISK_EVENT"
                            ),
                            event_count=len(
                                events
                            ),
                        )
                    )

                if state is None:
                    return (
                        ShadowPortfolioRiskRecoveryResult(
                            valid=False,
                            reason=(
                                "INVALID_POSITION_"
                                "RISK_STATE"
                            ),
                            event_count=len(
                                events
                            ),
                        )
                    )

                if (
                    position_id
                    in positions
                ):
                    return (
                        ShadowPortfolioRiskRecoveryResult(
                            valid=False,
                            reason=(
                                "DUPLICATE_OPEN_"
                                "POSITION_ID"
                            ),
                            event_count=len(
                                events
                            ),
                        )
                    )

                positions[
                    position_id
                ] = state

            elif event_type == "POSITION_CLOSED":
                if (
                    position_id
                    not in positions
                ):
                    return (
                        ShadowPortfolioRiskRecoveryResult(
                            valid=False,
                            reason=(
                                "CLOSE_WITHOUT_"
                                "OPEN_POSITION"
                            ),
                            event_count=len(
                                events
                            ),
                        )
                    )

                positions.pop(
                    position_id
                )

            else:
                return (
                    ShadowPortfolioRiskRecoveryResult(
                        valid=False,
                        reason=(
                            "UNSUPPORTED_SHADOW_"
                            "JOURNAL_EVENT"
                        ),
                        event_count=len(
                            events
                        ),
                        open_position_count=len(
                            positions
                        ),
                    )
                )

        snapshot = (
            ShadowPortfolioRiskState
            .snapshot(
                positions=tuple(
                    positions.values()
                )
            )
        )

        if not snapshot.valid:
            return (
                ShadowPortfolioRiskRecoveryResult(
                    valid=False,
                    reason=(
                        snapshot.reason
                    ),
                    event_count=len(
                        events
                    ),
                    open_position_count=len(
                        positions
                    ),
                    snapshot=snapshot,
                )
            )

        if not positions:
            reason = (
                "NO_OPEN_PORTFOLIO_"
                "RISK_POSITION"
            )
        else:
            reason = (
                "OPEN_PORTFOLIO_"
                "RISK_STATE_RECOVERED"
            )

        return (
            ShadowPortfolioRiskRecoveryResult(
                valid=True,
                reason=reason,
                event_count=len(
                    events
                ),
                open_position_count=len(
                    positions
                ),
                snapshot=snapshot,
            )
        )
