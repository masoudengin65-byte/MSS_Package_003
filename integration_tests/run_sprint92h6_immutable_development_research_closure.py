"""Run Sprint 92H.6 research closure only. No replay or market-data access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.immutable_development_research_closure import (
    ImmutableDevelopmentResearchClosure,
)


ROOT = Path(__file__).resolve().parents[1]

H5 = ROOT / "reports/MSS_Sprint92H5_Immutable_Development_Outcome_Analysis.json"
C6 = ROOT / "reports/MSS_Sprint92C6_Research_Closure_True_OOS_Preregistration.json"
E8 = ROOT / "reports/MSS_Sprint92E8_External_Historical_Validation_Closure.json"
G5 = ROOT / "reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json"

OUTPUT = ROOT / "reports/MSS_Sprint92H6_Immutable_Development_Research_Closure.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(f"H6 output already exists: {OUTPUT}")

    protected = {
        "h5": sha(H5),
        "c6": sha(C6),
        "e8": sha(E8),
        "g5": sha(G5),
    }

    builder = ImmutableDevelopmentResearchClosure()

    first = builder.build(
        load(H5),
        load(C6),
        load(E8),
        load(G5),
    )

    second = builder.build(
        load(H5),
        load(C6),
        load(E8),
        load(G5),
    )

    if first != second:
        raise RuntimeError("H6 deterministic rebuild failed")

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
        "h5": sha(H5),
        "c6": sha(C6),
        "e8": sha(E8),
        "g5": sha(G5),
    }:
        raise RuntimeError("protected source artifact changed")

    print(
        "USDJPY_STATUS",
        first["immutable_development_closure"]
        ["final_classifications"]["USDJPY"],
    )
    print(
        "LEGACY_C6_EXECUTION_AUTHORIZED",
        first["legacy_true_oos_protocol"]
        ["automatic_execution_authorized_by_h6"],
    )
    print(
        "NEW_PREREGISTRATION_REQUIRED",
        first["future_experiment_governance"]
        ["next_experiment_requires_new_preregistration"],
    )
    print(
        "TRUE_OOS_STATUS",
        first["future_experiment_governance"]
        ["true_future_oos_status"],
    )
    print("REPLAY_RUN False")
    print("MT5_ACCESSED False")
    print("VALIDATION_ACCESSED False")
    print("TRUE_OOS_USED False")
    print("PRODUCTION_CHANGE_JUSTIFIED False")

    print(
        "JSON_SHA256",
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


if __name__ == "__main__":
    main()
