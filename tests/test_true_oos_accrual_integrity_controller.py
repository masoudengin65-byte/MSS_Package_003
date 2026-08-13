import json
from pathlib import Path

from mss.analysis.true_oos_accrual_integrity_controller import (
    TrueOosAccrualIntegrityController,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def write_chunk(path: Path, rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                + "\n"
            )


def test_detect_uncommitted_sequence(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    reports = tmp_path / "reports"

    (ledger / "chunks").mkdir(parents=True)
    reports.mkdir(parents=True)

    target = ledger / "chunks" / "chunk_000006.jsonl"
    target.write_text("x\n", encoding="utf-8")

    result = (
        TrueOosAccrualIntegrityController.detect_uncommitted_sequence(
            ledger_root=ledger,
            report_root=reports,
            expected_sequence=6,
        )
    )

    assert (
        result.status
        == TrueOosAccrualIntegrityController.STATUS_UNCOMMITTED_SEQUENCE
    )
    assert result.details["ledger_write_allowed"] is False
    assert result.details["existing_artifacts"]["chunk"] is True


def test_manifest_chain_valid(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir(parents=True)

    genesis = ledger / "manifest_000000.json"

    write_json(
        genesis,
        {
            "manifest_sequence": 0,
            "previous_manifest_sha256": None,
        },
    )

    genesis_sha = (
        TrueOosAccrualIntegrityController.sha256_file(genesis)
    )

    manifest1 = ledger / "manifest_000001.json"

    write_json(
        manifest1,
        {
            "manifest_sequence": 1,
            "previous_manifest_sha256": genesis_sha,
        },
    )

    result = (
        TrueOosAccrualIntegrityController.verify_manifest_chain(
            ledger_root=ledger
        )
    )

    assert (
        result.status
        == TrueOosAccrualIntegrityController.STATUS_READY
    )
    assert result.details["manifest_count"] == 2
    assert result.details["latest_sequence"] == 1


def test_manifest_chain_hash_mismatch_blocks_write(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir(parents=True)

    write_json(
        ledger / "manifest_000000.json",
        {
            "manifest_sequence": 0,
            "previous_manifest_sha256": None,
        },
    )

    write_json(
        ledger / "manifest_000001.json",
        {
            "manifest_sequence": 1,
            "previous_manifest_sha256": "bad-sha",
        },
    )

    result = (
        TrueOosAccrualIntegrityController.verify_manifest_chain(
            ledger_root=ledger
        )
    )

    assert (
        result.status
        == TrueOosAccrualIntegrityController.STATUS_LEDGER_INTEGRITY_FAILURE
    )
    assert result.details["ledger_write_allowed"] is False
    assert (
        result.details["reason"]
        == "PREVIOUS_MANIFEST_SHA_MISMATCH"
    )


def test_gap_scan_detects_missing_m15_slot(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger"

    write_chunk(
        ledger / "chunks" / "chunk_000001.jsonl",
        [
            [1000, 1, 1, 1, 1, 1, 1, 1],
            [1900, 1, 1, 1, 1, 1, 1, 1],
            [3700, 1, 1, 1, 1, 1, 1, 1],
        ],
    )

    result = (
        TrueOosAccrualIntegrityController.scan_ledger_gaps(
            ledger_root=ledger,
            timeframe_seconds=900,
        )
    )

    assert (
        result.status
        == TrueOosAccrualIntegrityController.STATUS_BROKER_SOURCE_GAP
    )
    assert result.details["gap_count"] == 1
    assert (
        result.details["gaps"][0]["missing_slot_count"]
        == 1
    )
    assert result.details["synthetic_backfill_allowed"] is False
    assert result.details["ledger_rewrite_required"] is False


def test_duplicate_timestamps_fail_integrity(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger"

    write_chunk(
        ledger / "chunks" / "chunk_000001.jsonl",
        [
            [1000, 1, 1, 1, 1, 1, 1, 1],
            [1900, 1, 1, 1, 1, 1, 1, 1],
            [1900, 1, 1, 1, 1, 1, 1, 1],
        ],
    )

    result = (
        TrueOosAccrualIntegrityController.scan_ledger_gaps(
            ledger_root=ledger,
            timeframe_seconds=900,
        )
    )

    assert (
        result.status
        == TrueOosAccrualIntegrityController.STATUS_LEDGER_INTEGRITY_FAILURE
    )
    assert (
        result.details["reason"]
        == "DUPLICATE_LEDGER_TIMESTAMPS"
    )
    assert result.details["ledger_write_allowed"] is False


def test_no_new_data_is_healthy_no_write() -> None:
    result = (
        TrueOosAccrualIntegrityController.classify_no_new_data(
            previous_row_count=84
        )
    )

    assert (
        result.status
        == TrueOosAccrualIntegrityController.STATUS_NO_NEW_DATA
    )
    assert result.details["previous_row_count"] == 84
    assert result.details["rows_appended"] == 0
    assert result.details["ledger_write_performed"] is False
    assert result.details["manifest_write_performed"] is False
    assert result.details["chunk_write_performed"] is False
    assert result.details["replay_run"] is False
    assert result.details["outcomes_analyzed"] is False
    assert result.details["orders_sent"] is False


def test_time_authority_blocked_is_no_write() -> None:
    gate = {
        "gate_confirmed": False,
        "authority": {
            "time_authority": {
                "status": (
                    "BROKER_TIME_AUTHORITY_STALE_OR_AMBIGUOUS"
                )
            }
        },
        "sync": {
            "status": "MT5_BAR_SYNCHRONIZED"
        },
    }

    result = (
        TrueOosAccrualIntegrityController
        .classify_time_authority_gate(
            gate=gate
        )
    )

    assert (
        result.status
        == TrueOosAccrualIntegrityController
        .STATUS_TIME_AUTHORITY_BLOCKED
    )

    assert result.details["gate_confirmed"] is False
    assert result.details["ledger_write_allowed"] is False
    assert result.details["manifest_write_allowed"] is False
    assert result.details["chunk_write_allowed"] is False
    assert result.details["report_write_allowed"] is False
    assert result.details["replay_run"] is False
    assert result.details["outcomes_analyzed"] is False
    assert result.details["orders_sent"] is False


def test_confirmed_time_authority_allows_prewrite_path() -> None:
    gate = {
        "gate_confirmed": True,
        "authority": {
            "time_authority": {
                "status": "BROKER_TIME_DOMAIN_CONFIRMED"
            }
        },
        "sync": {
            "status": "MT5_BAR_SYNCHRONIZED"
        },
    }

    result = (
        TrueOosAccrualIntegrityController
        .classify_time_authority_gate(
            gate=gate
        )
    )

    assert (
        result.status
        == TrueOosAccrualIntegrityController.STATUS_READY
    )

    assert result.details["gate_confirmed"] is True
    assert result.details["ledger_write_allowed"] is True
