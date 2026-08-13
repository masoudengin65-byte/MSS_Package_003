"""Sprint 92H.13.4 read-only True-OOS reliability controller."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.true_oos_accrual_integrity_controller import (
    TrueOosAccrualIntegrityController,
)
from mss.analysis.true_oos_incremental_accrual import (
    TrueOosIncrementalAccrual,
)
from mss.analysis.true_oos_time_authority_gate import (
    TrueOosTimeAuthorityGate,
)
from mss.analysis.true_oos_ledger_store import (
    TrueOosLedgerStore,
)
from mss.analysis.true_oos_accrual_session_journal import (
    TrueOosAccrualSessionJournal,
)


ROOT = Path(__file__).resolve().parents[1]

LEDGER_ROOT = (
    ROOT
    / "research_data"
    / "sprint92h_true_oos_v2"
    / "USDJPY_M15"
)

REPORT_ROOT = ROOT / "reports"

SESSION_JOURNAL_ROOT = (
    ROOT
    / "research_data"
    / "sprint92h_true_oos_v2"
    / "USDJPY_M15"
    / "session_journal"
)

GLOBAL_TIME_AUTHORITY_REPORT = (
    REPORT_ROOT
    / "MSS_Sprint92H13_2_Global_Time_Authority.json"
)

SYMBOL = "USDJPY"
REQUEST_COUNT = 20_000


def sha(path: Path) -> str:
    return hashlib.sha256(
        Path(path).read_bytes()
    ).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


def finalize_no_write_session(
    *,
    session_path: Path,
    terminal_state: str,
    status: str,
    **details,
) -> str:
    """Finalize a normal fail-safe no-write session."""

    payload = {
        "status": status,
        "ledger_write": False,
        "manifest_write": False,
        "chunk_write": False,
        "report_write": False,
        "replay_run": False,
        "outcomes_analyzed": False,
        "orders_sent": False,
        **details,
    }

    final_sha = (
        TrueOosAccrualSessionJournal.finalize_session(
            session_path=session_path,
            terminal_state=terminal_state,
            result=payload,
        )
    )

    print(
        "SESSION_TERMINAL_STATE",
        terminal_state,
    )
    print(
        "SESSION_JOURNAL_SHA256",
        final_sha,
    )

    return final_sha


def main() -> None:
    controller = TrueOosAccrualIntegrityController

    # -------------------------------------------------
    # 1. Verify manifest chain before MT5 access.
    # -------------------------------------------------
    chain = controller.verify_manifest_chain(
        ledger_root=LEDGER_ROOT
    )

    print(
        "MANIFEST_CHAIN_STATUS",
        chain.status,
    )

    if not chain.details.get(
        "ledger_write_allowed",
        False,
    ):
        print(
            "STATUS",
            "MANIFEST_CHAIN_BLOCKED_NO_WRITE",
        )
        print("LEDGER_WRITE False")
        print("REPLAY_RUN False")
        print("OUTCOMES_ANALYZED False")
        print("ORDERS_SENT False")
        return

    previous_manifest_path, previous_manifest = (
        controller.latest_manifest(
            LEDGER_ROOT
        )
    )

    previous_manifest_sha = sha(
        previous_manifest_path
    )

    previous_sequence = int(
        previous_manifest[
            "manifest_sequence"
        ]
    )

    next_sequence = (
        previous_sequence + 1
    )

    print(
        "LATEST_SEQUENCE",
        previous_sequence,
    )

    print(
        "EXPECTED_NEXT_SEQUENCE",
        next_sequence,
    )

    # -------------------------------------------------
    # 2. Detect a pre-existing next sequence.
    # -------------------------------------------------
    preflight = (
        controller.detect_uncommitted_sequence(
            ledger_root=LEDGER_ROOT,
            report_root=REPORT_ROOT,
            expected_sequence=next_sequence,
        )
    )

    print(
        "PREFLIGHT_STATUS",
        preflight.status,
    )

    if (
        preflight.status
        == controller.STATUS_UNCOMMITTED_SEQUENCE
    ):
        print(
            "STATUS",
            "UNCOMMITTED_SEQUENCE_PRESENT_NO_WRITE",
        )
        print(
            "UNCOMMITTED_SEQUENCE",
            next_sequence,
        )
        print(
            "EXISTING_ARTIFACTS",
            json.dumps(
                preflight.details[
                    "existing_artifacts"
                ],
                sort_keys=True,
            ),
        )
        print("LEDGER_WRITE False")
        print("REPLAY_RUN False")
        print("OUTCOMES_ANALYZED False")
        print("ORDERS_SENT False")
        return

    # -------------------------------------------------
    # 2.1 Session recovery preflight.
    # -------------------------------------------------
    recovery_chunk_path = (
        LEDGER_ROOT
        / "chunks"
        / f"chunk_{next_sequence:06d}.jsonl"
    )

    recovery_manifest_path = (
        LEDGER_ROOT
        / f"manifest_{next_sequence:06d}.json"
    )

    recovery_report_path = (
        REPORT_ROOT
        / (
            "MSS_Sprint92H13_5_Session_Journal_Accrual_"
            f"{next_sequence:06d}.json"
        )
    )

    recovery = (
        TrueOosAccrualSessionJournal
        .inspect_recovery_state(
            journal_root=SESSION_JOURNAL_ROOT,
            sequence=next_sequence,
            chunk_path=recovery_chunk_path,
            manifest_path=recovery_manifest_path,
            report_path=recovery_report_path,
        )
    )

    print(
        "SESSION_RECOVERY_STATUS",
        recovery.status,
    )

    if (
        recovery.status
        != TrueOosAccrualSessionJournal.STATUS_READY
    ):
        print(
            "STATUS",
            "SESSION_RECOVERY_BLOCKED_NO_WRITE",
        )
        print("LEDGER_WRITE False")
        print("MANIFEST_WRITE False")
        print("CHUNK_WRITE False")
        print("REPORT_WRITE False")
        print("REPLAY_RUN False")
        print("OUTCOMES_ANALYZED False")
        print("ORDERS_SENT False")
        return

    # -------------------------------------------------
    # 2.2 Start session evidence.
    # Any unexpected interruption after this point
    # intentionally leaves state=STARTED.
    # -------------------------------------------------
    session_path, session_started_sha = (
        TrueOosAccrualSessionJournal.start_session(
            journal_root=SESSION_JOURNAL_ROOT,
            sequence=next_sequence,
            previous_manifest_sha256=(
                previous_manifest_sha
            ),
            expected_chunk_path=str(
                recovery_chunk_path
            ),
            expected_manifest_path=str(
                recovery_manifest_path
            ),
            expected_report_path=str(
                recovery_report_path
            ),
        )
    )

    print(
        "SESSION_JOURNAL_STATE",
        "STARTED",
    )
    print(
        "SESSION_JOURNAL_PATH",
        str(session_path),
    )
    print(
        "SESSION_STARTED_SHA256",
        session_started_sha,
    )

    # -------------------------------------------------
    # 3. Establish next immutable target names.
    #    Nothing is written in H13.4 preview mode.
    # -------------------------------------------------
    chunk_relative = (
        "research_data/"
        "sprint92h_true_oos_v2/"
        "USDJPY_M15/chunks/"
        f"chunk_{next_sequence:06d}.jsonl"
    )

    protected_before = {
        "previous_manifest":
            previous_manifest_sha,
        "global_time_authority_report":
            sha(
                GLOBAL_TIME_AUTHORITY_REPORT
            ),
    }

    # -------------------------------------------------
    # 4. Read previous confirmed broker offset.
    # -------------------------------------------------
    previous_authority = load_json(
        GLOBAL_TIME_AUTHORITY_REPORT
    )

    if (
        previous_authority[
            "time_authority"
        ]["status"]
        != "BROKER_TIME_DOMAIN_CONFIRMED"
    ):
        print(
            "STATUS",
            "PREVIOUS_TIME_AUTHORITY_NOT_CONFIRMED_NO_WRITE",
        )
        print("LEDGER_WRITE False")
        print("REPLAY_RUN False")
        print("OUTCOMES_ANALYZED False")
        print("ORDERS_SENT False")
        finalize_no_write_session(
            session_path=session_path,
            terminal_state="PRECHECK_BLOCKED_NO_WRITE",
            status="PREVIOUS_TIME_AUTHORITY_NOT_CONFIRMED_NO_WRITE",
        )
        return

    previous_offset = int(
        previous_authority[
            "observation"
        ][
            "detected_broker_offset_seconds"
        ]
    )

    # -------------------------------------------------
    # 5. Broker-agnostic MT5 time authority gate.
    # -------------------------------------------------
    mt5.shutdown()

    if not mt5.initialize(
        timeout=120_000,
    ):
        raise RuntimeError(
            "MT5 auto-discovery/initialization failed: "
            f"{mt5.last_error()}"
        )

    try:
        if not mt5.symbol_select(
            SYMBOL,
            True,
        ):
            raise RuntimeError(
                f"{SYMBOL} unavailable: "
                f"{mt5.last_error()}"
            )

        gate = (
            TrueOosTimeAuthorityGate
            .synchronized_snapshot(
                previous_broker_offset_seconds=(
                    previous_offset
                )
            )
        )

        authority_status = (
            gate[
                "authority"
            ][
                "time_authority"
            ][
                "status"
            ]
        )

        print(
            "TIME_AUTHORITY_STATUS",
            authority_status,
        )

        print(
            "TIME_GATE_CONFIRMED",
            gate["gate_confirmed"],
        )

        print(
            "BAR_SYNC_STATUS",
            gate["sync"]["status"],
        )

        print(
            "BROKER_OFFSET",
            gate[
                "detected_broker_offset_label"
            ],
        )

        if not gate["gate_confirmed"]:
            print(
                "STATUS",
                "TIME_AUTHORITY_BLOCKED_NO_WRITE",
            )
            print("LEDGER_WRITE False")
            print("MANIFEST_WRITE False")
            print("CHUNK_WRITE False")
            print("REPORT_WRITE False")
            print("REPLAY_RUN False")
            print("OUTCOMES_ANALYZED False")
            print("ORDERS_SENT False")
            finalize_no_write_session(
                session_path=session_path,
                terminal_state="TIME_AUTHORITY_BLOCKED_NO_WRITE",
                status="TIME_AUTHORITY_BLOCKED_NO_WRITE",
            )
            return

        TrueOosTimeAuthorityGate.require_confirmed(
            gate
        )

        current_bar_epoch = int(
            gate["current_bar_epoch"]
        )

        rates = mt5.copy_rates_from_pos(
            SYMBOL,
            mt5.TIMEFRAME_M15,
            1,
            REQUEST_COUNT,
        )

        if rates is None:
            raise RuntimeError(
                "M15 history unavailable: "
                f"{mt5.last_error()}"
            )

    finally:
        mt5.shutdown()

    # -------------------------------------------------
    # 6. Verify existing immutable ledger using
    #    the actual H13 engine contract.
    # -------------------------------------------------
    ledger_audit = (
        TrueOosIncrementalAccrual
        .verify_existing_ledger(
            ROOT,
            previous_manifest,
        )
    )

    print(
        "EXISTING_LEDGER_VERIFIED",
        ledger_audit["verified"],
    )

    print(
        "EXISTING_LEDGER_ROWS",
        len(ledger_audit["rows"]),
    )

    # -------------------------------------------------
    # 7. Existing ledger gap audit.
    #    Known broker-source gaps do not rewrite data.
    # -------------------------------------------------
    gap_audit = controller.scan_ledger_gaps(
        ledger_root=LEDGER_ROOT,
        timeframe_seconds=900,
    )

    print(
        "EXISTING_GAP_STATUS",
        gap_audit.status,
    )

    print(
        "EXISTING_GAP_COUNT",
        gap_audit.details.get(
            "gap_count",
            0,
        ),
    )

    if (
        gap_audit.status
        == controller.STATUS_LEDGER_INTEGRITY_FAILURE
    ):
        print(
            "STATUS",
            "LEDGER_INTEGRITY_BLOCKED_NO_WRITE",
        )
        print("LEDGER_WRITE False")
        print("REPLAY_RUN False")
        print("OUTCOMES_ANALYZED False")
        print("ORDERS_SENT False")
        finalize_no_write_session(
            session_path=session_path,
            terminal_state="PRECHECK_BLOCKED_NO_WRITE",
            status="LEDGER_INTEGRITY_BLOCKED_NO_WRITE",
        )
        return

    # -------------------------------------------------
    # 8. Build candidate accrual using exact H13 API.
    # -------------------------------------------------
    try:
        result = (
            TrueOosIncrementalAccrual.build(
                previous_manifest,
                previous_manifest_sha,
                ledger_audit,
                rates,
                current_bar_epoch,
                chunk_relative,
            )
        )

    except RuntimeError as exc:
        if (
            str(exc)
            == "NO_NEW_COMPLETED_TRUE_OOS_CANDLES_AVAILABLE"
        ):
            no_data = (
                controller.classify_no_new_data(
                    previous_row_count=int(
                        previous_manifest[
                            "row_count"
                        ]
                    )
                )
            )

            print(
                "STATUS",
                no_data.status,
            )

            print(
                "PREVIOUS_ROWS",
                no_data.details[
                    "previous_row_count"
                ],
            )

            print("ROWS_APPENDED 0")
            print("LEDGER_WRITE False")
            print("MANIFEST_WRITE False")
            print("CHUNK_WRITE False")
            print("REPORT_WRITE False")
            print("REPLAY_RUN False")
            print("OUTCOMES_ANALYZED False")
            print("ORDERS_SENT False")
            finalize_no_write_session(
                session_path=session_path,
                terminal_state="NO_NEW_DATA_NO_WRITE",
                status="NO_NEW_DATA_NO_WRITE",
            )
            return

        raise

    new_rows = result["_new_rows"]

    accrual = result["accrual"]

    # -------------------------------------------------
    # 9. Recheck protected governance artifacts.
    # -------------------------------------------------
    protected_after = {
        "previous_manifest":
            sha(
                previous_manifest_path
            ),
        "global_time_authority_report":
            sha(
                GLOBAL_TIME_AUTHORITY_REPORT
            ),
    }

    if protected_after != protected_before:
        print(
            "STATUS",
            "PROTECTED_ARTIFACT_CHANGED_NO_WRITE",
        )
        print("LEDGER_WRITE False")
        print("REPLAY_RUN False")
        print("OUTCOMES_ANALYZED False")
        print("ORDERS_SENT False")
        finalize_no_write_session(
            session_path=session_path,
            terminal_state="PRECHECK_BLOCKED_NO_WRITE",
            status="PROTECTED_ARTIFACT_CHANGED_NO_WRITE",
        )
        finalize_no_write_session(
            session_path=session_path,
            terminal_state="PRECHECK_BLOCKED_NO_WRITE",
            status="PROTECTED_ARTIFACT_CHANGED_NO_WRITE",
        )
        return

    # -------------------------------------------------
    # 10. Read-only accrual preview.
    # -------------------------------------------------
    print(
        "STATUS",
        "ACCRUAL_PREVIEW_READY",
    )

    print(
        "NEXT_SEQUENCE",
        result[
            "sequence"
        ][
            "new_manifest_sequence"
        ],
    )

    print(
        "PREVIOUS_ROWS",
        accrual[
            "previous_row_count"
        ],
    )

    print(
        "ROWS_TO_APPEND",
        accrual[
            "rows_appended"
        ],
    )

    print(
        "PROJECTED_TOTAL_ROWS",
        accrual[
            "new_total_row_count"
        ],
    )

    print(
        "FIRST_NEW_EPOCH",
        accrual[
            "first_new_epoch"
        ],
    )

    print(
        "LAST_NEW_EPOCH",
        accrual[
            "last_new_epoch"
        ],
    )

    print(
        "PROJECTED_REMAINING_ROWS",
        accrual[
            "remaining_rows"
        ],
    )

    print(
        "NEW_ROWS_BUFFERED",
        len(new_rows),
    )

    print(
        "BROKER_DRIFT_AUDIT",
        json.dumps(
            result[
                "broker_drift_audit"
            ],
            sort_keys=True,
            default=str,
        ),
    )

    print(
        "NEW_ROWS_INTEGRITY_PASS",
        result[
            "new_rows_integrity"
        ][
            "pass"
        ],
    )

    # -------------------------------------------------
    # 11. Final pre-write target and governance checks.
    # -------------------------------------------------
    chunk_path = (
        ROOT
        / chunk_relative
    )

    next_manifest_path = (
        LEDGER_ROOT
        / f"manifest_{next_sequence:06d}.json"
    )

    report_path = (
        REPORT_ROOT
        / (
            "MSS_Sprint92H13_5_Session_Journal_Accrual_"
            f"{next_sequence:06d}.json"
        )
    )

    for target in (
        chunk_path,
        next_manifest_path,
        report_path,
    ):
        if target.exists():
            print(
                "STATUS",
                "WRITE_ONCE_TARGET_EXISTS_NO_WRITE",
            )
            print(
                "EXISTING_TARGET",
                str(target),
            )
            print("LEDGER_WRITE False")
            print("MANIFEST_WRITE False")
            print("CHUNK_WRITE False")
            print("REPORT_WRITE False")
            print("REPLAY_RUN False")
            print("OUTCOMES_ANALYZED False")
            print("ORDERS_SENT False")
            finalize_no_write_session(
                session_path=session_path,
                terminal_state="UNCOMMITTED_SEQUENCE_BLOCKED_NO_WRITE",
                status="WRITE_ONCE_TARGET_EXISTS_NO_WRITE",
            )
            return

    if {
        "previous_manifest":
            sha(previous_manifest_path),
        "global_time_authority_report":
            sha(GLOBAL_TIME_AUTHORITY_REPORT),
    } != protected_before:
        print(
            "STATUS",
            "PROTECTED_ARTIFACT_CHANGED_NO_WRITE",
        )
        print("LEDGER_WRITE False")
        print("MANIFEST_WRITE False")
        print("CHUNK_WRITE False")
        print("REPORT_WRITE False")
        print("REPLAY_RUN False")
        print("OUTCOMES_ANALYZED False")
        print("ORDERS_SENT False")
        finalize_no_write_session(
            session_path=session_path,
            terminal_state="PRECHECK_BLOCKED_NO_WRITE",
            status="PROTECTED_ARTIFACT_CHANGED_NO_WRITE",
        )
        return

    # -------------------------------------------------
    # 12. Immutable write phase.
    # -------------------------------------------------
    written_chunk = (
        TrueOosLedgerStore.write_chunk(
            chunk_path,
            new_rows,
        )
    )

    if (
        written_chunk["file_sha256"]
        != result["new_chunk"]["file_sha256"]
    ):
        raise RuntimeError(
            "new chunk SHA mismatch"
        )

    if (
        written_chunk["row_count"]
        != result["new_chunk"]["row_count"]
    ):
        raise RuntimeError(
            "new chunk row-count mismatch"
        )

    new_manifest_sha = (
        TrueOosLedgerStore.write_manifest(
            next_manifest_path,
            result["next_manifest"],
        )
    )

    if (
        sha(previous_manifest_path)
        != previous_manifest_sha
    ):
        raise RuntimeError(
            "previous immutable manifest changed"
        )

    # -------------------------------------------------
    # 13. Post-write gap audit.
    # -------------------------------------------------
    post_gap = controller.scan_ledger_gaps(
        ledger_root=LEDGER_ROOT,
        timeframe_seconds=900,
    )

    if (
        post_gap.status
        == controller.STATUS_LEDGER_INTEGRITY_FAILURE
    ):
        raise RuntimeError(
            "post-write ledger integrity failure"
        )

    result["time_authority_gate"] = {
        "schema_version": gate["schema_version"],
        "gate_confirmed": gate["gate_confirmed"],
        "sync_status": gate["sync"]["status"],
        "sync_attempts": gate["sync"]["attempts"],
        "broker_offset_seconds": (
            gate["detected_broker_offset_seconds"]
        ),
        "broker_offset_label": (
            gate["detected_broker_offset_label"]
        ),
        "authority_status": authority_status,
    }

    result["reliability_controller"] = {
        "schema_version": (
            "MSS_SPRINT_92H13_4_RELIABILITY_REPORT_V1"
        ),
        "manifest_chain_status": chain.status,
        "preflight_status": preflight.status,
        "existing_gap_status": gap_audit.status,
        "existing_gap_count": (
            gap_audit.details.get(
                "gap_count",
                0,
            )
        ),
        "post_write_gap_status": post_gap.status,
        "post_write_gap_count": (
            post_gap.details.get(
                "gap_count",
                0,
            )
        ),
        "known_broker_source_gaps_preserved": True,
        "synthetic_backfill_allowed": False,
        "ledger_rewrite_allowed": False,
        "write_phase_enabled": True,
    }

    result["immutable_write"] = {
        "chunk_path": str(chunk_path),
        "chunk_sha256": (
            written_chunk["file_sha256"]
        ),
        "manifest_path": str(
            next_manifest_path
        ),
        "manifest_sha256": new_manifest_sha,
        "report_path": str(report_path),
    }

    session_payload_at_report = (
        TrueOosAccrualSessionJournal.load_json(
            session_path
        )
    )

    result["session_journal"] = {
        "schema_version": (
            TrueOosAccrualSessionJournal.VERSION
        ),
        "target_sequence": next_sequence,
        "attempt": session_payload_at_report["attempt"],
        "session_path": str(session_path),
        "started_sha256": session_started_sha,
        "state_at_report_write": (
            session_payload_at_report["state"]
        ),
        "completion_policy": (
            "FINALIZE_ONLY_AFTER_CHUNK_MANIFEST_REPORT_DURABLE"
        ),
        "unexpected_interruption_policy": (
            "LEAVE_STARTED_AND_BLOCK_AUTOMATIC_CONTINUATION"
        ),
    }

    result["audit"]["strategy_replay_run"] = False
    result["audit"]["outcomes_analyzed"] = False
    result["audit"]["orders_sent"] = False

    report_bytes = (
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        + "\n"
    ).encode("utf-8")

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with report_path.open("xb") as f:
        f.write(report_bytes)
        f.flush()

    report_sha = sha(report_path)

    session_final_sha = (
        TrueOosAccrualSessionJournal.finalize_session(
            session_path=session_path,
            terminal_state="COMPLETED_WRITE",
            result={
                "status": (
                    result["accrual"][
                        "eligibility_status"
                    ]
                ),
                "target_sequence": next_sequence,
                "attempt": (
                    session_payload_at_report[
                        "attempt"
                    ]
                ),
                "previous_row_count": (
                    result["accrual"][
                        "previous_row_count"
                    ]
                ),
                "rows_appended": (
                    result["accrual"][
                        "rows_appended"
                    ]
                ),
                "new_total_row_count": (
                    result["accrual"][
                        "new_total_row_count"
                    ]
                ),
                "chunk_sha256": (
                    written_chunk[
                        "file_sha256"
                    ]
                ),
                "manifest_sha256": (
                    new_manifest_sha
                ),
                "report_sha256": report_sha,
                "post_write_gap_count": (
                    post_gap.details.get(
                        "gap_count",
                        0,
                    )
                ),
                "ledger_write": True,
                "chunk_write": True,
                "manifest_write": True,
                "report_write": True,
                "replay_run": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },
        )
    )

    print(
        "SESSION_TERMINAL_STATE",
        "COMPLETED_WRITE",
    )
    print(
        "SESSION_FINAL_SHA256",
        session_final_sha,
    )

    print(
        "STATUS",
        result["accrual"]["eligibility_status"],
    )
    print(
        "SEQUENCE",
        result["sequence"]["new_manifest_sequence"],
    )
    print(
        "PREVIOUS_ROWS",
        result["accrual"]["previous_row_count"],
    )
    print(
        "ROWS_APPENDED",
        result["accrual"]["rows_appended"],
    )
    print(
        "TOTAL_ROWS",
        result["accrual"]["new_total_row_count"],
    )
    print(
        "FIRST_NEW_EPOCH",
        result["accrual"]["first_new_epoch"],
    )
    print(
        "LAST_NEW_EPOCH",
        result["accrual"]["last_new_epoch"],
    )
    print(
        "REMAINING_ROWS",
        result["accrual"]["remaining_rows"],
    )
    print(
        "BROKER_DRIFT_DETECTED",
        result["broker_drift_audit"]["drift_detected"],
    )
    print(
        "DRIFTED_TIMESTAMPS",
        result["broker_drift_audit"]["drifted_timestamp_count"],
    )
    print(
        "POST_WRITE_GAP_COUNT",
        post_gap.details.get(
            "gap_count",
            0,
        ),
    )
    print(
        "CHUNK_SHA256",
        written_chunk["file_sha256"],
    )
    print(
        "MANIFEST_SHA256",
        new_manifest_sha,
    )
    print(
        "REPORT_SHA256",
        report_sha,
    )
    print("WRITE_PHASE_ENABLED True")
    print("REPLAY_RUN False")
    print("OUTCOMES_ANALYZED False")
    print("ORDERS_SENT False")


if __name__ == "__main__":
    main()
