"""Write the Sprint 93.2A outcome-blind forward-shadow preregistration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.sprint93_confluence_gate_v2_preregistration import (
    Sprint93ConfluenceGateV2Preregistration,
)


ROOT = Path(__file__).resolve().parents[1]
G5 = ROOT / "reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json"
H6 = ROOT / "reports/MSS_Sprint92H6_Immutable_Development_Research_Closure.json"
C2 = ROOT / "reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json"
OUTPUT = ROOT / "reports/MSS_Sprint93_2A_Confluence_Gate_V2_Preregistration.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(f"Sprint 93.2A output already exists: {OUTPUT}")

    builder = Sprint93ConfluenceGateV2Preregistration()
    execution_hashes = {
        relative: sha(ROOT / relative)
        for relative in builder.REQUIRED_EXECUTION_FILES
    }
    protected = {"g5": sha(G5), "h6": sha(H6), "c2": sha(C2)}

    first = builder.build(
        load(G5), load(H6), load(C2), execution_hashes
    )
    second = builder.build(
        load(G5), load(H6), load(C2), execution_hashes
    )
    if first != second:
        raise RuntimeError("Sprint 93.2A deterministic rebuild failed")

    first["audit"]["deterministic_rebuild"] = True
    first["source_file_sha256"] = protected

    text = json.dumps(
        first,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")

    if protected != {"g5": sha(G5), "h6": sha(H6), "c2": sha(C2)}:
        raise RuntimeError("protected source artifact changed")

    print("MODE", first["mode"])
    print("EXECUTION_ID", first["execution_id"])
    print(
        "FIRST_ELIGIBLE_CANDLE_OPEN_UTC",
        first["source_governance"]["first_eligible_candle_open_utc"],
    )
    print(
        "SYMBOLS",
        ",".join(
            item["broker_symbol"]
            for item in first["paired_forward_shadow_contract"]["symbols"]
        ),
    )
    print(
        "TIMEBOX_DAYS",
        first["paired_forward_shadow_contract"]["timebox_calendar_days"],
    )
    print("MT5_ACCESSED False")
    print("REPLAY_RUN False")
    print("OUTCOMES_ANALYZED False")
    print("ORDER_CHECK_CALLED False")
    print("ORDER_SEND_CALLED False")
    print(
        "JSON_SHA256",
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


if __name__ == "__main__":
    main()
