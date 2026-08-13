from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class RecoveryDecision:
    status: str
    details: dict[str, Any]


class TrueOosAccrualSessionJournal:
    """
    Sprint 92H.13.5

    Crash/recovery journal for immutable True-OOS accrual.

    Important:
    - Ledger sequence and execution attempt are independent.
    - Multiple terminal NO-WRITE attempts may exist for one target sequence.
    - Any STARTED/ambiguous attempt blocks automatic continuation.
    - Sequence artifacts are never deleted or rewritten automatically.
    """

    VERSION = "MSS_SPRINT_92H13_5_SESSION_JOURNAL_V2"

    STATUS_READY = "READY_FOR_NEW_SESSION"
    STATUS_INCOMPLETE_SESSION = (
        "INCOMPLETE_SESSION_REQUIRES_REVIEW"
    )
    STATUS_PARTIAL_ARTIFACTS = (
        "PARTIAL_SEQUENCE_ARTIFACTS_REQUIRE_REVIEW"
    )
    STATUS_COMPLETED_SESSION = "SESSION_COMPLETED"
    STATUS_RECOVERY_BLOCKED = "RECOVERY_BLOCKED_NO_WRITE"

    TERMINAL_STATES = {
        "COMPLETED_WRITE",
        "NO_NEW_DATA_NO_WRITE",
        "TIME_AUTHORITY_BLOCKED_NO_WRITE",
        "PRECHECK_BLOCKED_NO_WRITE",
        "UNCOMMITTED_SEQUENCE_BLOCKED_NO_WRITE",
        "ERROR_NO_WRITE",
    }

    SAFE_RETRY_TERMINAL_STATES = {
        "NO_NEW_DATA_NO_WRITE",
        "TIME_AUTHORITY_BLOCKED_NO_WRITE",
        "PRECHECK_BLOCKED_NO_WRITE",
        "UNCOMMITTED_SEQUENCE_BLOCKED_NO_WRITE",
        "ERROR_NO_WRITE",
    }

    SESSION_RE = re.compile(
        r"^session_(?P<sequence>\d{6})_(?P<attempt>\d{6})\.json$"
    )

    @staticmethod
    def utc_now_iso() -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

    @staticmethod
    def sha256_file(path: Path) -> str:
        return hashlib.sha256(
            Path(path).read_bytes()
        ).hexdigest()

    @staticmethod
    def load_json(path: Path) -> dict[str, Any]:
        return json.loads(
            Path(path).read_text(
                encoding="utf-8"
            )
        )

    @classmethod
    def session_path(
        cls,
        *,
        journal_root: Path,
        sequence: int,
        attempt: int,
    ) -> Path:
        return (
            Path(journal_root)
            / (
                f"session_{sequence:06d}_"
                f"{attempt:06d}.json"
            )
        )

    @classmethod
    def _session_records(
        cls,
        *,
        journal_root: Path,
        sequence: int,
    ) -> list[tuple[int, Path]]:
        root = Path(journal_root)

        if not root.exists():
            return []

        records: list[tuple[int, Path]] = []

        for path in root.glob(
            f"session_{sequence:06d}_*.json"
        ):
            match = cls.SESSION_RE.match(
                path.name
            )

            if match is None:
                continue

            if int(match.group("sequence")) != int(
                sequence
            ):
                continue

            records.append(
                (
                    int(match.group("attempt")),
                    path,
                )
            )

        records.sort(
            key=lambda item: item[0]
        )

        return records

    @classmethod
    def next_attempt(
        cls,
        *,
        journal_root: Path,
        sequence: int,
    ) -> int:
        records = cls._session_records(
            journal_root=journal_root,
            sequence=sequence,
        )

        if not records:
            return 1

        return records[-1][0] + 1

    @classmethod
    def _temp_files(
        cls,
        *,
        journal_root: Path,
        sequence: int,
    ) -> list[Path]:
        root = Path(journal_root)

        if not root.exists():
            return []

        result = list(
            root.glob(
                f"session_{sequence:06d}_*.json.tmp"
            )
        )

        result.extend(
            root.glob(
                f"session_{sequence:06d}_*.tmp"
            )
        )

        return sorted(
            set(result),
            key=lambda p: p.name,
        )

    @classmethod
    def start_session(
        cls,
        *,
        journal_root: Path,
        sequence: int,
        previous_manifest_sha256: str,
        expected_chunk_path: str,
        expected_manifest_path: str,
        expected_report_path: str,
    ) -> tuple[Path, str]:
        journal_root = Path(journal_root)

        journal_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Never start if recovery state is ambiguous.
        # Caller is expected to perform full preflight,
        # but we also protect against incomplete attempts.
        records = cls._session_records(
            journal_root=journal_root,
            sequence=sequence,
        )

        for _, existing in records:
            payload = cls.load_json(existing)

            if payload.get("state") == "STARTED":
                raise RuntimeError(
                    "INCOMPLETE_SESSION_REQUIRES_REVIEW: "
                    f"{existing}"
                )

            if payload.get("state") not in cls.TERMINAL_STATES:
                raise RuntimeError(
                    "UNKNOWN_SESSION_STATE_REQUIRES_REVIEW: "
                    f"{existing}"
                )

        temp_files = cls._temp_files(
            journal_root=journal_root,
            sequence=sequence,
        )

        if temp_files:
            raise RuntimeError(
                "SESSION_TEMP_ARTIFACT_REQUIRES_REVIEW: "
                + ", ".join(
                    str(p)
                    for p in temp_files
                )
            )

        attempt = cls.next_attempt(
            journal_root=journal_root,
            sequence=sequence,
        )

        path = cls.session_path(
            journal_root=journal_root,
            sequence=sequence,
            attempt=attempt,
        )

        payload = {
            "schema_version": cls.VERSION,
            "sequence": int(sequence),
            "attempt": int(attempt),
            "state": "STARTED",
            "started_utc": cls.utc_now_iso(),
            "completed_utc": None,
            "previous_manifest_sha256": (
                previous_manifest_sha256
            ),
            "expected_artifacts": {
                "chunk": expected_chunk_path,
                "manifest": expected_manifest_path,
                "report": expected_report_path,
            },
            "result": None,
            "audit": {
                "ledger_rewrite_allowed": False,
                "frozen_artifact_overwrite_allowed": False,
                "automatic_artifact_deletion_allowed": False,
                "synthetic_backfill_allowed": False,
                "strategy_replay_run": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },
        }

        data = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

        with path.open("xb") as f:
            f.write(data)
            f.flush()

        return (
            path,
            cls.sha256_file(path),
        )

    @classmethod
    def finalize_session(
        cls,
        *,
        session_path: Path,
        terminal_state: str,
        result: dict[str, Any],
    ) -> str:
        if terminal_state not in cls.TERMINAL_STATES:
            raise RuntimeError(
                "INVALID_SESSION_TERMINAL_STATE"
            )

        path = Path(session_path)

        if not path.exists():
            raise RuntimeError(
                "SESSION_JOURNAL_NOT_FOUND"
            )

        payload = cls.load_json(path)

        if payload.get("state") != "STARTED":
            raise RuntimeError(
                "SESSION_NOT_IN_STARTED_STATE"
            )

        payload["state"] = terminal_state
        payload["completed_utc"] = (
            cls.utc_now_iso()
        )
        payload["result"] = result

        data = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

        temp = path.with_suffix(
            path.suffix + ".tmp"
        )

        if temp.exists():
            raise RuntimeError(
                "SESSION_FINALIZE_TEMP_ALREADY_EXISTS"
            )

        with temp.open("xb") as f:
            f.write(data)
            f.flush()

        temp.replace(path)

        return cls.sha256_file(path)

    @classmethod
    def inspect_recovery_state(
        cls,
        *,
        journal_root: Path,
        sequence: int,
        chunk_path: Path,
        manifest_path: Path,
        report_path: Path,
    ) -> RecoveryDecision:
        artifacts = {
            "chunk": Path(chunk_path).exists(),
            "manifest": Path(manifest_path).exists(),
            "report": Path(report_path).exists(),
        }

        temp_files = cls._temp_files(
            journal_root=journal_root,
            sequence=sequence,
        )

        if temp_files:
            return RecoveryDecision(
                status=cls.STATUS_RECOVERY_BLOCKED,
                details={
                    "sequence": sequence,
                    "reason": (
                        "SESSION_TEMP_ARTIFACT_REQUIRES_REVIEW"
                    ),
                    "temp_files": [
                        str(p)
                        for p in temp_files
                    ],
                    "artifacts": artifacts,
                    "ledger_write_allowed": False,
                    "automatic_recovery_allowed": False,
                },
            )

        records = cls._session_records(
            journal_root=journal_root,
            sequence=sequence,
        )

        completed_write_sessions: list[str] = []
        safe_terminal_sessions: list[str] = []

        for attempt, session in records:
            try:
                payload = cls.load_json(session)
            except Exception as exc:
                return RecoveryDecision(
                    status=cls.STATUS_RECOVERY_BLOCKED,
                    details={
                        "sequence": sequence,
                        "attempt": attempt,
                        "session_path": str(session),
                        "reason": (
                            "SESSION_JOURNAL_UNREADABLE"
                        ),
                        "error": str(exc),
                        "artifacts": artifacts,
                        "ledger_write_allowed": False,
                        "automatic_recovery_allowed": False,
                    },
                )

            state = payload.get("state")

            if state == "STARTED":
                return RecoveryDecision(
                    status=cls.STATUS_INCOMPLETE_SESSION,
                    details={
                        "sequence": sequence,
                        "attempt": attempt,
                        "session_path": str(session),
                        "session_state": state,
                        "artifacts": artifacts,
                        "ledger_write_allowed": False,
                        "automatic_recovery_allowed": False,
                    },
                )

            if state == "COMPLETED_WRITE":
                completed_write_sessions.append(
                    str(session)
                )
                continue

            if state in cls.SAFE_RETRY_TERMINAL_STATES:
                safe_terminal_sessions.append(
                    str(session)
                )
                continue

            return RecoveryDecision(
                status=cls.STATUS_RECOVERY_BLOCKED,
                details={
                    "sequence": sequence,
                    "attempt": attempt,
                    "session_path": str(session),
                    "session_state": state,
                    "reason": (
                        "UNKNOWN_SESSION_STATE"
                    ),
                    "artifacts": artifacts,
                    "ledger_write_allowed": False,
                    "automatic_recovery_allowed": False,
                },
            )

        # Existing target artifacts are never automatically
        # removed, reused, repaired, or overwritten.
        if any(artifacts.values()):
            return RecoveryDecision(
                status=cls.STATUS_PARTIAL_ARTIFACTS,
                details={
                    "sequence": sequence,
                    "artifacts": artifacts,
                    "completed_write_sessions": (
                        completed_write_sessions
                    ),
                    "safe_terminal_sessions": (
                        safe_terminal_sessions
                    ),
                    "ledger_write_allowed": False,
                    "automatic_artifact_deletion_allowed": False,
                    "automatic_recovery_allowed": False,
                },
            )

        # If a COMPLETED_WRITE session exists but caller still
        # considers the same sequence current, state is ambiguous.
        if completed_write_sessions:
            return RecoveryDecision(
                status=cls.STATUS_RECOVERY_BLOCKED,
                details={
                    "sequence": sequence,
                    "reason": (
                        "COMPLETED_WRITE_SESSION_BUT_TARGET_SEQUENCE_STILL_CURRENT"
                    ),
                    "completed_write_sessions": (
                        completed_write_sessions
                    ),
                    "artifacts": artifacts,
                    "ledger_write_allowed": False,
                    "automatic_recovery_allowed": False,
                },
            )

        next_attempt = cls.next_attempt(
            journal_root=journal_root,
            sequence=sequence,
        )

        return RecoveryDecision(
            status=cls.STATUS_READY,
            details={
                "sequence": sequence,
                "next_attempt": next_attempt,
                "prior_safe_terminal_attempts": len(
                    safe_terminal_sessions
                ),
                "safe_terminal_sessions": (
                    safe_terminal_sessions
                ),
                "artifacts": artifacts,
                "ledger_write_allowed": True,
                "automatic_recovery_allowed": True,
            },
        )
