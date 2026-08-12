"""Create Sprint 92H.7 preregistration without eligibility or outcome access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.distinct_future_experiment_preregistration import (
    DistinctFutureExperimentPreregistration,
)


ROOT = Path(__file__).resolve().parents[1]

H6 = ROOT / "reports/MSS_Sprint92H6_Immutable_Development_Research_Closure.json"
C2 = ROOT / "reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json"
OUTPUT = ROOT / "reports/MSS_Sprint92H7_Distinct_Future_True_OOS_Preregistration.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(f"H7 output already exists: {OUTPUT}")

    builder = DistinctFutureExperimentPreregistration()

    execution_hashes = {
        relative: sha(ROOT / relative)
        for relative in builder.REQUIRED_EXECUTION_FILES
    }

    protected = {
        "h6": sha(H6),
        "c2": sha(C2),
    }

    first = builder.build(
        load(H6),
        load(C2),
        execution_hashes,
    )

    second = builder.build(
        load(H6),
        load(C2),
        execution_hashes,
    )

    if first != second:
        raise RuntimeError("H7 deterministic rebuild failed")

    first["audit"]["deterministic_rebuild"] = True
    first["source_file_sha256"] = protected

    text = json.dumps(
        first,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    OUTPUT.write_text(text, encoding="utf-8", newline="\n")

    if protected != {
        "h6": sha(H6),
        "c2": sha(C2),
    }:
        raise RuntimeError("protected source artifact changed")

    print("MODE", first["mode"])
    print("EXECUTION_ID", first["execution_id"])
    print(
        "PRIMARY_SYMBOL",
        first["research_hypothesis"]["primary_symbol"],
    )
    print(
        "TRUE_OOS_BOUNDARY",
        first["source_lineage"]["true_oos_boundary"]["timestamp"],
    )
    print(
        "REQUIRED_CANDLES",
        first["immutable_snapshot_contract"]["required_completed_candles"],
    )
    print(
        "FROZEN_UNANALYZED_PREFIX",
        first["source_lineage"]
        ["existing_frozen_unanalyzed_prefix"]["candles"],
    )
    print("ELIGIBILITY_CHECKED False")
    print("MT5_ACCESSED False")
    print("REPLAY_RUN False")
    print("OUTCOMES_ANALYZED False")
    print("TRUE_OOS_USED False")
    print(
        "JSON_SHA256",
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


if __name__ == "__main__":
    main()
