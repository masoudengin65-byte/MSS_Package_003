"""Create Sprint 92H.9 preregistration without MT5 or market-data access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.raw_immutable_true_oos_preregistration import (
    RawImmutableTrueOosPreregistration,
)


ROOT = Path(__file__).resolve().parents[1]

H7 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H7_Distinct_Future_True_OOS_Preregistration.json"
)

H82 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H8_2_True_OOS_Source_Integrity_Closure.json"
)

OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H9_Raw_Immutable_True_OOS_Preregistration.json"
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"H9 output already exists; overwrite prohibited: {OUTPUT}"
        )

    protected_before = {
        "h7": sha(H7),
        "h82": sha(H82),
    }

    builder = RawImmutableTrueOosPreregistration()

    first = builder.build(
        load(H7),
        load(H82),
    )

    second = builder.build(
        load(H7),
        load(H82),
    )

    if first != second:
        raise RuntimeError("H9 deterministic rebuild failed")

    first["source_file_sha256"] = protected_before
    first["audit"]["deterministic_rebuild"] = True

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

    if protected_before != {
        "h7": sha(H7),
        "h82": sha(H82),
    }:
        raise RuntimeError("protected source artifact changed")

    print(
        "EXECUTION_ID",
        first["execution_id"],
    )
    print(
        "PRIMARY_SYMBOL",
        first["research_hypothesis"]["primary_symbol"],
    )
    print(
        "BOUNDARY_LOCKED_IN_H9",
        first["new_boundary_contract"]["exact_timestamp_locked_in_h9"],
    )
    print(
        "REQUIRED_CANDLES",
        first["immutable_accrual_contract"]["required_completed_candles"],
    )
    print(
        "STORAGE",
        first["immutable_accrual_contract"]["storage_model"],
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
