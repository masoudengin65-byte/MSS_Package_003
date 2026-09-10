"""Publish the source-independent price-comparison preregistration."""

import json
from pathlib import Path

from mss.analysis.independent_price_comparison_preregistration import build_preregistration


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "MSS_Sprint93_3D_Independent_Price_Comparison_Preregistration_V1.json"


if __name__ == "__main__":
    result = build_preregistration(ROOT)
    if result != build_preregistration(ROOT):
        raise RuntimeError("Deterministic independent-price preregistration rebuild failed")
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("INDEPENDENT_PRICE_COMPARISON_PREREGISTRATION_CREATED")
    print("CANDIDATE_SOURCE_SELECTED", result["candidate_source"]["selected"])
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
