"""Publish the WM Markets source-specific price-comparison acquisition manifest."""

import json
from pathlib import Path

from mss.analysis.wm_markets_price_comparison_acquisition_manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "MSS_Sprint93_3E_WM_Markets_Price_Comparison_Acquisition_Manifest_V1.json"


if __name__ == "__main__":
    result = build_manifest(ROOT)
    if result != build_manifest(ROOT):
        raise RuntimeError("Deterministic WM Markets acquisition manifest rebuild failed")
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("WM_MARKETS_PRICE_COMPARISON_MANIFEST_CREATED")
    print("ALL_REQUIRED_GATES_PASS", result["pre_acquisition_gates"]["all_required_gates_pass"])
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
