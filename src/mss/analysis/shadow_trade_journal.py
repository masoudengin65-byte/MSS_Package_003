"""Append-only hash-chained journal for MSS Shadow Live trades."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class ShadowTradeJournalBusyError(RuntimeError):
    """Raised when another process owns the journal transaction lock."""


class ShadowTradeJournal:
    """
    Sprint 92H.14.2

    Append-only JSONL event journal.

    This journal is completely separate from sealed True-OOS
    research artifacts.
    """

    VERSION = (
        "MSS_SPRINT92H14_2_SHADOW_TRADE_JOURNAL_V1"
    )

    GENESIS_SHA256 = "0" * 64

    @classmethod
    @contextmanager
    def exclusive_transaction(
        cls,
        path,
    ):
        """Hold a fail-safe cross-process lock for one journal transaction."""

        path = Path(path)
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        lock_path = path.with_name(
            f".{path.name}.mss.lock"
        )
        lock_handle = lock_path.open("a+b")

        try:
            lock_handle.seek(0, os.SEEK_END)
            if lock_handle.tell() == 0:
                lock_handle.write(b"\0")
                lock_handle.flush()
                os.fsync(lock_handle.fileno())
            lock_handle.seek(0)

            try:
                if os.name == "nt":
                    msvcrt.locking(
                        lock_handle.fileno(),
                        msvcrt.LK_NBLCK,
                        1,
                    )
                else:
                    fcntl.flock(
                        lock_handle.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
            except OSError as exc:
                if exc.errno not in (
                    errno.EACCES,
                    errno.EAGAIN,
                ):
                    raise
                raise ShadowTradeJournalBusyError(
                    "SHADOW_JOURNAL_TRANSACTION_BUSY: "
                    f"{path}"
                ) from exc

            try:
                yield
            finally:
                lock_handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(
                        lock_handle.fileno(),
                        msvcrt.LK_UNLCK,
                        1,
                    )
                else:
                    fcntl.flock(
                        lock_handle.fileno(),
                        fcntl.LOCK_UN,
                    )
        finally:
            lock_handle.close()

    @staticmethod
    def _canonical_json(
        payload: dict[str, Any],
    ) -> str:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _sha256_text(
        text: str,
    ) -> str:
        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    @classmethod
    def _read_events(
        cls,
        path: Path,
    ) -> list[dict[str, Any]]:

        if not path.exists():
            return []

        events = []

        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line_number, line in enumerate(
                handle,
                start=1,
            ):
                line = line.rstrip("\n")

                if not line:
                    raise RuntimeError(
                        "EMPTY_JOURNAL_LINE: "
                        f"{line_number}"
                    )

                try:
                    event = json.loads(
                        line
                    )
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        "INVALID_JOURNAL_JSON: "
                        f"{line_number}"
                    ) from exc

                events.append(
                    event
                )

        return events

    @classmethod
    def verify(
        cls,
        path,
    ) -> dict[str, Any]:

        path = Path(path)

        events = cls._read_events(
            path
        )

        previous_sha = (
            cls.GENESIS_SHA256
        )

        for index, event in enumerate(
            events,
            start=1,
        ):
            recorded_previous = (
                event.get(
                    "previous_event_sha256"
                )
            )

            recorded_event_sha = (
                event.get(
                    "event_sha256"
                )
            )

            if recorded_previous != previous_sha:
                return {
                    "valid": False,
                    "reason": (
                        "PREVIOUS_HASH_MISMATCH"
                    ),
                    "event_index": index,
                    "event_count": len(events),
                }

            body = dict(event)

            body.pop(
                "event_sha256",
                None,
            )

            calculated_sha = (
                cls._sha256_text(
                    cls._canonical_json(
                        body
                    )
                )
            )

            if (
                calculated_sha
                != recorded_event_sha
            ):
                return {
                    "valid": False,
                    "reason": (
                        "EVENT_HASH_MISMATCH"
                    ),
                    "event_index": index,
                    "event_count": len(events),
                }

            previous_sha = (
                recorded_event_sha
            )

        return {
            "valid": True,
            "reason": (
                "SHADOW_JOURNAL_CHAIN_VALID"
            ),
            "event_count": len(events),
            "last_event_sha256": (
                previous_sha
            ),
        }

    @classmethod
    def append_event(
        cls,
        *,
        path,
        event_type: str,
        position_id: str,
        broker_epoch: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        with cls.exclusive_transaction(
            path
        ):
            return cls._append_event_unlocked(
                path=path,
                event_type=event_type,
                position_id=position_id,
                broker_epoch=broker_epoch,
                payload=payload,
            )

    @classmethod
    def _append_event_unlocked(
        cls,
        *,
        path,
        event_type: str,
        position_id: str,
        broker_epoch: int,
        payload: dict[str, Any],
        pre_write_check: Callable[[], None] | None = None,
    ) -> dict[str, Any]:

        path = Path(path)

        if not event_type:
            raise ValueError(
                "event_type is required"
            )

        if not position_id:
            raise ValueError(
                "position_id is required"
            )

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "payload must be dict"
            )

        existing = cls.verify(
            path
        )

        if not existing["valid"]:
            raise RuntimeError(
                "SHADOW_JOURNAL_INTEGRITY_FAILURE: "
                f"{existing['reason']}"
            )

        previous_sha = (
            existing[
                "last_event_sha256"
            ]
        )

        event_sequence = (
            existing["event_count"]
            + 1
        )

        body = {
            "schema_version": (
                cls.VERSION
            ),
            "event_sequence": (
                event_sequence
            ),
            "event_type": (
                str(event_type)
            ),
            "position_id": (
                str(position_id)
            ),
            "broker_epoch": (
                int(broker_epoch)
            ),
            "previous_event_sha256": (
                previous_sha
            ),
            "payload": payload,
            "audit": {
                "shadow_only": True,
                "real_order_send_allowed": False,
                "order_send_called": False,
                "order_check_called": False,
                "true_oos_data_accessed": False,
                "true_oos_artifacts_modified": False,
            },
        }

        event_sha = (
            cls._sha256_text(
                cls._canonical_json(
                    body
                )
            )
        )

        event = dict(body)

        event["event_sha256"] = (
            event_sha
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        line = (
            cls._canonical_json(
                event
            )
            + "\n"
        )

        with path.open(
            "a",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            if pre_write_check is not None:
                pre_write_check()
            handle.write(
                line
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )

        verified = cls.verify(
            path
        )

        if not verified["valid"]:
            raise RuntimeError(
                "POST_APPEND_JOURNAL_VERIFY_FAILURE"
            )

        if (
            verified["last_event_sha256"]
            != event_sha
        ):
            raise RuntimeError(
                "POST_APPEND_HASH_MISMATCH"
            )

        return event
