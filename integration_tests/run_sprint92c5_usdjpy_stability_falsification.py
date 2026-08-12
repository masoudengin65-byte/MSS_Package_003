"""Build Sprint 92C.5 from the frozen C3 trade records only."""

import hashlib
import json
from pathlib import Path

from mss.analysis.usdjpy_stability_falsification import UsdJpyStabilityFalsification


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json"
OUTPUT = ROOT / "reports/MSS_Sprint92C5_USDJPY_Stability_Falsification.json"


def main():
    before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    audit = UsdJpyStabilityFalsification()
    first, second = audit.build(payload), audit.build(payload)
    if first != second:
        raise RuntimeError("Deterministic rebuild failed")
    first["source"]["source_sha256"] = before
    first["validation"]["deterministic_rebuild"] = True
    output = json.dumps(first, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != before:
        raise RuntimeError("Protected C3 source changed")
    for segment, row in first["segment_results"].items():
        print("SEGMENT", segment, row["overall"], flush=True)
        print("CHECKS", segment, row["predefined_falsification_checks"], flush=True)
    print("ASSESSMENT", first["final_assessment"], flush=True)
    print("JSON_SHA256", hashlib.sha256(output.encode()).hexdigest(), flush=True)
    print("TRUE_OOS_USED False", flush=True)


if __name__ == "__main__":
    main()
