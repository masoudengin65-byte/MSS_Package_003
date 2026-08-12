"""Build the Sprint 92C closure and future True-OOS protocol without data access."""

import hashlib
import json
from pathlib import Path

from mss.analysis.research_closure_preregistration import ResearchClosurePreregistration


ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "c1": ROOT / "reports/MSS_Sprint92C1_Historical_Depth_Audit.json",
    "c2": ROOT / "reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json",
    "c3": ROOT / "reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json",
    "c4": ROOT / "reports/MSS_Sprint92C4_Development_Validation_Robustness.json",
    "c5": ROOT / "reports/MSS_Sprint92C5_USDJPY_Stability_Falsification.json",
}
OUTPUT = ROOT / "reports/MSS_Sprint92C6_Research_Closure_True_OOS_Preregistration.json"


def main():
    before = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in PATHS.items()}
    sources = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in PATHS.items()}
    builder = ResearchClosurePreregistration()
    first, second = builder.build(sources), builder.build(sources)
    if first != second:
        raise RuntimeError("Deterministic rebuild failed")
    first["audit"]["deterministic_rebuild"] = True
    first["source_file_sha256"] = before
    output = json.dumps(first, indent=2, sort_keys=True, allow_nan=False) + "\n"
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    after = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in PATHS.items()}
    if before != after:
        raise RuntimeError("Protected source artifact changed")
    print("CONCLUSION", first["sprint_92c_closure"]["scientific_conclusion"], flush=True)
    print("PRODUCTION_DECISION", first["sprint_92c_closure"]["production_decision"], flush=True)
    print("OOS_ELIGIBILITY_CHECKED False", flush=True)
    print("OOS_OUTCOMES_ANALYZED False", flush=True)
    print("JSON_SHA256", hashlib.sha256(output.encode()).hexdigest(), flush=True)


if __name__ == "__main__":
    main()
