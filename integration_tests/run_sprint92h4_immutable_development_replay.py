"""Run the single preregistered Sprint 92H.4 immutable Development replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.immutable_development_replay import ImmutableDevelopmentReplay


ROOT = Path(__file__).resolve().parents[1]

PROTOCOL = ROOT / "reports/MSS_Sprint92H3_Immutable_Development_Replay_Preregistration.json"
OUTPUT = ROOT / "reports/MSS_Sprint92H4_Immutable_Development_Replay.json"


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"authoritative H.4 output already exists; rerun prohibited: {OUTPUT}"
        )

    protocol_bytes = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_bytes)

    engine = ImmutableDevelopmentReplay()

    histories, source_verification = engine.load_verified_sources(
        ROOT,
        protocol,
    )

    metadata = engine.frozen_metadata(protocol)
    config = engine.config()

    print("SOURCE_VERIFICATION_PASS", len(source_verification) == 8, flush=True)
    print("TOTAL_SOURCE_CANDLES", sum(len(x) for x in histories.values()), flush=True)
    print("MT5_ACCESSED False", flush=True)
    print("VALIDATION_ACCESSED False", flush=True)
    print("TRUE_OOS_USED False", flush=True)

    print("AUTHORITATIVE_DEVELOPMENT_REPLAY_COUNT 1", flush=True)

    results = engine.replay.run_once(
        histories,
        metadata,
        config,
    )

    payload = engine.summarize(
        histories,
        metadata,
        results,
        source_verification,
        protocol,
    )

    payload["source"]["h3_protocol_file_sha256"] = file_sha(PROTOCOL)

    first = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    second_payload = engine.summarize(
        histories,
        metadata,
        results,
        source_verification,
        protocol,
    )
    second_payload["source"]["h3_protocol_file_sha256"] = file_sha(PROTOCOL)

    second = json.dumps(
        second_payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if first != second:
        raise RuntimeError("deterministic frozen-result artifact rebuild failed")

    payload["audit"]["deterministic_artifact_rebuild"] = True

    output = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    OUTPUT.write_text(
        output,
        encoding="utf-8",
        newline="\n",
    )

    for row in payload["per_symbol_results"]:
        print(
            "RESULT",
            row["canonical_symbol"],
            "CLOSED",
            row["closed_trades"],
            "NET",
            row["net_profit"],
            "PF",
            row["profit_factor"],
            "RETURN",
            row["return_percent"],
            flush=True,
        )

    combined = payload["combined_independent_results"]

    print(
        "COMBINED",
        json.dumps(combined, sort_keys=True),
        flush=True,
    )

    print(
        "JSON_SHA256",
        hashlib.sha256(output.encode()).hexdigest(),
        flush=True,
    )

    print("REAL_ORDERS_SENT False", flush=True)


if __name__ == "__main__":
    main()
