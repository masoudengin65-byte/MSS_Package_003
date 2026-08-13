"""Run one time-authority-gated immutable True-OOS accrual."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.true_oos_incremental_accrual import (
    TrueOosIncrementalAccrual,
)
from mss.analysis.true_oos_ledger_store import (
    TrueOosLedgerStore,
)
from mss.analysis.true_oos_time_authority_gate import (
    TrueOosTimeAuthorityGate,
)


ROOT = Path(__file__).resolve().parents[1]

LEDGER_ROOT = (
    ROOT
    / "research_data"
    / "sprint92h_true_oos_v2"
    / "USDJPY_M15"
)

GLOBAL_TIME_AUTHORITY_REPORT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H13_2_Global_Time_Authority.json"
)

SYMBOL = "USDJPY"
REQUEST_COUNT = 20_000


def sha(path):
    return hashlib.sha256(
        Path(path).read_bytes()
    ).hexdigest()


def load_json(path):
    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


def latest_manifest():
    manifests = sorted(
        LEDGER_ROOT.glob(
            "manifest_[0-9][0-9][0-9][0-9][0-9][0-9].json"
        )
    )

    if not manifests:
        raise RuntimeError(
            "no True-OOS ledger manifest exists"
        )

    return manifests[-1]


def previous_broker_offset():
    if not GLOBAL_TIME_AUTHORITY_REPORT.is_file():
        raise RuntimeError(
            "committed H13.2 Global Time Authority report missing"
        )

    payload = load_json(
        GLOBAL_TIME_AUTHORITY_REPORT
    )

    if (
        payload["time_authority"]["status"]
        != "BROKER_TIME_DOMAIN_CONFIRMED"
    ):
        raise RuntimeError(
            "previous Global Time Authority was not confirmed"
        )

    return int(
        payload["observation"]
        ["detected_broker_offset_seconds"]
    )


def main():
    previous_manifest_path = (
        latest_manifest()
    )

    previous_manifest = load_json(
        previous_manifest_path
    )

    previous_manifest_sha = sha(
        previous_manifest_path
    )

    previous_sequence = int(
        previous_manifest["manifest_sequence"]
    )

    if previous_sequence < 1:
        raise RuntimeError(
            "gated accrual requires non-empty True-OOS ledger"
        )

    next_sequence = (
        previous_sequence + 1
    )

    chunk_relative = (
        "research_data/sprint92h_true_oos_v2/"
        "USDJPY_M15/chunks/"
        f"chunk_{next_sequence:06d}.jsonl"
    )

    chunk_path = (
        ROOT
        / chunk_relative
    )

    next_manifest_path = (
        LEDGER_ROOT
        / f"manifest_{next_sequence:06d}.json"
    )

    report_path = (
        ROOT
        / "reports"
        / (
            "MSS_Sprint92H13_3_Gated_True_OOS_Accrual_"
            f"{next_sequence:06d}.json"
        )
    )

    # Write-once targets are checked before MT5 access,
    # but absolutely nothing is created here.
    for path in (
        chunk_path,
        next_manifest_path,
        report_path,
    ):
        if path.exists():
            raise RuntimeError(
                f"write-once gated accrual target exists: {path}"
            )

    protected_before = {
        "previous_manifest": (
            previous_manifest_sha
        ),
        "global_time_authority_report": (
            sha(
                GLOBAL_TIME_AUTHORITY_REPORT
            )
        ),
    }

    prior_offset = (
        previous_broker_offset()
    )

    mt5.shutdown()

    # Intentionally broker-agnostic:
    # no terminal path, broker name, country,
    # or UTC offset is hardcoded.
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

        # -------------------------------------------------
        # TIME AUTHORITY GATE COMES BEFORE LEDGER WRITING.
        # -------------------------------------------------
        gate = (
            TrueOosTimeAuthorityGate
            .synchronized_snapshot(
                previous_broker_offset_seconds=(
                    prior_offset
                )
            )
        )

        TrueOosTimeAuthorityGate.require_confirmed(
            gate
        )

        current_bar_epoch = int(
            gate["current_bar_epoch"]
        )

        # Only after confirmed time authority do we obtain
        # the completed historical candle window.
        rates = mt5.copy_rates_from_pos(
            SYMBOL,
            mt5.TIMEFRAME_M15,
            1,
            REQUEST_COUNT,
        )

        if rates is None:
            raise RuntimeError(
                f"M15 history unavailable: "
                f"{mt5.last_error()}"
            )

    finally:
        mt5.shutdown()

    # No write has occurred yet.
    ledger_audit = (
        TrueOosIncrementalAccrual
        .verify_existing_ledger(
            ROOT,
            previous_manifest,
        )
    )

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

    new_rows = result.pop(
        "_new_rows"
    )

    # Recheck protected artifacts immediately
    # before first immutable write.
    if protected_before != {
        "previous_manifest": (
            sha(previous_manifest_path)
        ),
        "global_time_authority_report": (
            sha(
                GLOBAL_TIME_AUTHORITY_REPORT
            )
        ),
    }:
        raise RuntimeError(
            "protected governance artifact changed "
            "before ledger write"
        )

    # -------------------------------------------------
    # FIRST WRITE OCCURS ONLY AFTER TIME GATE PASSED.
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

    result["time_authority_gate"] = {
        "schema_version": (
            gate["schema_version"]
        ),
        "gate_confirmed": (
            gate["gate_confirmed"]
        ),
        "sync_status": (
            gate["sync"]["status"]
        ),
        "sync_attempts": (
            gate["sync"]["attempts"]
        ),
        "broker_offset_seconds": (
            gate[
                "detected_broker_offset_seconds"
            ]
        ),
        "broker_offset_label": (
            gate[
                "detected_broker_offset_label"
            ]
        ),
        "authority_status": (
            gate["authority"]
            ["time_authority"]
            ["status"]
        ),
        "ledger_write_allowed": (
            gate["fail_safe"]
            ["ledger_write_allowed"]
        ),
        "raw_mt5_time_preserved": True,
    }

    result["portability"] = {
        "terminal_auto_discovery": True,
        "hardcoded_terminal_path": False,
        "hardcoded_broker_identity": False,
        "hardcoded_broker_offset": False,
        "hardcoded_system_timezone": False,
        "country_agnostic": True,
        "broker_agnostic": True,
    }

    result["created_artifacts"] = {
        "chunk": (
            chunk_relative
        ),
        "chunk_sha256": (
            written_chunk["file_sha256"]
        ),
        "manifest": str(
            next_manifest_path
            .relative_to(ROOT)
        ).replace("\\", "/"),
        "manifest_sha256": (
            new_manifest_sha
        ),
    }

    result["protected_source_sha256"] = (
        protected_before
    )

    result["gated_accrual_governance"] = {
        "time_authority_checked_before_ledger_write": True,
        "ledger_write_without_confirmed_gate_allowed": False,
        "existing_chunks_modified": False,
        "existing_manifests_modified": False,
        "strategy_replay_run": False,
        "outcomes_analyzed": False,
        "orders_sent": False,
    }

    text = json.dumps(
        result,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    report_path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    print(
        "SEQUENCE",
        next_sequence,
    )

    print(
        "TIME_AUTHORITY_STATUS",
        gate["authority"]
        ["time_authority"]
        ["status"],
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

    print(
        "STATUS",
        result["accrual"]
        ["eligibility_status"],
    )

    print(
        "PREVIOUS_ROWS",
        result["accrual"]
        ["previous_row_count"],
    )

    print(
        "ROWS_APPENDED",
        result["accrual"]
        ["rows_appended"],
    )

    print(
        "TOTAL_ROWS",
        result["accrual"]
        ["new_total_row_count"],
    )

    print(
        "FIRST_NEW_EPOCH",
        result["accrual"]
        ["first_new_epoch"],
    )

    print(
        "LAST_NEW_EPOCH",
        result["accrual"]
        ["last_new_epoch"],
    )

    print(
        "REMAINING_ROWS",
        result["accrual"]
        ["remaining_rows"],
    )

    print(
        "BROKER_DRIFT_DETECTED",
        result["broker_drift_audit"]
        ["drift_detected"],
    )

    print(
        "DRIFTED_TIMESTAMPS",
        result["broker_drift_audit"]
        ["drifted_timestamp_count"],
    )

    print(
        "CHUNK_SHA256",
        written_chunk["file_sha256"],
    )

    print(
        "MANIFEST_SHA256",
        new_manifest_sha,
    )

    print("REPLAY_RUN False")
    print("OUTCOMES_ANALYZED False")
    print("ORDERS_SENT False")

    print(
        "JSON_SHA256",
        hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest(),
    )


if __name__ == "__main__":
    main()
