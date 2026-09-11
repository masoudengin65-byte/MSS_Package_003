"""Write the price-pattern-only comparison report from immutable local evidence."""

import json
from pathlib import Path

from mss.analysis.fibo_group_price_pattern_comparison import build_comparison

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Price_Pattern_Comparison_V1.json"
)


if __name__ == "__main__":
    result = build_comparison(ROOT)
    if result != build_comparison(ROOT):
        raise RuntimeError("Deterministic price-pattern comparison rebuild failed")
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_PRICE_PATTERN_COMPARISON_CREATED")
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
