"""Create Sprint 92H.3 preregistration without MT5 access or replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mss.analysis.immutable_development_replay_preregistration import (
    ImmutableDevelopmentReplayPreregistration,
)


ROOT = Path(__file__).resolve().parents[1]

H1 = ROOT / "reports/MSS_Sprint92H1_Immutable_Research_Data_Preregistration.json"
H2 = ROOT / "reports/MSS_Sprint92H2_Immutable_Research_Data_Manifest.json"
V2 = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v2.json"

OUTPUT = ROOT / "reports/MSS_Sprint92H3_Immutable_Development_Replay_Preregistration.json"


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(f"write-once preregistration already exists: {OUTPUT}")

    before = {
        str(path): sha256_file(path)
        for path in (H1, H2, V2)
    }

    h1 = json.loads(H1.read_text(encoding="utf-8"))
    h2 = json.loads(H2.read_text(encoding="utf-8"))
    v2 = json.loads(V2.read_text(encoding="utf-8"))

    builder = ImmutableDevelopmentReplayPreregistration()

    kwargs = {
        "h1_file_sha256": before[str(H1)],
        "h2_file_sha256": before[str(H2)],
        "v2_file_sha256": before[str(V2)],
    }

    first = builder.build(h1, h2, v2, **kwargs)
    second = builder.build(h1, h2, v2, **kwargs)

    if first != second:
        raise RuntimeError("deterministic preregistration rebuild failed")

    first["audit"]["deterministic_rebuild"] = True

    output = json.dumps(
        first,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    OUTPUT.write_text(output, encoding="utf-8", newline="\n")

    after = {
        str(path): sha256_file(path)
        for path in (H1, H2, V2)
    }

    if before != after:
        raise RuntimeError("protected source artifact changed")

    print("MODE", first["mode"], flush=True)
    print("SYMBOLS", first["dataset_contract"]["symbol_count"], flush=True)
    print("TOTAL_CANDLES", first["dataset_contract"]["total_candles"], flush=True)
    print("REPLAY_RUN", first["audit"]["strategy_replay_run"], flush=True)
    print("MT5_ACCESSED", first["audit"]["mt5_accessed"], flush=True)
    print("VALIDATION_ACCESSED", first["audit"]["validation_accessed"], flush=True)
    print("TRUE_OOS_USED", first["audit"]["true_future_oos_used"], flush=True)
    print(
        "JSON_SHA256",
        hashlib.sha256(output.encode()).hexdigest(),
        flush=True,
    )


if __name__ == "__main__":
    main()
