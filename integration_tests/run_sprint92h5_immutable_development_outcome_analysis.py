"""Run Sprint 92H.5 from the frozen H.4 result only; no replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.immutable_development_outcome_analysis import (
    ImmutableDevelopmentOutcomeAnalysis,
)


ROOT = Path(__file__).resolve().parents[1]

SOURCE = ROOT / "reports/MSS_Sprint92H4_Immutable_Development_Replay.json"
OUTPUT = ROOT / "reports/MSS_Sprint92H5_Immutable_Development_Outcome_Analysis.json"


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"H5 output already exists: {OUTPUT}"
        )

    before = file_hash(SOURCE)

    payload = json.loads(
        SOURCE.read_text(encoding="utf-8")
    )

    analyzer = ImmutableDevelopmentOutcomeAnalysis()

    first = analyzer.build(payload)
    second = analyzer.build(payload)

    if first != second:
        raise RuntimeError(
            "deterministic H5 analysis rebuild failed"
        )

    first["audit"]["deterministic_rebuild"] = True
    first["source"]["h4_file_sha256"] = before

    output = json.dumps(
        first,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    OUTPUT.write_text(
        output,
        encoding="utf-8",
        newline="\n",
    )

    if file_hash(SOURCE) != before:
        raise RuntimeError(
            "protected H4 artifact changed"
        )

    print(
        "CLOSED_TRADES",
        first["source"]["closed_trade_count"],
        flush=True,
    )

    for symbol, label in first["final_classifications"].items():
        row = first["per_symbol_results"][symbol]
        point = row["point_metrics"]
        ordinary = row["ordinary_bootstrap"]["bootstrap_metrics"]["expectancy"]
        block = row["moving_block_bootstrap"]["bootstrap_metrics"]["expectancy"]

        print(
            "RESULT",
            symbol,
            "NET",
            round(point["net_pnl_account_currency"], 2),
            "EXPECTANCY",
            round(point["expectancy_account_currency"], 4),
            "PF",
            round(point["profit_factor"], 4)
            if point["profit_factor"] is not None
            else None,
            "TEMPORAL",
            row["temporal_classification"]["classification"],
            "P_ORD",
            round(ordinary["probability_above_threshold"], 4),
            "P_BLOCK",
            round(block["probability_above_threshold"], 4),
            "CLASS",
            label,
            flush=True,
        )

    print(
        "ALL_RECONCILED",
        first["reconciliation"]["all_symbols_reconciled"],
        flush=True,
    )

    print("REPLAY_RUN False", flush=True)
    print("MT5_ACCESSED False", flush=True)
    print("VALIDATION_ACCESSED False", flush=True)
    print("TRUE_OOS_USED False", flush=True)
    print("PRODUCTION_CHANGE_JUSTIFIED False", flush=True)

    print(
        "JSON_SHA256",
        hashlib.sha256(output.encode()).hexdigest(),
        flush=True,
    )


if __name__ == "__main__":
    main()
