"""Create the Sprint 93.3A protocol without running a portfolio replay."""

import hashlib
import json
from pathlib import Path

from mss.analysis.shared_capital_portfolio_preregistration import (
    SharedCapitalPortfolioPreregistration,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v2.json"
OUTPUT = ROOT / "reports/MSS_Sprint93_3A_Shared_Capital_Portfolio_Preregistration.json"


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    builder = SharedCapitalPortfolioPreregistration()
    first = builder.build(source)
    if first != builder.build(source):
        raise RuntimeError("deterministic preregistration rebuild failed")
    first["source_hashes"]["source_replay_file_sha256"] = hashlib.sha256(
        source_bytes
    ).hexdigest()
    first["audit"]["deterministic_rebuild"] = True
    output = json.dumps(first, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    if SOURCE.read_bytes() != source_bytes:
        raise RuntimeError("protected source replay changed")
    print("SPRINT93_3A_PREREGISTRATION_CREATED")
    print("PRIMARY_BALANCE_USD 100.0")
    print("PRIMARY_RISK_PERCENT 0.5")
    print("CORE_SYMBOL_COUNT 8")
    print("SHARED_CAPITAL_REPLAY_RUN False")
    print("JSON_SHA256", hashlib.sha256(output.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()
