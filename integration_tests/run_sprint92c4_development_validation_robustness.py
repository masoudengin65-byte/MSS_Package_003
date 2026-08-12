"""Build Sprint 92C.4 from the frozen Sprint 92C.3 artifact only."""

import hashlib
import json
from pathlib import Path

from mss.analysis.development_validation_robustness import DevelopmentValidationRobustness


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json"
OUTPUT = ROOT / "reports/MSS_Sprint92C4_Development_Validation_Robustness.json"


def main():
    source_before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    audit = DevelopmentValidationRobustness()
    first = audit.build(payload)
    second = audit.build(payload)
    if first != second:
        raise RuntimeError("Deterministic rebuild failed")
    first["validation"]["deterministic_rebuild"] = True
    first["source"]["source_sha256"] = source_before
    output = json.dumps(first, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_before:
        raise RuntimeError("Protected Sprint 92C.3 source changed")
    for symbol, classification in first["final_classifications"].items():
        dev = first["per_symbol_results"][symbol]["ordinary_bootstrap"]["DEVELOPMENT"]["bootstrap_metrics"]["expectancy"]
        val = first["per_symbol_results"][symbol]["ordinary_bootstrap"]["VALIDATION"]["bootstrap_metrics"]["expectancy"]
        print("RESULT", symbol, classification, dev["ci_95"]["lower"], dev["ci_95"]["upper"], val["ci_95"]["lower"], val["ci_95"]["upper"], flush=True)
    print("JSON_SHA256", hashlib.sha256(output.encode()).hexdigest(), flush=True)
    print("STRATEGY_REPLAY_RUN False", flush=True)
    print("TRUE_OOS_USED False", flush=True)


if __name__ == "__main__":
    main()
