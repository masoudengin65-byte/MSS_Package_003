"""Write current public FIBO MT5 NDD commission evidence."""

import json
from pathlib import Path

from mss.analysis.fibo_group_current_public_commission_evidence import build_evidence

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint93_3F_FIBO_Group_Current_Public_Commission_Evidence_V1.json"
)


if __name__ == "__main__":
    result = build_evidence(ROOT)
    if result != build_evidence(ROOT):
        raise RuntimeError(
            "Deterministic FIBO public commission evidence rebuild failed"
        )
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_CURRENT_PUBLIC_COMMISSION_EVIDENCE_CREATED")
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
