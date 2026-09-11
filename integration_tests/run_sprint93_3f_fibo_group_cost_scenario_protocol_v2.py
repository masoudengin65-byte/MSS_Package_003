"""Write the V2 FIBO current-reference scenario protocol."""

import json
from pathlib import Path

from mss.analysis.fibo_group_cost_scenario_protocol_v2 import build_protocol

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Cost_Scenario_Protocol_V2.json"


if __name__ == "__main__":
    result = build_protocol(ROOT)
    if result != build_protocol(ROOT):
        raise RuntimeError(
            "Deterministic FIBO V2 cost scenario protocol rebuild failed"
        )
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_COST_SCENARIO_PROTOCOL_V2_CREATED")
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
