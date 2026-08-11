"""Build Sprint 92B.1 solely from the frozen v2 replay JSON."""

import json
from pathlib import Path

from mss.analysis.temporal_stability_audit import TemporalStabilityAudit


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v2.json"
OUTPUT = ROOT / "reports/MSS_Sprint92B1_Temporal_Stability_Audit.json"


def main():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    report = TemporalStabilityAudit().build(source)
    repeated = TemporalStabilityAudit().build(source)
    if report != repeated:
        raise RuntimeError("Temporal audit rebuild is not deterministic")
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT}")
    for symbol, row in report["temporal_classifications"].items():
        print(symbol, row["classification"])
    print(report["xauusd_deep_audit"]["answer"])
    print("STRATEGY_REPLAY_RUN=False")


if __name__ == "__main__":
    main()
