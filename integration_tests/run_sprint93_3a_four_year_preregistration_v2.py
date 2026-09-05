"""Create the four-year V2 protocol without acquiring historical prices."""

import hashlib
import json
from pathlib import Path

from mss.analysis.shared_capital_portfolio_preregistration_v2 import (
    SharedCapitalPortfolioPreregistrationV2,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v2.json"
OUTPUT = ROOT / "reports/MSS_Sprint93_3A_Four_Year_Shared_Capital_Preregistration_V2.json"


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    builder = SharedCapitalPortfolioPreregistrationV2()
    first = builder.build(source)
    if first != builder.build(source):
        raise RuntimeError("deterministic V2 preregistration rebuild failed")
    first["source_hashes"]["reference_replay_file_sha256"] = hashlib.sha256(
        source_bytes
    ).hexdigest()
    first["audit"]["deterministic_rebuild"] = True
    output = json.dumps(first, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    if SOURCE.read_bytes() != source_bytes:
        raise RuntimeError("protected reference replay changed")
    print("SPRINT93_3A_FOUR_YEAR_PREREGISTRATION_V2_CREATED")
    print("WINDOW 2021-09-01T00:00:00Z 2025-09-01T00:00:00Z")
    print("HISTORY_DOWNLOADED False")
    print("REPLAY_RUN False")
    print("JSON_SHA256", hashlib.sha256(output.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()
