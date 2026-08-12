"""Initialize the Sprint 92H.11 empty immutable True-OOS ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.true_oos_ledger_initialization import (
    TrueOosLedgerInitialization,
)
from mss.analysis.true_oos_ledger_store import (
    TrueOosLedgerStore,
)


ROOT = Path(__file__).resolve().parents[1]

H9 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H9_Raw_Immutable_True_OOS_Preregistration.json"
)

H10 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H10_One_Time_True_OOS_Anchor_Lock.json"
)

OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H11_Append_Only_True_OOS_Ledger_Initialization.json"
)

LEDGER_ROOT = (
    ROOT
    / "research_data"
    / "sprint92h_true_oos_v2"
    / "USDJPY_M15"
)

INITIAL_MANIFEST = (
    LEDGER_ROOT
    / "manifest_000000.json"
)


def load(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def sha(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"H11 report already exists: {OUTPUT}"
        )

    if INITIAL_MANIFEST.exists():
        raise RuntimeError(
            f"H11 ledger already initialized: {INITIAL_MANIFEST}"
        )

    protected_before = {
        "h9": sha(H9),
        "h10": sha(H10),
    }

    builder = TrueOosLedgerInitialization()

    first = builder.build(
        load(H9),
        load(H10),
    )

    second = builder.build(
        load(H9),
        load(H10),
    )

    if first != second:
        raise RuntimeError(
            "H11 deterministic rebuild failed"
        )

    initial_manifest = {
        "schema_version": (
            "MSS_TRUE_OOS_LEDGER_MANIFEST_V1"
        ),
        "execution_id": first["execution_id"],
        "manifest_sequence": 0,
        "previous_manifest_sha256": None,
        "true_oos_boundary": (
            first["ledger_identity"]["true_oos_boundary"]
        ),
        "timeframe": "M15",
        "symbol": "USDJPY",
        "chunk_count": 0,
        "row_count": 0,
        "first_candle_open_timestamp": None,
        "last_candle_open_timestamp": None,
        "chunks": [],
        "aggregate_ledger_sha256": (
            first["initial_state"]
            ["aggregate_ledger_sha256"]
        ),
        "eligibility_status": "ACCRUAL_NOT_STARTED",
    }

    manifest_sha = (
        TrueOosLedgerStore.write_manifest(
            INITIAL_MANIFEST,
            initial_manifest,
        )
    )

    first["created_artifacts"] = {
        "initial_manifest": (
            str(
                INITIAL_MANIFEST.relative_to(ROOT)
            ).replace("\\", "/")
        ),
        "initial_manifest_sha256": manifest_sha,
        "chunk_files_created": 0,
        "market_rows_written": 0,
    }

    first["source_file_sha256"] = (
        protected_before
    )

    first["audit"]["deterministic_rebuild"] = True

    if protected_before != {
        "h9": sha(H9),
        "h10": sha(H10),
    }:
        raise RuntimeError(
            "protected H9/H10 artifact changed"
        )

    text = json.dumps(
        first,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    OUTPUT.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    print(
        "EXECUTION_ID",
        first["execution_id"],
    )
    print(
        "TRUE_OOS_BOUNDARY",
        first["ledger_identity"]["true_oos_boundary"],
    )
    print(
        "LEDGER_ROWS",
        first["initial_state"]["row_count"],
    )
    print(
        "CHUNKS",
        first["initial_state"]["chunk_count"],
    )
    print(
        "INITIAL_MANIFEST_SHA256",
        manifest_sha,
    )
    print("MT5_ACCESSED False")
    print("MARKET_DATA_ACQUIRED False")
    print("REPLAY_RUN False")
    print("OUTCOMES_ANALYZED False")
    print(
        "JSON_SHA256",
        hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest(),
    )


if __name__ == "__main__":
    main()
