"""Run one immutable incremental True-OOS ledger accrual."""

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


ROOT = Path(__file__).resolve().parents[1]

TERMINAL_PATH = Path(
    r"C:\Program Files\Alpari MT5\terminal64.exe"
)

LEDGER_ROOT = (
    ROOT
    / "research_data"
    / "sprint92h_true_oos_v2"
    / "USDJPY_M15"
)

REQUEST_COUNT = 20_000


def sha(path):
    return hashlib.sha256(
        Path(path).read_bytes()
    ).hexdigest()


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


def main():
    previous_manifest_path = (
        latest_manifest()
    )

    previous_manifest = json.loads(
        previous_manifest_path.read_text(
            encoding="utf-8"
        )
    )

    previous_manifest_sha = sha(
        previous_manifest_path
    )

    previous_sequence = int(
        previous_manifest["manifest_sequence"]
    )

    if previous_sequence < 1:
        raise RuntimeError(
            "H13 requires at least manifest_000001"
        )

    next_sequence = previous_sequence + 1

    chunk_relative = (
        "research_data/sprint92h_true_oos_v2/"
        "USDJPY_M15/chunks/"
        f"chunk_{next_sequence:06d}.jsonl"
    )

    chunk_path = (
        ROOT / chunk_relative
    )

    next_manifest_path = (
        LEDGER_ROOT
        / f"manifest_{next_sequence:06d}.json"
    )

    report_path = (
        ROOT
        / "reports"
        / (
            "MSS_Sprint92H13_Incremental_True_OOS_Accrual_"
            f"{next_sequence:06d}.json"
        )
    )

    for path in (
        chunk_path,
        next_manifest_path,
        report_path,
    ):
        if path.exists():
            raise RuntimeError(
                f"write-once H13 target exists: {path}"
            )

    protected_before = {
        "previous_manifest": (
            previous_manifest_sha
        ),
    }

    ledger_audit = (
        TrueOosIncrementalAccrual
        .verify_existing_ledger(
            ROOT,
            previous_manifest,
        )
    )

    if not TERMINAL_PATH.is_file():
        raise RuntimeError(
            f"MT5 terminal missing: {TERMINAL_PATH}"
        )

    mt5.shutdown()

    if not mt5.initialize(
        path=str(TERMINAL_PATH),
        timeout=120_000,
    ):
        raise RuntimeError(
            f"MT5 initialization failed: "
            f"{mt5.last_error()}"
        )

    try:
        if not mt5.symbol_select(
            "USDJPY",
            True,
        ):
            raise RuntimeError(
                f"USDJPY unavailable: "
                f"{mt5.last_error()}"
            )

        current = mt5.copy_rates_from_pos(
            "USDJPY",
            mt5.TIMEFRAME_M15,
            0,
            1,
        )

        if current is None or len(current) != 1:
            raise RuntimeError(
                f"current M15 bar unavailable: "
                f"{mt5.last_error()}"
            )

        current_bar_epoch = int(
            current[0]["time"]
        )

        rates = mt5.copy_rates_from_pos(
            "USDJPY",
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

    result["created_artifacts"] = {
        "chunk": chunk_relative,
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
