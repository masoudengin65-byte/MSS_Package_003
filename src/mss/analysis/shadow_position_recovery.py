"""Recovery of open Shadow Live virtual positions from journal."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)
from mss.analysis.virtual_position_engine import (
    VirtualPosition,
)


@dataclass(frozen=True)
class ShadowPositionRecoveryResult:
    valid: bool = False
    reason: str = ""

    event_count: int = 0
    open_position_count: int = 0

    position: VirtualPosition | None = None

    real_order_send_allowed: bool = False


class ShadowPositionRecovery:
    """
    Sprint 92H.14.3.3

    Recover current virtual position state from the
    append-only Shadow journal.

    No MT5 execution APIs are used.
    """

    VERSION = (
        "MSS_SPRINT92H14_3_3_SHADOW_POSITION_RECOVERY_V1"
    )

    @staticmethod
    def _read_events(path: Path):
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
    ) -> ShadowPositionRecoveryResult:

        path = Path(path)

        verification = (
            ShadowTradeJournal.verify(
                path
            )
        )

        if not verification["valid"]:
            return ShadowPositionRecoveryResult(
                valid=False,
                reason=(
                    "SHADOW_JOURNAL_INTEGRITY_FAILURE"
                ),
                event_count=verification.get(
                    "event_count",
                    0,
                ),
            )

        events = cls._read_events(
            path
        )

        positions = {}

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
            )

            if not position_id:
                continue

            if event_type == "POSITION_OPENED":
                payload = event.get(
                    "payload",
                    {},
                )

                try:
                    position = VirtualPosition(
                        position_id=position_id,
                        symbol=str(
                            payload["symbol"]
                        ),
                        direction=str(
                            payload["direction"]
                        ),
                        volume=float(
                            payload["volume"]
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
                        initial_risk_price=float(
                            payload[
                                "initial_risk_price"
                            ]
                        ),
                        open_broker_epoch=int(
                            event[
                                "broker_epoch"
                            ]
                        ),
                        status="OPEN",
                        valid=True,
                        real_order_send_allowed=False,
                    )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    return (
                        ShadowPositionRecoveryResult(
                            valid=False,
                            reason=(
                                "INVALID_POSITION_OPEN_EVENT"
                            ),
                            event_count=len(
                                events
                            ),
                        )
                    )

                positions[
                    position_id
                ] = position

            elif event_type == "POSITION_CLOSED":
                positions.pop(
                    position_id,
                    None,
                )

        open_positions = list(
            positions.values()
        )

        if not open_positions:
            return ShadowPositionRecoveryResult(
                valid=True,
                reason="NO_OPEN_SHADOW_POSITION",
                event_count=len(events),
                open_position_count=0,
            )

        if len(open_positions) > 1:
            return ShadowPositionRecoveryResult(
                valid=False,
                reason=(
                    "MULTIPLE_OPEN_SHADOW_POSITIONS"
                ),
                event_count=len(events),
                open_position_count=len(
                    open_positions
                ),
            )

        return ShadowPositionRecoveryResult(
            valid=True,
            reason="OPEN_SHADOW_POSITION_RECOVERED",
            event_count=len(events),
            open_position_count=1,
            position=open_positions[0],
            real_order_send_allowed=False,
        )
