"""Publish V5 before a fresh historical dataset freeze."""

import hashlib
import json
from pathlib import Path

from mss.analysis.shared_capital_portfolio_preregistration_v5 import (
    SharedCapitalPortfolioPreregistrationV5,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v2.json"
OUTPUT = ROOT / "reports/MSS_Sprint93_3A_Availability_Preregistration_V5.json"


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    builder = SharedCapitalPortfolioPreregistrationV5()
    result = builder.build(source)
    if result != builder.build(source):
        raise RuntimeError("deterministic V5 preregistration rebuild failed")
    result["source_hashes"]["reference_replay_file_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    result["audit"]["deterministic_rebuild"] = True
    output = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    if SOURCE.read_bytes() != source_bytes:
        raise RuntimeError("protected reference replay changed")
    print("SPRINT93_3A_AVAILABILITY_PREREGISTRATION_V5_CREATED")
    print("V4_PARTIAL_RAW_FILES_ELIGIBLE_FOR_ANALYSIS False")
    print("STRATEGY_OR_REPLAY_RUN False")
    print("JSON_SHA256", hashlib.sha256(output.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()
