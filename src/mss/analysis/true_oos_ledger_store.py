"""Write-once chunked storage for the raw-immutable True-OOS candle ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class TrueOosLedgerStore:
    VERSION = "MSS_SPRINT92H11_TRUE_OOS_LEDGER_STORE_V1"

    FIELDS = (
        "time",
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "spread",
        "real_volume",
    )

    @staticmethod
    def canonical_array(row):
        return [
            int(row["time"]),
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            int(row["tick_volume"]),
            int(row["spread"]),
            int(row["real_volume"]),
        ]

    @classmethod
    def canonical_line(cls, row):
        return (
            json.dumps(
                cls.canonical_array(row),
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        )

    @classmethod
    def record_sha256(cls, row):
        return hashlib.sha256(
            cls.canonical_line(row).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def bytes_sha256(payload):
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def write_chunk(cls, path, rows):
        path = Path(path)

        if path.exists():
            raise FileExistsError(
                f"write-once chunk already exists: {path}"
            )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        lines = [
            cls.canonical_line(row)
            for row in rows
        ]

        payload = "".join(lines).encode("utf-8")

        temporary = path.with_name(
            path.name + ".tmp"
        )

        if temporary.exists():
            raise FileExistsError(
                f"stale temporary file exists: {temporary}"
            )

        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()

            temporary.replace(path)

        finally:
            if temporary.exists():
                temporary.unlink()

        return {
            "row_count": len(rows),
            "file_sha256": cls.bytes_sha256(payload),
            "file_size_bytes": len(payload),
            "record_sha256": [
                cls.record_sha256(row)
                for row in rows
            ],
        }

    @staticmethod
    def write_manifest(path, payload):
        path = Path(path)

        if path.exists():
            raise FileExistsError(
                f"write-once manifest already exists: {path}"
            )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        text = (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )

        temporary = path.with_name(
            path.name + ".tmp"
        )

        if temporary.exists():
            raise FileExistsError(
                f"stale temporary manifest exists: {temporary}"
            )

        try:
            with temporary.open(
                "x",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(text)
                handle.flush()

            temporary.replace(path)

        finally:
            if temporary.exists():
                temporary.unlink()

        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()
