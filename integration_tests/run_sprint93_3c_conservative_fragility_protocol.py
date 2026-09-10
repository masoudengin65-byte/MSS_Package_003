"""Publish the preregistered conservative fragility-screen protocol."""

import json
from pathlib import Path

from mss.analysis.historical_conservative_fragility_protocol import build_protocol


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "MSS_Sprint93_3C_Conservative_Fragility_Protocol_V1.json"


if __name__ == "__main__":
    protocol = build_protocol(ROOT)
    if protocol != build_protocol(ROOT):
        raise RuntimeError("Deterministic conservative-fragility protocol rebuild failed")
    OUTPUT.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("CONSERVATIVE_FRAGILITY_PROTOCOL_CREATED")
    print("BROKER_ACCURATE_NET_PROFIT_CLAIM_ALLOWED", protocol["research_boundary"]["broker_accurate_net_profit_claim_allowed"])
    print("ORDER_SEND_CALLED", protocol["audit"]["order_send_called"])
