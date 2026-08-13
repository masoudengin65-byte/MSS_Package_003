from pathlib import Path

from mss.analysis.true_oos_accrual_session_journal import (
    TrueOosAccrualSessionJournal,
)


def inspect(
    tmp_path: Path,
    sequence: int = 8,
):
    return (
        TrueOosAccrualSessionJournal.inspect_recovery_state(
            journal_root=tmp_path / "journal",
            sequence=sequence,
            chunk_path=tmp_path / "chunk_000008.jsonl",
            manifest_path=tmp_path / "manifest_000008.json",
            report_path=tmp_path / "report_000008.json",
        )
    )


def start(
    tmp_path: Path,
    sequence: int = 8,
):
    return (
        TrueOosAccrualSessionJournal.start_session(
            journal_root=tmp_path / "journal",
            sequence=sequence,
            previous_manifest_sha256="abc123",
            expected_chunk_path="chunk_000008.jsonl",
            expected_manifest_path="manifest_000008.json",
            expected_report_path="report_000008.json",
        )
    )


def test_ready_when_no_session_or_artifacts(
    tmp_path: Path,
) -> None:
    result = inspect(tmp_path)

    assert (
        result.status
        == TrueOosAccrualSessionJournal.STATUS_READY
    )
    assert result.details["next_attempt"] == 1
    assert result.details["ledger_write_allowed"] is True


def test_started_session_blocks_recovery_write(
    tmp_path: Path,
) -> None:
    session_path, _ = start(tmp_path)

    assert session_path.name == (
        "session_000008_000001.json"
    )

    result = inspect(tmp_path)

    assert (
        result.status
        == TrueOosAccrualSessionJournal.STATUS_INCOMPLETE_SESSION
    )
    assert result.details["attempt"] == 1
    assert result.details["session_state"] == "STARTED"
    assert result.details["ledger_write_allowed"] is False


def test_no_new_data_allows_second_attempt_same_sequence(
    tmp_path: Path,
) -> None:
    session1, _ = start(tmp_path)

    TrueOosAccrualSessionJournal.finalize_session(
        session_path=session1,
        terminal_state="NO_NEW_DATA_NO_WRITE",
        result={
            "rows_appended": 0,
            "ledger_write": False,
        },
    )

    result = inspect(tmp_path)

    assert (
        result.status
        == TrueOosAccrualSessionJournal.STATUS_READY
    )
    assert result.details["next_attempt"] == 2
    assert result.details["ledger_write_allowed"] is True

    session2, _ = start(tmp_path)

    assert session2.name == (
        "session_000008_000002.json"
    )


def test_time_authority_block_allows_retry_same_sequence(
    tmp_path: Path,
) -> None:
    session1, _ = start(tmp_path)

    TrueOosAccrualSessionJournal.finalize_session(
        session_path=session1,
        terminal_state=(
            "TIME_AUTHORITY_BLOCKED_NO_WRITE"
        ),
        result={
            "ledger_write": False,
        },
    )

    result = inspect(tmp_path)

    assert (
        result.status
        == TrueOosAccrualSessionJournal.STATUS_READY
    )
    assert result.details["next_attempt"] == 2


def test_partial_artifact_blocks_write(
    tmp_path: Path,
) -> None:
    chunk = tmp_path / "chunk_000008.jsonl"
    chunk.write_text(
        '{"test":1}\n',
        encoding="utf-8",
    )

    result = inspect(tmp_path)

    assert (
        result.status
        == TrueOosAccrualSessionJournal.STATUS_PARTIAL_ARTIFACTS
    )
    assert result.details["ledger_write_allowed"] is False
    assert (
        result.details[
            "automatic_artifact_deletion_allowed"
        ]
        is False
    )


def test_finalize_completed_write(
    tmp_path: Path,
) -> None:
    session_path, _ = start(tmp_path)

    final_sha = (
        TrueOosAccrualSessionJournal.finalize_session(
            session_path=session_path,
            terminal_state="COMPLETED_WRITE",
            result={
                "rows_appended": 2,
                "ledger_write": True,
                "replay_run": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },
        )
    )

    assert len(final_sha) == 64

    payload = (
        TrueOosAccrualSessionJournal.load_json(
            session_path
        )
    )

    assert payload["sequence"] == 8
    assert payload["attempt"] == 1
    assert payload["state"] == "COMPLETED_WRITE"
    assert payload["completed_utc"] is not None


def test_completed_write_same_target_blocks_reuse(
    tmp_path: Path,
) -> None:
    session_path, _ = start(tmp_path)

    TrueOosAccrualSessionJournal.finalize_session(
        session_path=session_path,
        terminal_state="COMPLETED_WRITE",
        result={
            "rows_appended": 2,
            "ledger_write": True,
        },
    )

    result = inspect(tmp_path)

    assert (
        result.status
        == TrueOosAccrualSessionJournal.STATUS_RECOVERY_BLOCKED
    )
    assert (
        result.details["reason"]
        == "COMPLETED_WRITE_SESSION_BUT_TARGET_SEQUENCE_STILL_CURRENT"
    )


def test_temp_session_file_blocks_recovery(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "journal"
    journal.mkdir()

    temp = (
        journal
        / "session_000008_000001.json.tmp"
    )
    temp.write_text(
        "{}",
        encoding="utf-8",
    )

    result = inspect(tmp_path)

    assert (
        result.status
        == TrueOosAccrualSessionJournal.STATUS_RECOVERY_BLOCKED
    )
    assert (
        result.details["reason"]
        == "SESSION_TEMP_ARTIFACT_REQUIRES_REVIEW"
    )
    assert result.details["ledger_write_allowed"] is False


def test_unknown_session_state_blocks(
    tmp_path: Path,
) -> None:
    session_path, _ = start(tmp_path)

    payload = (
        TrueOosAccrualSessionJournal.load_json(
            session_path
        )
    )

    payload["state"] = "UNKNOWN_STATE"

    session_path.write_text(
        __import__("json").dumps(payload),
        encoding="utf-8",
    )

    result = inspect(tmp_path)

    assert (
        result.status
        == TrueOosAccrualSessionJournal.STATUS_RECOVERY_BLOCKED
    )
    assert result.details["ledger_write_allowed"] is False
