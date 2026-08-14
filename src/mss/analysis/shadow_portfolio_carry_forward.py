"""One-time Shadow portfolio carry-forward protocol.

Sprint 92H.14.5b.1

Transfers ownership of an already-open predecessor
Shadow position into the current journal namespace.

Guarantees:
- predecessor journal is read-only
- predecessor hash is checked before/after
- no MT5 calls
- no real execution APIs
- target event remains compatible with existing
  Shadow lifecycle recovery
- import is idempotent
- a previously consumed predecessor position is
  never re-imported
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from mss.analysis.shadow_portfolio_risk_recovery import (
    ShadowPortfolioRiskRecovery,
)
from mss.analysis.shadow_position_recovery import (
    ShadowPositionRecovery,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


@dataclass(frozen=True)
class ShadowPortfolioCarryForwardResult:
    valid: bool = False
    action: str = "BLOCK"
    reason: str = ""

    position_id: str = ""
    symbol: str = ""

    source_event_sha256: str = ""
    target_event_sha256: str = ""

    predecessor_sha256_before: str = ""
    predecessor_sha256_after: str = ""


@dataclass(frozen=True)
class ShadowPortfolioCarryForwardConsumptionResult:
    valid: bool = False
    consumed: bool = False
    reason: str = ""

    position_id: str = ""
    symbol: str = ""
    source_event_sha256: str = ""


class ShadowPortfolioCarryForward:
    VERSION = (
        "MSS_SPRINT92H14_5B_1_"
        "SHADOW_PORTFOLIO_CARRY_FORWARD_V1"
    )

    _PROHIBITED_PATH_FRAGMENTS = (
        "sprint92h_true_oos",
        "true_oos_v2",
        "/true_oos/",
    )

    @staticmethod
    def _file_sha256(
        path: Path,
    ) -> str:

        if not path.exists():
            return ""

        return hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

    @staticmethod
    def _file_state(
        path: Path,
    ) -> tuple[bool, str]:

        if not path.exists():
            return (
                False,
                "",
            )

        return (
            True,
            hashlib.sha256(
                path.read_bytes()
            ).hexdigest(),
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
    def _path_allowed(
        cls,
        path: Path,
    ) -> bool:

        normalized = (
            str(path.resolve())
            .replace("\\", "/")
            .lower()
        )

        return not any(
            fragment in normalized
            for fragment
            in cls._PROHIBITED_PATH_FRAGMENTS
        )

    @classmethod
    def _active_open_events(
        cls,
        events: list[dict],
    ) -> dict[str, dict] | None:

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
            ).strip()

            if not position_id:
                return None

            if event_type == "POSITION_OPENED":
                if position_id in positions:
                    return None

                positions[position_id] = event

            elif event_type == "POSITION_CLOSED":
                if position_id not in positions:
                    return None

                positions.pop(
                    position_id
                )

            else:
                return None

        return positions

    @classmethod
    def _already_imported(
        cls,
        *,
        events: list[dict],
        source_event_sha256: str,
        source_position_id: str,
    ) -> bool:

        for event in events:
            payload = event.get(
                "payload",
                {},
            )

            if not isinstance(
                payload,
                dict,
            ):
                continue

            continuity = payload.get(
                "continuity_import",
                {},
            )

            if not isinstance(
                continuity,
                dict,
            ):
                continue

            if (
                str(
                    continuity.get(
                        "source_event_sha256",
                        "",
                    )
                )
                == source_event_sha256
                and
                str(
                    continuity.get(
                        "source_position_id",
                        "",
                    )
                )
                == source_position_id
            ):
                return True

        return False

    @classmethod
    def inspect_consumption(
        cls,
        *,
        predecessor_journal_path,
        current_journal_path,
        expected_position_id: str,
        expected_symbol: str,
    ) -> ShadowPortfolioCarryForwardConsumptionResult:
        """Inspect whether a predecessor position was
        already carried forward into the current journal.

        This method is strictly read-only.
        """

        predecessor_path = Path(
            predecessor_journal_path
        ).resolve()

        current_path = Path(
            current_journal_path
        ).resolve()

        expected_position_id = str(
            expected_position_id
        ).strip()

        expected_symbol = (
            str(expected_symbol)
            .strip()
            .upper()
        )

        if (
            not expected_position_id
            or not expected_symbol
        ):
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "EXPECTED_POSITION_"
                        "IDENTITY_REQUIRED"
                    ),
                )
            )

        if predecessor_path == current_path:
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "SOURCE_TARGET_"
                        "JOURNAL_COLLISION"
                    ),
                )
            )

        if (
            not cls._path_allowed(
                predecessor_path
            )
            or
            not cls._path_allowed(
                current_path
            )
        ):
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "PROHIBITED_JOURNAL_PATH"
                    ),
                )
            )

        if not predecessor_path.exists():
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "PREDECESSOR_JOURNAL_"
                        "NOT_FOUND"
                    ),
                )
            )

        try:
            predecessor_verify = (
                ShadowTradeJournal.verify(
                    predecessor_path
                )
            )

            current_verify = (
                ShadowTradeJournal.verify(
                    current_path
                )
            )

        except (
            RuntimeError,
            OSError,
            TypeError,
            ValueError,
        ):
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "JOURNAL_INTEGRITY_"
                        "CHECK_FAILED"
                    ),
                )
            )

        if not predecessor_verify["valid"]:
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "PREDECESSOR_JOURNAL_"
                        "INTEGRITY_FAILURE"
                    ),
                )
            )

        if not current_verify["valid"]:
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "CURRENT_JOURNAL_"
                        "INTEGRITY_FAILURE"
                    ),
                )
            )

        try:
            predecessor_events = (
                cls._read_events(
                    predecessor_path
                )
            )

            current_events = (
                cls._read_events(
                    current_path
                )
            )

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason="JOURNAL_READ_FAILURE",
                )
            )

        active = cls._active_open_events(
            predecessor_events
        )

        if active is None:
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "INVALID_PREDECESSOR_"
                        "LIFECYCLE"
                    ),
                )
            )

        if expected_position_id not in active:
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "EXPECTED_PREDECESSOR_"
                        "POSITION_NOT_OPEN"
                    ),
                )
            )

        source_event = active[
            expected_position_id
        ]

        source_payload = source_event.get(
            "payload",
            {},
        )

        if not isinstance(
            source_payload,
            dict,
        ):
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "INVALID_PREDECESSOR_"
                        "OPEN_PAYLOAD"
                    ),
                )
            )

        source_symbol = (
            str(
                source_payload.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if source_symbol != expected_symbol:
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "PREDECESSOR_SYMBOL_"
                        "MISMATCH"
                    ),
                )
            )

        source_event_sha = str(
            source_event.get(
                "event_sha256",
                "",
            )
        )

        if not source_event_sha:
            return (
                ShadowPortfolioCarryForwardConsumptionResult(
                    valid=False,
                    consumed=False,
                    reason=(
                        "SOURCE_EVENT_HASH_MISSING"
                    ),
                )
            )

        consumed = cls._already_imported(
            events=current_events,
            source_event_sha256=(
                source_event_sha
            ),
            source_position_id=(
                expected_position_id
            ),
        )

        return (
            ShadowPortfolioCarryForwardConsumptionResult(
                valid=True,
                consumed=consumed,
                reason=(
                    "PREDECESSOR_POSITION_"
                    "ALREADY_CONSUMED"
                    if consumed
                    else
                    "PREDECESSOR_POSITION_"
                    "NOT_YET_CONSUMED"
                ),
                position_id=(
                    expected_position_id
                ),
                symbol=expected_symbol,
                source_event_sha256=(
                    source_event_sha
                ),
            )
        )

    @classmethod
    def import_open_position(
        cls,
        *,
        predecessor_journal_path,
        current_journal_path,
        expected_position_id: str,
        expected_symbol: str,
    ) -> ShadowPortfolioCarryForwardResult:

        predecessor_path = Path(
            predecessor_journal_path
        ).resolve()

        current_path = Path(
            current_journal_path
        ).resolve()

        expected_position_id = str(
            expected_position_id
        ).strip()

        expected_symbol = (
            str(expected_symbol)
            .strip()
            .upper()
        )

        if (
            not expected_position_id
            or not expected_symbol
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "EXPECTED_POSITION_"
                    "IDENTITY_REQUIRED"
                ),
            )

        if (
            predecessor_path
            == current_path
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "SOURCE_TARGET_"
                    "JOURNAL_COLLISION"
                ),
            )

        if (
            not cls._path_allowed(
                predecessor_path
            )
            or
            not cls._path_allowed(
                current_path
            )
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "PROHIBITED_JOURNAL_PATH"
                ),
            )

        predecessor_sha_before = (
            cls._file_sha256(
                predecessor_path
            )
        )

        if not predecessor_sha_before:
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "PREDECESSOR_JOURNAL_"
                    "NOT_FOUND"
                ),
            )

        try:
            predecessor_verify = (
                ShadowTradeJournal.verify(
                    predecessor_path
                )
            )

            current_verify = (
                ShadowTradeJournal.verify(
                    current_path
                )
            )

        except (
            RuntimeError,
            OSError,
            TypeError,
            ValueError,
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "JOURNAL_INTEGRITY_"
                    "CHECK_FAILED"
                ),
            )

        if not predecessor_verify[
            "valid"
        ]:
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "PREDECESSOR_JOURNAL_"
                    "INTEGRITY_FAILURE"
                ),
            )

        if not current_verify[
            "valid"
        ]:
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "CURRENT_JOURNAL_"
                    "INTEGRITY_FAILURE"
                ),
            )

        try:
            predecessor_events = (
                cls._read_events(
                    predecessor_path
                )
            )

            current_events = (
                cls._read_events(
                    current_path
                )
            )

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "JOURNAL_READ_FAILURE"
                ),
            )

        active = cls._active_open_events(
            predecessor_events
        )

        if active is None:
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "INVALID_PREDECESSOR_"
                    "LIFECYCLE"
                ),
            )

        if (
            expected_position_id
            not in active
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "EXPECTED_PREDECESSOR_"
                    "POSITION_NOT_OPEN"
                ),
            )

        source_event = active[
            expected_position_id
        ]

        source_payload = source_event.get(
            "payload",
            {},
        )

        if not isinstance(
            source_payload,
            dict,
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "INVALID_PREDECESSOR_"
                    "OPEN_PAYLOAD"
                ),
            )

        source_symbol = (
            str(
                source_payload.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if (
            source_symbol
            != expected_symbol
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "PREDECESSOR_SYMBOL_"
                    "MISMATCH"
                ),
            )

        source_event_sha = str(
            source_event.get(
                "event_sha256",
                "",
            )
        )

        if not source_event_sha:
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "SOURCE_EVENT_HASH_MISSING"
                ),
            )

        # -------------------------------------------------
        # Idempotency:
        #
        # If the source was ever imported into the current
        # journal, do not import it again — even if that
        # current position has subsequently been closed.
        # -------------------------------------------------

        if cls._already_imported(
            events=current_events,
            source_event_sha256=(
                source_event_sha
            ),
            source_position_id=(
                expected_position_id
            ),
        ):
            predecessor_sha_after = (
                cls._file_sha256(
                    predecessor_path
                )
            )

            if (
                predecessor_sha_after
                != predecessor_sha_before
            ):
                return ShadowPortfolioCarryForwardResult(
                    valid=False,
                    action="BLOCK",
                    reason=(
                        "PREDECESSOR_JOURNAL_"
                        "MUTATED"
                    ),
                    predecessor_sha256_before=(
                        predecessor_sha_before
                    ),
                    predecessor_sha256_after=(
                        predecessor_sha_after
                    ),
                )

            return ShadowPortfolioCarryForwardResult(
                valid=True,
                action="ALREADY_IMPORTED",
                reason=(
                    "PREDECESSOR_POSITION_"
                    "ALREADY_CONSUMED"
                ),
                position_id=(
                    expected_position_id
                ),
                symbol=expected_symbol,
                source_event_sha256=(
                    source_event_sha
                ),
                predecessor_sha256_before=(
                    predecessor_sha_before
                ),
                predecessor_sha256_after=(
                    predecessor_sha_after
                ),
            )

        # First implementation is deliberately strict:
        # import is only allowed into a pristine current
        # per-symbol journal.
        if current_events:
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "CURRENT_JOURNAL_NOT_PRISTINE"
                ),
                position_id=(
                    expected_position_id
                ),
                symbol=expected_symbol,
                source_event_sha256=(
                    source_event_sha
                ),
                predecessor_sha256_before=(
                    predecessor_sha_before
                ),
            )

        target_state_before = (
            cls._file_state(
                current_path
            )
        )

        required_payload_fields = (
            "symbol",
            "direction",
            "volume",
            "entry_price",
            "stop_loss",
            "take_profit",
            "initial_risk_price",
            "risk_percent",
            "risk_amount",
        )

        if any(
            field not in source_payload
            for field
            in required_payload_fields
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "PREDECESSOR_OPEN_PAYLOAD_"
                    "INCOMPLETE"
                ),
            )

        imported_payload = dict(
            source_payload
        )

        imported_payload[
            "continuity_import"
        ] = {
            "source_position_id": (
                expected_position_id
            ),
            "source_event_sha256": (
                source_event_sha
            ),
            "source_event_sequence": (
                source_event.get(
                    "event_sequence"
                )
            ),
            "source_schema_version": (
                source_event.get(
                    "schema_version"
                )
            ),
            "source_journal_path": (
                str(predecessor_path)
            ),
            "source_journal_sha256": (
                predecessor_sha_before
            ),
            "predecessor_read_only": True,
            "performance_evidence": False,
            "carry_forward_version": (
                cls.VERSION
            ),
        }

        # -------------------------------------------------
        # Transactional staging.
        #
        # Never append directly to the real target before
        # both recovery layers have accepted the event.
        # -------------------------------------------------

        current_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        staging_path = (
            current_path.parent
            / (
                current_path.name
                + ".carry_forward."
                + uuid.uuid4().hex
                + ".tmp"
            )
        )

        target_event = None
        staging_sha256 = ""

        try:
            target_event = (
                ShadowTradeJournal.append_event(
                    path=staging_path,
                    event_type="POSITION_OPENED",
                    position_id=(
                        expected_position_id
                    ),
                    broker_epoch=int(
                        source_event[
                            "broker_epoch"
                        ]
                    ),
                    payload=imported_payload,
                )
            )

            staging_verify = (
                ShadowTradeJournal.verify(
                    staging_path
                )
            )

            if not staging_verify[
                "valid"
            ]:
                return ShadowPortfolioCarryForwardResult(
                    valid=False,
                    action="BLOCK",
                    reason=(
                        "STAGED_JOURNAL_"
                        "INTEGRITY_FAILURE"
                    ),
                )

            # ---------------------------------------------
            # Validate BOTH recovery layers before commit.
            # ---------------------------------------------

            lifecycle_recovery = (
                ShadowPositionRecovery
                .recover(
                    staging_path
                )
            )

            risk_recovery = (
                ShadowPortfolioRiskRecovery
                .recover(
                    staging_path
                )
            )

            if (
                not lifecycle_recovery.valid
                or
                lifecycle_recovery.open_position_count
                != 1
                or
                lifecycle_recovery.position
                is None
                or
                lifecycle_recovery.position.position_id
                != expected_position_id
                or
                lifecycle_recovery.position.symbol
                != expected_symbol
            ):
                return ShadowPortfolioCarryForwardResult(
                    valid=False,
                    action="BLOCK",
                    reason=(
                        "STAGED_LIFECYCLE_"
                        "RECOVERY_FAILURE"
                    ),
                )

            if (
                not risk_recovery.valid
                or
                risk_recovery.open_position_count
                != 1
                or
                risk_recovery.snapshot
                is None
                or
                len(
                    risk_recovery.snapshot.positions
                )
                != 1
                or
                risk_recovery.snapshot
                .positions[0]
                .position_id
                != expected_position_id
                or
                risk_recovery.snapshot
                .positions[0]
                .symbol
                != expected_symbol
            ):
                return ShadowPortfolioCarryForwardResult(
                    valid=False,
                    action="BLOCK",
                    reason=(
                        "STAGED_RISK_"
                        "RECOVERY_FAILURE"
                    ),
                )

            staging_sha256 = (
                cls._file_sha256(
                    staging_path
                )
            )

            if not staging_sha256:
                return ShadowPortfolioCarryForwardResult(
                    valid=False,
                    action="BLOCK",
                    reason=(
                        "STAGED_JOURNAL_HASH_MISSING"
                    ),
                )

            # ---------------------------------------------
            # Source must remain byte-for-byte immutable.
            # ---------------------------------------------

            predecessor_sha_precommit = (
                cls._file_sha256(
                    predecessor_path
                )
            )

            if (
                predecessor_sha_precommit
                != predecessor_sha_before
            ):
                return ShadowPortfolioCarryForwardResult(
                    valid=False,
                    action="BLOCK",
                    reason=(
                        "PREDECESSOR_JOURNAL_MUTATED"
                    ),
                    predecessor_sha256_before=(
                        predecessor_sha_before
                    ),
                    predecessor_sha256_after=(
                        predecessor_sha_precommit
                    ),
                )

            # ---------------------------------------------
            # Target must still be exactly as pristine as
            # it was at preflight. This prevents silently
            # overwriting a concurrent change.
            # ---------------------------------------------

            target_state_precommit = (
                cls._file_state(
                    current_path
                )
            )

            if (
                target_state_precommit
                != target_state_before
            ):
                return ShadowPortfolioCarryForwardResult(
                    valid=False,
                    action="BLOCK",
                    reason=(
                        "CURRENT_JOURNAL_CHANGED_"
                        "DURING_IMPORT"
                    ),
                )

            # ---------------------------------------------
            # Atomic commit on the same filesystem.
            # ---------------------------------------------

            try:
                os.replace(
                    staging_path,
                    current_path,
                )
            except OSError:
                return ShadowPortfolioCarryForwardResult(
                    valid=False,
                    action="BLOCK",
                    reason="ATOMIC_COMMIT_FAILED",
                    position_id=(
                        expected_position_id
                    ),
                    symbol=expected_symbol,
                    source_event_sha256=(
                        source_event_sha
                    ),
                    predecessor_sha256_before=(
                        predecessor_sha_before
                    ),
                    predecessor_sha256_after=(
                        cls._file_sha256(
                            predecessor_path
                        )
                    ),
                )

        finally:
            if staging_path.exists():
                try:
                    staging_path.unlink()
                except OSError:
                    pass

        # -------------------------------------------------
        # The committed bytes must exactly match the bytes
        # already validated in staging.
        # -------------------------------------------------

        committed_sha256 = (
            cls._file_sha256(
                current_path
            )
        )

        if (
            committed_sha256
            != staging_sha256
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "ATOMIC_COMMIT_HASH_MISMATCH"
                ),
            )

        predecessor_sha_after = (
            cls._file_sha256(
                predecessor_path
            )
        )

        if (
            predecessor_sha_after
            != predecessor_sha_before
        ):
            return ShadowPortfolioCarryForwardResult(
                valid=False,
                action="BLOCK",
                reason=(
                    "PREDECESSOR_JOURNAL_MUTATED"
                ),
                predecessor_sha256_before=(
                    predecessor_sha_before
                ),
                predecessor_sha256_after=(
                    predecessor_sha_after
                ),
            )

        return ShadowPortfolioCarryForwardResult(
            valid=True,
            action="IMPORTED",
            reason=(
                "PREDECESSOR_POSITION_"
                "CARRIED_FORWARD"
            ),
            position_id=(
                expected_position_id
            ),
            symbol=expected_symbol,
            source_event_sha256=(
                source_event_sha
            ),
            target_event_sha256=str(
                target_event[
                    "event_sha256"
                ]
            ),
            predecessor_sha256_before=(
                predecessor_sha_before
            ),
            predecessor_sha256_after=(
                predecessor_sha_after
            ),
        )
