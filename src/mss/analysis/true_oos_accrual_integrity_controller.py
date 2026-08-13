from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AccrualIntegrityResult:
    status: str
    details: dict[str, Any]


class TrueOosAccrualIntegrityController:
    """
    Sprint 92H.13.4
    True OOS Accrual Reliability and Integrity Controller

    Responsibilities:
    - Detect already-created/uncommitted next-sequence artifacts.
    - Validate manifest/chunk chain continuity.
    - Detect ledger timestamp gaps without fabricating candles.
    - Classify no-new-data as a healthy no-write state.
    - Preserve append-only / write-once invariants.
    """

    VERSION = "MSS_SPRINT_92H13_4_V1"

    STATUS_READY = "READY_FOR_ACCRUAL"
    STATUS_NO_NEW_DATA = "NO_NEW_COMPLETED_TRUE_OOS_CANDLES"
    STATUS_UNCOMMITTED_SEQUENCE = "UNCOMMITTED_SEQUENCE_PRESENT"
    STATUS_LEDGER_INTEGRITY_FAILURE = "LEDGER_INTEGRITY_FAILURE"
    STATUS_BROKER_SOURCE_GAP = "BROKER_SOURCE_HISTORY_GAP_DETECTED"
    STATUS_TIME_AUTHORITY_BLOCKED = "TIME_AUTHORITY_BLOCKED_NO_WRITE"

    @staticmethod
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def latest_manifest(
        ledger_root: Path,
    ) -> tuple[Path, dict[str, Any]]:
        manifests = sorted(
            ledger_root.glob("manifest_*.json"),
            key=lambda p: int(p.stem.split("_")[-1]),
        )

        if not manifests:
            raise RuntimeError("NO_TRUE_OOS_MANIFEST_FOUND")

        latest_path = manifests[-1]
        latest = TrueOosAccrualIntegrityController._load_json(latest_path)

        return latest_path, latest

    @staticmethod
    def expected_next_sequence(latest_manifest: dict[str, Any]) -> int:
        return int(latest_manifest["manifest_sequence"]) + 1

    @classmethod
    def detect_uncommitted_sequence(
        cls,
        *,
        ledger_root: Path,
        report_root: Path,
        expected_sequence: int,
    ) -> AccrualIntegrityResult:
        seq = f"{expected_sequence:06d}"

        chunk = ledger_root / "chunks" / f"chunk_{seq}.jsonl"
        manifest = ledger_root / f"manifest_{seq}.json"
        report = (
            report_root
            / f"MSS_Sprint92H13_3_Gated_True_OOS_Accrual_{seq}.json"
        )

        existing = {
            "chunk": chunk.exists(),
            "manifest": manifest.exists(),
            "report": report.exists(),
        }

        if any(existing.values()):
            return AccrualIntegrityResult(
                status=cls.STATUS_UNCOMMITTED_SEQUENCE,
                details={
                    "sequence": expected_sequence,
                    "existing_artifacts": existing,
                    "chunk_path": str(chunk),
                    "manifest_path": str(manifest),
                    "report_path": str(report),
                    "ledger_write_allowed": False,
                },
            )

        return AccrualIntegrityResult(
            status=cls.STATUS_READY,
            details={
                "sequence": expected_sequence,
                "existing_artifacts": existing,
                "ledger_write_allowed": True,
            },
        )

    @classmethod
    def verify_manifest_chain(
        cls,
        *,
        ledger_root: Path,
    ) -> AccrualIntegrityResult:
        manifest_paths = sorted(
            ledger_root.glob("manifest_*.json"),
            key=lambda p: int(p.stem.split("_")[-1]),
        )

        if not manifest_paths:
            return AccrualIntegrityResult(
                status=cls.STATUS_LEDGER_INTEGRITY_FAILURE,
                details={
                    "reason": "NO_MANIFESTS_FOUND",
                    "ledger_write_allowed": False,
                },
            )

        previous_sha: str | None = None
        previous_sequence: int | None = None

        for path in manifest_paths:
            manifest = cls._load_json(path)
            sequence = int(manifest["manifest_sequence"])

            if previous_sequence is None:
                if sequence != 0:
                    return AccrualIntegrityResult(
                        status=cls.STATUS_LEDGER_INTEGRITY_FAILURE,
                        details={
                            "reason": "GENESIS_SEQUENCE_NOT_ZERO",
                            "path": str(path),
                            "sequence": sequence,
                            "ledger_write_allowed": False,
                        },
                    )

                if manifest.get("previous_manifest_sha256") is not None:
                    return AccrualIntegrityResult(
                        status=cls.STATUS_LEDGER_INTEGRITY_FAILURE,
                        details={
                            "reason": "GENESIS_PREVIOUS_SHA_NOT_NULL",
                            "path": str(path),
                            "ledger_write_allowed": False,
                        },
                    )

            else:
                if sequence != previous_sequence + 1:
                    return AccrualIntegrityResult(
                        status=cls.STATUS_LEDGER_INTEGRITY_FAILURE,
                        details={
                            "reason": "MANIFEST_SEQUENCE_GAP",
                            "path": str(path),
                            "expected_sequence": previous_sequence + 1,
                            "actual_sequence": sequence,
                            "ledger_write_allowed": False,
                        },
                    )

                if manifest.get("previous_manifest_sha256") != previous_sha:
                    return AccrualIntegrityResult(
                        status=cls.STATUS_LEDGER_INTEGRITY_FAILURE,
                        details={
                            "reason": "PREVIOUS_MANIFEST_SHA_MISMATCH",
                            "path": str(path),
                            "expected_previous_sha256": previous_sha,
                            "actual_previous_sha256": manifest.get(
                                "previous_manifest_sha256"
                            ),
                            "ledger_write_allowed": False,
                        },
                    )

            previous_sha = cls.sha256_file(path)
            previous_sequence = sequence

        return AccrualIntegrityResult(
            status=cls.STATUS_READY,
            details={
                "manifest_count": len(manifest_paths),
                "latest_sequence": previous_sequence,
                "latest_manifest_sha256": previous_sha,
                "ledger_write_allowed": True,
            },
        )

    @classmethod
    def scan_ledger_gaps(
        cls,
        *,
        ledger_root: Path,
        timeframe_seconds: int = 900,
    ) -> AccrualIntegrityResult:
        chunk_paths = sorted(
            (ledger_root / "chunks").glob("chunk_*.jsonl"),
            key=lambda p: int(p.stem.split("_")[-1]),
        )

        timestamps: list[int] = []

        for path in chunk_paths:
            with path.open("r", encoding="utf-8") as f:
                for line_number, line in enumerate(f, start=1):
                    raw = line.strip()
                    if not raw:
                        continue

                    row = json.loads(raw)

                    if not isinstance(row, list) or len(row) < 1:
                        return AccrualIntegrityResult(
                            status=cls.STATUS_LEDGER_INTEGRITY_FAILURE,
                            details={
                                "reason": "INVALID_CANONICAL_LEDGER_ROW",
                                "path": str(path),
                                "line_number": line_number,
                                "ledger_write_allowed": False,
                            },
                        )

                    timestamps.append(int(row[0]))

        if not timestamps:
            return AccrualIntegrityResult(
                status=cls.STATUS_READY,
                details={
                    "row_count": 0,
                    "gap_count": 0,
                    "gaps": [],
                    "ledger_write_allowed": True,
                },
            )

        if timestamps != sorted(timestamps):
            return AccrualIntegrityResult(
                status=cls.STATUS_LEDGER_INTEGRITY_FAILURE,
                details={
                    "reason": "NON_MONOTONIC_LEDGER_TIMESTAMPS",
                    "ledger_write_allowed": False,
                },
            )

        if len(timestamps) != len(set(timestamps)):
            return AccrualIntegrityResult(
                status=cls.STATUS_LEDGER_INTEGRITY_FAILURE,
                details={
                    "reason": "DUPLICATE_LEDGER_TIMESTAMPS",
                    "ledger_write_allowed": False,
                },
            )

        gaps: list[dict[str, int]] = []

        for previous, current in zip(timestamps, timestamps[1:]):
            delta = current - previous

            if delta > timeframe_seconds:
                missing_count = (delta // timeframe_seconds) - 1

                gaps.append(
                    {
                        "previous_epoch": previous,
                        "current_epoch": current,
                        "delta_seconds": delta,
                        "missing_slot_count": missing_count,
                    }
                )

        if gaps:
            return AccrualIntegrityResult(
                status=cls.STATUS_BROKER_SOURCE_GAP,
                details={
                    "row_count": len(timestamps),
                    "gap_count": len(gaps),
                    "gaps": gaps,
                    "synthetic_backfill_allowed": False,
                    "ledger_rewrite_required": False,
                    "ledger_write_allowed": True,
                },
            )

        return AccrualIntegrityResult(
            status=cls.STATUS_READY,
            details={
                "row_count": len(timestamps),
                "gap_count": 0,
                "gaps": [],
                "ledger_write_allowed": True,
            },
        )

    @classmethod
    def classify_time_authority_gate(
        cls,
        *,
        gate: dict[str, Any],
    ) -> AccrualIntegrityResult:
        confirmed = bool(
            gate.get("gate_confirmed", False)
        )

        authority_status = (
            gate.get("authority", {})
            .get("time_authority", {})
            .get("status")
        )

        sync_status = (
            gate.get("sync", {})
            .get("status")
        )

        if not confirmed:
            return AccrualIntegrityResult(
                status=cls.STATUS_TIME_AUTHORITY_BLOCKED,
                details={
                    "gate_confirmed": False,
                    "authority_status": authority_status,
                    "sync_status": sync_status,
                    "ledger_write_allowed": False,
                    "manifest_write_allowed": False,
                    "chunk_write_allowed": False,
                    "report_write_allowed": False,
                    "replay_run": False,
                    "outcomes_analyzed": False,
                    "orders_sent": False,
                },
            )

        return AccrualIntegrityResult(
            status=cls.STATUS_READY,
            details={
                "gate_confirmed": True,
                "authority_status": authority_status,
                "sync_status": sync_status,
                "ledger_write_allowed": True,
            },
        )

    @classmethod
    def classify_no_new_data(
        cls,
        *,
        previous_row_count: int,
    ) -> AccrualIntegrityResult:
        return AccrualIntegrityResult(
            status=cls.STATUS_NO_NEW_DATA,
            details={
                "previous_row_count": int(previous_row_count),
                "rows_appended": 0,
                "ledger_write_performed": False,
                "manifest_write_performed": False,
                "chunk_write_performed": False,
                "report_write_required": False,
                "replay_run": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },
        )
