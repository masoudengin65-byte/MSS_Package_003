"""Build the no-outcome historical execution-evidence gate."""

import json
from pathlib import Path

from mss.analysis.historical_execution_evidence_gate import build_gate


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "MSS_Sprint93_3B_Historical_Execution_Evidence_Gate_V1.json"


if __name__ == "__main__":
    gate = build_gate(ROOT)
    if gate != build_gate(ROOT):
        raise RuntimeError("Deterministic historical-execution gate rebuild failed")
    OUTPUT.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("HISTORICAL_EXECUTION_EVIDENCE_GATE_CREATED")
    print("NET_PROFIT_REPLAY_ELIGIBLE", gate["net_profit_replay"]["eligible"])
    print("ORDER_SEND_CALLED", gate["safety"]["order_send_called"])
