"""Reusable incremental append-only accrual for the immutable True-OOS ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.analysis.true_oos_ledger_store import TrueOosLedgerStore


class TrueOosIncrementalAccrual:
    VERSION = "MSS_SPRINT92H13_INCREMENTAL_APPEND_ONLY_ACCRUAL_ENGINE_V1"

    SYMBOL = "USDJPY"
    TIMEFRAME = "M15"
    TIMEFRAME_SECONDS = 900
    REQUIRED_CANDLES = 10_000

    @staticmethod
    def epoch(row):
        return int(HistoricalDepthAudit._value(row, "time"))

    @staticmethod
    def decode_chunk(path):
        rows = []

        with Path(path).open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line in handle:
                values = json.loads(line)

                if not isinstance(values, list) or len(values) != 8:
                    raise RuntimeError(
                        f"invalid immutable ledger row: {path}"
                    )

                rows.append(
                    {
                        "time": int(values[0]),
                        "open": float(values[1]),
                        "high": float(values[2]),
                        "low": float(values[3]),
                        "close": float(values[4]),
                        "tick_volume": int(values[5]),
                        "spread": int(values[6]),
                        "real_volume": int(values[7]),
                    }
                )

        return rows

    @classmethod
    def verify_existing_ledger(
        cls,
        root,
        manifest,
    ):
        root = Path(root)

        if manifest["schema_version"] != (
            "MSS_TRUE_OOS_LEDGER_MANIFEST_V1"
        ):
            raise RuntimeError("unexpected ledger manifest schema")

        if manifest["execution_id"] != (
            "MSS_92H9_USDJPY_RAW_IMMUTABLE_TRUE_OOS_V2"
        ):
            raise RuntimeError("unexpected ledger execution id")

        chunks = manifest["chunks"]

        if len(chunks) != manifest["chunk_count"]:
            raise RuntimeError("chunk count reconciliation failure")

        all_rows = []
        chunk_audits = []

        for expected_sequence, chunk in enumerate(
            chunks,
            start=1,
        ):
            if chunk["sequence"] != expected_sequence:
                raise RuntimeError(
                    "non-contiguous chunk sequence"
                )

            path = root / chunk["path"]

            if not path.is_file():
                raise RuntimeError(
                    f"frozen chunk missing: {path}"
                )

            actual_file_sha = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()

            if actual_file_sha != chunk["file_sha256"]:
                raise RuntimeError(
                    f"frozen chunk hash failure: {path}"
                )

            rows = cls.decode_chunk(path)

            if len(rows) != chunk["row_count"]:
                raise RuntimeError(
                    f"frozen chunk row-count failure: {path}"
                )

            if not rows:
                raise RuntimeError(
                    f"empty historical chunk: {path}"
                )

            if cls.epoch(rows[0]) != chunk["first_epoch"]:
                raise RuntimeError(
                    f"frozen chunk first epoch failure: {path}"
                )

            if cls.epoch(rows[-1]) != chunk["last_epoch"]:
                raise RuntimeError(
                    f"frozen chunk last epoch failure: {path}"
                )

            actual_record_hashes = [
                TrueOosLedgerStore.record_sha256(row)
                for row in rows
            ]

            if actual_record_hashes != chunk["record_sha256"]:
                raise RuntimeError(
                    f"record-level hash failure: {path}"
                )

            all_rows.extend(rows)

            chunk_audits.append(
                {
                    "sequence": chunk["sequence"],
                    "path": chunk["path"],
                    "row_count": len(rows),
                    "file_sha256": actual_file_sha,
                    "verified": True,
                }
            )

        times = [
            cls.epoch(row)
            for row in all_rows
        ]

        if times != sorted(times):
            raise RuntimeError(
                "existing ledger is not chronological"
            )

        if len(times) != len(set(times)):
            raise RuntimeError(
                "existing ledger contains duplicate timestamps"
            )

        if len(all_rows) != manifest["row_count"]:
            raise RuntimeError(
                "ledger row count reconciliation failure"
            )

        if all_rows:
            if (
                cls.epoch(all_rows[0])
                != manifest["first_candle_open_epoch"]
            ):
                raise RuntimeError(
                    "ledger first epoch reconciliation failure"
                )

            if (
                cls.epoch(all_rows[-1])
                != manifest["last_candle_open_epoch"]
            ):
                raise RuntimeError(
                    "ledger last epoch reconciliation failure"
                )

        aggregate_payload = b"".join(
            TrueOosLedgerStore.canonical_line(row).encode("utf-8")
            for row in all_rows
        )

        aggregate_sha = hashlib.sha256(
            aggregate_payload
        ).hexdigest()

        if (
            aggregate_sha
            != manifest["aggregate_ledger_sha256"]
        ):
            raise RuntimeError(
                "aggregate immutable ledger hash failure"
            )

        return {
            "rows": all_rows,
            "chunk_audits": chunk_audits,
            "aggregate_sha256": aggregate_sha,
            "verified": True,
        }

    @classmethod
    def completed_broker_rows(
        cls,
        rates,
        current_bar_epoch,
    ):
        completed = [
            row
            for row in rates
            if (
                cls.epoch(row)
                + cls.TIMEFRAME_SECONDS
                <= int(current_bar_epoch)
            )
        ]

        completed = sorted(
            completed,
            key=cls.epoch,
        )

        times = [
            cls.epoch(row)
            for row in completed
        ]

        if len(times) != len(set(times)):
            raise RuntimeError(
                "broker retrieval contains duplicate timestamps"
            )

        return completed

    @classmethod
    def broker_drift_audit(
        cls,
        frozen_rows,
        broker_completed_rows,
    ):
        frozen_by_time = {
            cls.epoch(row): row
            for row in frozen_rows
        }

        broker_by_time = {
            cls.epoch(row): row
            for row in broker_completed_rows
        }

        evidence = []

        fields = (
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "spread",
            "real_volume",
        )

        overlap = sorted(
            set(frozen_by_time)
            & set(broker_by_time)
        )

        for timestamp in overlap:
            frozen = frozen_by_time[timestamp]
            broker = broker_by_time[timestamp]

            changed = []

            for field in fields:
                if frozen[field] != broker[field]:
                    changed.append(
                        {
                            "field": field,
                            "frozen_value": frozen[field],
                            "broker_value": broker[field],
                        }
                    )

            if changed:
                evidence.append(
                    {
                        "time": timestamp,
                        "changed_fields": changed,
                        "frozen_record_sha256": (
                            TrueOosLedgerStore.record_sha256(
                                frozen
                            )
                        ),
                        "current_broker_record_sha256": (
                            TrueOosLedgerStore.record_sha256(
                                broker
                            )
                        ),
                    }
                )

        return {
            "overlap_timestamp_count": len(overlap),
            "drifted_timestamp_count": len(evidence),
            "drift_detected": bool(evidence),
            "evidence": evidence,
            "frozen_rows_modified": False,
        }

    @classmethod
    def build(
        cls,
        manifest,
        manifest_sha256,
        ledger_audit,
        broker_rates,
        current_bar_epoch,
        chunk_relative_path,
    ):
        if not ledger_audit["verified"]:
            raise RuntimeError(
                "existing immutable ledger not verified"
            )

        frozen_rows = ledger_audit["rows"]

        if not frozen_rows:
            raise RuntimeError(
                "H13 requires an existing non-empty ledger"
            )

        completed = cls.completed_broker_rows(
            broker_rates,
            current_bar_epoch,
        )

        drift = cls.broker_drift_audit(
            frozen_rows,
            completed,
        )

        last_frozen_epoch = int(
            manifest["last_candle_open_epoch"]
        )

        new_rows = [
            row
            for row in completed
            if cls.epoch(row) > last_frozen_epoch
        ]

        if not new_rows:
            raise RuntimeError(
                "NO_NEW_COMPLETED_TRUE_OOS_CANDLES_AVAILABLE"
            )

        new_times = [
            cls.epoch(row)
            for row in new_rows
        ]

        if new_times != sorted(new_times):
            raise RuntimeError(
                "new rows are not chronological"
            )

        if len(new_times) != len(set(new_times)):
            raise RuntimeError(
                "new rows contain duplicate timestamps"
            )

        integrity = HistoricalDepthAudit.integrity(
            new_rows,
            cls.TIMEFRAME,
            int(current_bar_epoch),
        )

        integrity_pass = (
            integrity["strictly_increasing_timestamps"]
            and integrity["duplicate_timestamp_count"] == 0
            and integrity["invalid_ohlc_count"] == 0
            and integrity["nonfinite_price_count"] == 0
            and integrity["negative_spread_count"] == 0
            and integrity["negative_volume_count"] == 0
            and integrity["future_candle_count"] == 0
        )

        if not integrity_pass:
            raise RuntimeError(
                "new broker candles failed integrity"
            )

        next_sequence = (
            int(manifest["manifest_sequence"])
            + 1
        )

        chunk_payload = b"".join(
            TrueOosLedgerStore.canonical_line(row).encode("utf-8")
            for row in new_rows
        )

        chunk = {
            "sequence": next_sequence,
            "path": chunk_relative_path,
            "row_count": len(new_rows),
            "first_epoch": cls.epoch(new_rows[0]),
            "last_epoch": cls.epoch(new_rows[-1]),
            "first_open_broker_time_label": (
                HistoricalDepthAudit._iso(
                    cls.epoch(new_rows[0])
                )
            ),
            "last_open_broker_time_label": (
                HistoricalDepthAudit._iso(
                    cls.epoch(new_rows[-1])
                )
            ),
            "file_sha256": hashlib.sha256(
                chunk_payload
            ).hexdigest(),
            "record_sha256": [
                TrueOosLedgerStore.record_sha256(row)
                for row in new_rows
            ],
        }

        aggregate_rows = (
            frozen_rows
            + new_rows
        )

        aggregate_payload = b"".join(
            TrueOosLedgerStore.canonical_line(row).encode("utf-8")
            for row in aggregate_rows
        )

        aggregate_sha = hashlib.sha256(
            aggregate_payload
        ).hexdigest()

        total_rows = len(aggregate_rows)

        eligibility_status = (
            "ELIGIBLE_FOR_FINAL_SNAPSHOT_GOVERNANCE"
            if total_rows >= cls.REQUIRED_CANDLES
            else "ACCRUAL_IN_PROGRESS"
        )

        next_manifest = {
            "schema_version": (
                "MSS_TRUE_OOS_LEDGER_MANIFEST_V1"
            ),
            "execution_id": manifest["execution_id"],
            "manifest_sequence": next_sequence,
            "previous_manifest_sha256": manifest_sha256,
            "true_oos_boundary": (
                manifest["true_oos_boundary"]
            ),
            "raw_true_oos_boundary_epoch": (
                manifest["raw_true_oos_boundary_epoch"]
            ),
            "time_authority": (
                manifest["time_authority"]
            ),
            "timeframe": manifest["timeframe"],
            "symbol": manifest["symbol"],
            "chunk_count": (
                manifest["chunk_count"] + 1
            ),
            "row_count": total_rows,
            "first_candle_open_epoch": (
                manifest["first_candle_open_epoch"]
            ),
            "last_candle_open_epoch": (
                cls.epoch(new_rows[-1])
            ),
            "chunks": (
                manifest["chunks"] + [chunk]
            ),
            "aggregate_ledger_sha256": (
                aggregate_sha
            ),
            "eligibility_status": eligibility_status,
        }

        return {
            "schema_version": cls.VERSION,
            "mode": (
                "INCREMENTAL_APPEND_ONLY_TRUE_OOS_ACCRUAL_"
                "NO_REPLAY_NO_OUTCOMES"
            ),
            "execution_id": manifest["execution_id"],

            "sequence": {
                "previous_manifest_sequence": (
                    manifest["manifest_sequence"]
                ),
                "new_chunk_sequence": next_sequence,
                "new_manifest_sequence": next_sequence,
            },

            "accrual": {
                "previous_row_count": (
                    manifest["row_count"]
                ),
                "rows_appended": len(new_rows),
                "new_total_row_count": total_rows,
                "previous_last_epoch": (
                    last_frozen_epoch
                ),
                "first_new_epoch": (
                    cls.epoch(new_rows[0])
                ),
                "last_new_epoch": (
                    cls.epoch(new_rows[-1])
                ),
                "remaining_rows": max(
                    0,
                    cls.REQUIRED_CANDLES
                    - total_rows,
                ),
                "eligibility_status": (
                    eligibility_status
                ),
            },

            "existing_ledger_audit": {
                "verified": True,
                "chunk_count": (
                    manifest["chunk_count"]
                ),
                "row_count": (
                    manifest["row_count"]
                ),
                "aggregate_sha256": (
                    ledger_audit[
                        "aggregate_sha256"
                    ]
                ),
                "chunks": (
                    ledger_audit[
                        "chunk_audits"
                    ]
                ),
            },

            "broker_drift_audit": drift,

            "new_rows_integrity": {
                **integrity,
                "pass": integrity_pass,
            },

            "new_chunk": chunk,
            "next_manifest": next_manifest,

            "immutability": {
                "existing_chunks_modified": False,
                "existing_manifest_modified": False,
                "new_chunk_write_once": True,
                "new_manifest_write_once": True,
                "broker_drift_overwrite_allowed": False,
            },

            "audit": {
                "mt5_accessed": True,
                "strategy_replay_run": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },

            "_new_rows": new_rows,
        }
