"""Write the non-performance FIBO candidate acquisition evidence inventory."""

import json
from pathlib import Path

from mss.analysis.fibo_group_acquisition_evidence import build_evidence


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Acquisition_Evidence_V1.json"


if __name__ == "__main__":
    result = build_evidence(ROOT)
    if result != build_evidence(ROOT):
        raise RuntimeError("Deterministic FIBO acquisition evidence rebuild failed")
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("FIBO_ACQUISITION_EVIDENCE_CREATED")
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
