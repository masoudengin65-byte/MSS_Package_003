"""Create Sprint 92H.8.2 source-integrity closure without MT5 access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.true_oos_source_integrity_closure import (
    TrueOosSourceIntegrityClosure,
)


ROOT = Path(__file__).resolve().parents[1]

H7 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H7_Distinct_Future_True_OOS_Preregistration.json"
)

H81 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H8_1_True_OOS_Eligibility_Audit.json"
)

OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H8_2_True_OOS_Source_Integrity_Closure.json"
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"H8.2 output already exists; overwrite prohibited: {OUTPUT}"
        )

    source_hashes_before = {
        "h7": sha(H7),
        "h81": sha(H81),
    }

    builder = TrueOosSourceIntegrityClosure()

    first = builder.build(
        load(H7),
        load(H81),
    )

    second = builder.build(
        load(H7),
        load(H81),
    )

    if first != second:
        raise RuntimeError("H8.2 deterministic rebuild failed")

    first["source_file_sha256"] = source_hashes_before
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

    if source_hashes_before != {
        "h7": sha(H7),
        "h81": sha(H81),
    }:
        raise RuntimeError("protected source artifact changed")

    print(
        "EXPERIMENT_STATUS",
        first["closed_experiment"]["status"],
    )
    print(
        "EXECUTION_ID",
        first["closed_experiment"]["execution_id"],
    )
    print(
        "STRATEGY_OUTCOME_STATUS",
        first["closed_experiment"]["strategy_outcome_status"],
    )
    print(
        "PREFIX_DRIFT",
        first["integrity_failure"]["failure_type"],
    )
    print(
        "NEW_PREREGISTRATION_REQUIRED",
        first["acceptance"]["new_preregistration_required"],
    )
    print("MT5_ACCESSED False")
    print("REPLAY_RUN False")
    print("OUTCOMES_ANALYZED False")
    print("PRODUCTION_CHANGE False")
    print(
        "JSON_SHA256",
        hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest(),
    )


if __name__ == "__main__":
    main()
