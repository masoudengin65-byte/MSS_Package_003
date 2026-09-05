"""Create the corrected UTC V3 protocol without acquiring prices."""

import hashlib
import json
from pathlib import Path

from mss.analysis.shared_capital_portfolio_preregistration_v3 import (
    SharedCapitalPortfolioPreregistrationV3,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v2.json"
OUTPUT = ROOT / "reports/MSS_Sprint93_3A_Four_Year_Shared_Capital_Preregistration_V3.json"


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    builder = SharedCapitalPortfolioPreregistrationV3()
    result = builder.build(source)
    if result != builder.build(source):
        raise RuntimeError("deterministic V3 preregistration rebuild failed")
    result["source_hashes"]["reference_replay_file_sha256"] = hashlib.sha256(
        source_bytes
    ).hexdigest()
    result["audit"]["deterministic_rebuild"] = True
    output = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    if SOURCE.read_bytes() != source_bytes:
        raise RuntimeError("protected reference replay changed")
    print("SPRINT93_3A_UTC_PREREGISTRATION_V3_CREATED")
    print("RETURNED_EPOCH_DOMAIN UTC")
    print("MANUAL_BROKER_OFFSET_APPLIED False")
    print("HISTORY_DOWNLOADED False")
    print("JSON_SHA256", hashlib.sha256(output.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()
