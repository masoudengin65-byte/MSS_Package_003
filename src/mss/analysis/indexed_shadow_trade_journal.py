"""Derived SQLite index for an authoritative ShadowTradeJournal JSONL chain.

JSONL remains the evidence.  SQLite is disposable acceleration: startup and any
unexpected JSONL fingerprint change trigger a complete frozen-journal verify and
index rebuild.  Appends use the exact frozen schema/canonicalization/hash rules,
fsync JSONL first, then commit the derived row.  A crash between those writes is
reconciled from JSONL on the next construction.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterator, Mapping

from mss.analysis.shadow_trade_journal import ShadowTradeJournal


class IndexedShadowTradeJournal:
    """One-path, one-process indexed view under an external runner lease."""

    VERSION = ShadowTradeJournal.VERSION
    GENESIS_SHA256 = ShadowTradeJournal.GENESIS_SHA256

    def __init__(self, path: Path):
        self.path = Path(path)
        self.index_path = self.index_path_for(self.path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.index_path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA temp_store=MEMORY")
        self._connection.execute("PRAGMA cache_size=-4096")
        self._create_schema()
        self._fingerprint: tuple[int, int, int] | None = None
        self._rebuild_from_authority()

    @staticmethod
    def index_path_for(path: Path) -> Path:
        path = Path(path)
        return path.with_name(path.name + ".index.sqlite3")

    @staticmethod
    def _canonical_json(payload: dict[str, Any]) -> str:
        return ShadowTradeJournal._canonical_json(payload)

    @staticmethod
    def _sha256_text(text: str) -> str:
        return ShadowTradeJournal._sha256_text(text)

    @contextmanager
    def exclusive_transaction(self, path: Path) -> Iterator[None]:
        self._require_path(path)
        with ShadowTradeJournal.exclusive_transaction(self.path):
            yield

    def _require_path(self, path: Path) -> None:
        if Path(path).resolve() != self.path.resolve():
            raise RuntimeError("indexed evidence backend is bound to one journal path")

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                file_size INTEGER NOT NULL,
                file_mtime_ns INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                last_event_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_sequence INTEGER PRIMARY KEY,
                event_id TEXT,
                manifest_sha256 TEXT,
                pair_symbol TEXT,
                pair_open_utc TEXT,
                phase TEXT,
                baseline_actual INTEGER,
                candidate_actual INTEGER,
                authority_json TEXT,
                event_sha256 TEXT NOT NULL,
                event_json TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS events_event_id
                ON events(event_id) WHERE event_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS events_phase_key
                ON events(manifest_sha256, pair_symbol, pair_open_utc, phase)
                WHERE manifest_sha256 IS NOT NULL;
            CREATE INDEX IF NOT EXISTS events_manifest_phase
                ON events(manifest_sha256, phase);
            """
        )

    def _file_fingerprint(self) -> tuple[int, int, int]:
        if not self.path.exists():
            return (0, 0, 0)
        stat = self.path.stat()
        return (int(stat.st_size), int(stat.st_mtime_ns), int(getattr(stat, "st_ino", 0)))

    @staticmethod
    def _columns(event: Mapping[str, Any]) -> tuple[Any, ...]:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        pair = payload.get("pair_key")
        pair_symbol = pair[0] if isinstance(pair, list) and len(pair) == 2 else None
        pair_open = pair[1] if isinstance(pair, list) and len(pair) == 2 else None
        branches = payload.get("branches")
        baseline_actual = candidate_actual = None
        if isinstance(branches, dict):
            baseline_actual = int(bool(branches.get("baseline", {}).get("is_actual_trade")))
            candidate_actual = int(bool(branches.get("candidate", {}).get("is_actual_trade")))
        authority = payload.get("global_time_authority")
        authority_json = (
            ShadowTradeJournal._canonical_json(authority)
            if isinstance(authority, dict)
            else None
        )
        manifest = payload.get("activation_manifest_sha256")
        event_id = payload.get("sprint93_2b_event_id")
        phase = payload.get("phase")
        if manifest is not None:
            if not all(isinstance(value, str) and value for value in (
                manifest, event_id, pair_symbol, pair_open, phase,
            )):
                raise RuntimeError("indexed evidence identity is malformed")
            identity = {
                "manifest_sha256": manifest,
                "pair_key": [pair_symbol, pair_open],
                "phase": phase,
            }
            expected = hashlib.sha256(
                (json.dumps(
                    identity, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False,
                ) + "\n").encode("utf-8")
            ).hexdigest()
            if event_id != expected or event.get("position_id") != event_id:
                raise RuntimeError("indexed evidence identity mismatch")
        return (
            int(event["event_sequence"]), event_id,
            manifest, pair_symbol, pair_open,
            phase, baseline_actual, candidate_actual, authority_json,
            str(event["event_sha256"]), ShadowTradeJournal._canonical_json(dict(event)),
        )

    def _insert_event(self, event: Mapping[str, Any]) -> None:
        self._connection.execute(
            """INSERT INTO events (
                event_sequence,event_id,manifest_sha256,pair_symbol,pair_open_utc,
                phase,baseline_actual,candidate_actual,authority_json,event_sha256,event_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            self._columns(event),
        )

    def _set_metadata(self, *, event_count: int, last_event_sha256: str) -> None:
        fingerprint = self._file_fingerprint()
        self._connection.execute(
            """INSERT INTO metadata(singleton,file_size,file_mtime_ns,event_count,last_event_sha256)
               VALUES(1,?,?,?,?) ON CONFLICT(singleton) DO UPDATE SET
               file_size=excluded.file_size,file_mtime_ns=excluded.file_mtime_ns,
               event_count=excluded.event_count,last_event_sha256=excluded.last_event_sha256""",
            (fingerprint[0], fingerprint[1], int(event_count), last_event_sha256),
        )
        self._fingerprint = fingerprint

    def _rebuild_from_authority(self) -> dict[str, Any]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._connection.execute("DELETE FROM events")
            self._connection.execute("DELETE FROM metadata")
            previous = self.GENESIS_SHA256
            count = 0
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as handle:
                    for count, line in enumerate(handle, start=1):
                        line = line.rstrip("\n")
                        if not line:
                            raise RuntimeError(f"EMPTY_JOURNAL_LINE:{count}")
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise RuntimeError(f"INVALID_JOURNAL_JSON:{count}") from exc
                        if event.get("previous_event_sha256") != previous:
                            raise RuntimeError(f"PREVIOUS_HASH_MISMATCH:{count}")
                        recorded = event.get("event_sha256")
                        body = dict(event)
                        body.pop("event_sha256", None)
                        calculated = self._sha256_text(self._canonical_json(body))
                        if calculated != recorded:
                            raise RuntimeError(f"EVENT_HASH_MISMATCH:{count}")
                        self._insert_event(event)
                        previous = str(recorded)
            self._set_metadata(
                event_count=count,
                last_event_sha256=previous,
            )
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")
        return {
            "valid": True, "reason": "SHADOW_JOURNAL_CHAIN_VALID",
            "event_count": count, "last_event_sha256": previous,
        }

    def _ensure_current(self) -> None:
        if self._fingerprint != self._file_fingerprint():
            self._rebuild_from_authority()

    def verify(self, path: Path) -> dict[str, Any]:
        self._require_path(path)
        self._ensure_current()
        row = self._connection.execute(
            "SELECT event_count,last_event_sha256 FROM metadata WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise RuntimeError("indexed evidence metadata is missing")
        return {
            "valid": True,
            "reason": "SHADOW_JOURNAL_CHAIN_VALID_INDEXED",
            "event_count": int(row[0]),
            "last_event_sha256": str(row[1]),
        }

    def full_verify(self) -> dict[str, Any]:
        return self._rebuild_from_authority()

    def _validated_event(self, raw: str) -> dict[str, Any]:
        event = json.loads(raw)
        recorded = event.get("event_sha256")
        body = dict(event)
        body.pop("event_sha256", None)
        if self._sha256_text(self._canonical_json(body)) != recorded:
            raise RuntimeError("derived index event differs from its authoritative hash")
        return event

    def _read_events(self, path: Path) -> list[dict[str, Any]]:
        self._require_path(path)
        self._ensure_current()
        return [self._validated_event(row[0]) for row in self._connection.execute(
            "SELECT event_json FROM events ORDER BY event_sequence"
        )]

    def find_event(self, event_id: str) -> dict[str, Any] | None:
        self._ensure_current()
        row = self._connection.execute(
            "SELECT event_json FROM events WHERE event_id=?", (event_id,)
        ).fetchone()
        return self._validated_event(row[0]) if row is not None else None

    def phase_event(
        self, manifest_sha256: str, pair_key: tuple[str, str], phase: str
    ) -> dict[str, Any] | None:
        self._ensure_current()
        row = self._connection.execute(
            """SELECT event_json FROM events WHERE manifest_sha256=?
               AND pair_symbol=? AND pair_open_utc=? AND phase=?""",
            (manifest_sha256, pair_key[0], pair_key[1], phase),
        ).fetchone()
        event = self._validated_event(row[0]) if row is not None else None
        if event is not None:
            payload = event.get("payload", {})
            if (payload.get("activation_manifest_sha256") != manifest_sha256
                    or payload.get("pair_key") != list(pair_key)
                    or payload.get("phase") != phase):
                raise RuntimeError("derived index phase lookup is inconsistent")
        return event

    def phase_keys(self, manifest_sha256: str) -> set[tuple[tuple[str, str], str]]:
        return set(self.iter_phase_keys(manifest_sha256))

    def iter_phase_keys(self, manifest_sha256: str):
        self._ensure_current()
        for row in self._connection.execute(
            """SELECT pair_symbol,pair_open_utc,phase,event_id FROM events
               WHERE manifest_sha256=?""", (manifest_sha256,)
        ):
            if not all(isinstance(value, str) and value for value in row):
                raise RuntimeError("indexed evidence identity is malformed")
            pair, phase, event_id = (row[0], row[1]), row[2], row[3]
            identity = {
                "manifest_sha256": manifest_sha256,
                "pair_key": list(pair),
                "phase": phase,
            }
            expected = hashlib.sha256(
                (json.dumps(
                    identity, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False,
                ) + "\n").encode("utf-8")
            ).hexdigest()
            if event_id != expected:
                raise RuntimeError("indexed evidence identity mismatch")
            yield pair, phase

    def phase_count(self, manifest_sha256: str) -> int:
        self._ensure_current()
        return int(self._connection.execute(
            "SELECT count(*) FROM events WHERE manifest_sha256=?",
            (manifest_sha256,),
        ).fetchone()[0])

    def has_phase(
        self, manifest_sha256: str, pair_key: tuple[str, str], phase: str
    ) -> bool:
        self._ensure_current()
        return self._connection.execute(
            """SELECT 1 FROM events WHERE manifest_sha256=? AND pair_symbol=?
               AND pair_open_utc=? AND phase=? LIMIT 1""",
            (manifest_sha256, pair_key[0], pair_key[1], phase),
        ).fetchone() is not None

    def recovery_sets(self, manifest_sha256: str) -> dict[str, set[tuple[str, str]]]:
        self._ensure_current()
        def pairs(phase: str) -> set[tuple[str, str]]:
            return {(str(row[0]), str(row[1])) for row in self._connection.execute(
                """SELECT pair_symbol,pair_open_utc FROM events
                   WHERE manifest_sha256=? AND phase=?""",
                (manifest_sha256, phase),
            )}
        decisions, entries, settlements = (
            pairs("decision"), pairs("entry"), pairs("settlement")
        )
        outstanding = self.outstanding_branches(manifest_sha256)
        return {
            "decisions": decisions, "entries": entries, "settlements": settlements,
            "open_pairs": {pair for pair, _branch in outstanding},
        }

    def outstanding_branches(
        self, manifest_sha256: str
    ) -> tuple[tuple[tuple[str, str], str], ...]:
        self._ensure_current()
        result = []
        for branch, column in (("baseline", "baseline_actual"),
                               ("candidate", "candidate_actual")):
            terminal = "terminal_" + branch
            rows = self._connection.execute(
                f"""SELECT e.pair_symbol,e.pair_open_utc FROM events e
                    WHERE e.manifest_sha256=? AND e.phase='entry' AND e.{column}=1
                    AND NOT EXISTS (SELECT 1 FROM events t WHERE
                        t.manifest_sha256=e.manifest_sha256
                        AND t.pair_symbol=e.pair_symbol
                        AND t.pair_open_utc=e.pair_open_utc AND t.phase=?)""",
                (manifest_sha256, terminal),
            )
            result.extend((((str(row[0]), str(row[1])), branch) for row in rows))
        return tuple(sorted(result))

    def ready_settlement_pairs(
        self, manifest_sha256: str
    ) -> tuple[tuple[str, str], ...]:
        self._ensure_current()
        rows = self._connection.execute(
            """SELECT e.pair_symbol,e.pair_open_utc FROM events e
               WHERE e.manifest_sha256=? AND e.phase='entry'
               AND (e.baseline_actual=1 OR e.candidate_actual=1)
               AND (e.baseline_actual=0 OR EXISTS (SELECT 1 FROM events b WHERE
                    b.manifest_sha256=e.manifest_sha256
                    AND b.pair_symbol=e.pair_symbol AND b.pair_open_utc=e.pair_open_utc
                    AND b.phase='terminal_baseline'))
               AND (e.candidate_actual=0 OR EXISTS (SELECT 1 FROM events c WHERE
                    c.manifest_sha256=e.manifest_sha256
                    AND c.pair_symbol=e.pair_symbol AND c.pair_open_utc=e.pair_open_utc
                    AND c.phase='terminal_candidate'))
               AND NOT EXISTS (SELECT 1 FROM events s WHERE
                    s.manifest_sha256=e.manifest_sha256
                    AND s.pair_symbol=e.pair_symbol AND s.pair_open_utc=e.pair_open_utc
                    AND s.phase='settlement')""",
            (manifest_sha256,),
        )
        return tuple(sorted((str(row[0]), str(row[1])) for row in rows))

    def entry_actual_flags(
        self, manifest_sha256: str, pair_key: tuple[str, str]
    ) -> tuple[bool, bool]:
        self._ensure_current()
        row = self._connection.execute(
            """SELECT event_json FROM events
               WHERE manifest_sha256=? AND pair_symbol=? AND pair_open_utc=? AND phase='entry'""",
            (manifest_sha256, pair_key[0], pair_key[1]),
        ).fetchone()
        if row is None:
            raise RuntimeError("indexed entry flags are missing")
        event = self._validated_event(row[0])
        branches = event.get("payload", {}).get("branches", {})
        try:
            return tuple(bool(branches[name]["is_actual_trade"])
                         for name in ("baseline", "candidate"))
        except (KeyError, TypeError) as exc:
            raise RuntimeError("indexed entry flags are malformed") from exc

    def latest_authority(self, manifest_sha256: str) -> dict[str, Any] | None:
        self._ensure_current()
        row = self._connection.execute(
            """SELECT event_json FROM events WHERE manifest_sha256=?
               AND authority_json IS NOT NULL ORDER BY event_sequence DESC LIMIT 1""",
            (manifest_sha256,),
        ).fetchone()
        if row is None:
            return None
        event = self._validated_event(row[0])
        authority = event.get("payload", {}).get("global_time_authority")
        if not isinstance(authority, dict):
            raise RuntimeError("indexed authority lookup is malformed")
        return authority

    def _append_event_unlocked(
        self, *, path: Path, event_type: str, position_id: str, broker_epoch: int,
        payload: dict[str, Any], pre_write_check: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        self._require_path(path)
        if not event_type or not position_id:
            raise ValueError("event_type and position_id are required")
        if not isinstance(payload, dict):
            raise TypeError("payload must be dict")
        current = self.verify(path)
        body = {
            "schema_version": self.VERSION,
            "event_sequence": int(current["event_count"]) + 1,
            "event_type": str(event_type),
            "position_id": str(position_id),
            "broker_epoch": int(broker_epoch),
            "previous_event_sha256": current["last_event_sha256"],
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
        event = dict(body)
        event["event_sha256"] = self._sha256_text(self._canonical_json(body))
        line = self._canonical_json(event) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            if pre_write_check is not None:
                pre_write_check()
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._insert_event(event)
            self._set_metadata(
                event_count=event["event_sequence"],
                last_event_sha256=event["event_sha256"],
            )
        except BaseException:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            # JSONL already committed. Reconcile the derived index before return.
            self._rebuild_from_authority()
            recovered = self.find_event(str(payload.get("sprint93_2b_event_id", "")))
            if recovered != event:
                raise RuntimeError("indexed journal reconciliation failed after append")
        else:
            self._connection.execute("COMMIT")
        return event

    def append_event(
        self, *, path: Path, event_type: str, position_id: str,
        broker_epoch: int, payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self.exclusive_transaction(path):
            return self._append_event_unlocked(
                path=path, event_type=event_type, position_id=position_id,
                broker_epoch=broker_epoch, payload=payload,
            )

    def close(self) -> None:
        self._connection.close()
