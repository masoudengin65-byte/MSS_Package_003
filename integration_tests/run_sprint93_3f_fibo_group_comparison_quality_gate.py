"""Write the FIBO comparison quality gate report."""

import json
from pathlib import Path

from mss.analysis.fibo_group_comparison_quality_gate import build_quality_gate

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Comparison_Quality_Gate_V1.json"


if __name__ == "__main__":
    result = build_quality_gate(ROOT)
    if result != build_quality_gate(ROOT):
        raise RuntimeError("Deterministic FIBO comparison quality gate rebuild failed")
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_COMPARISON_QUALITY_GATE_CREATED")
    print(
        "HISTORICAL_NET_PROFIT_REPLAY_ELIGIBLE",
        result["historical_net_profit_replay_eligible"],
    )
