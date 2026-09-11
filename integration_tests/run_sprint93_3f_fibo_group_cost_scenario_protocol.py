"""Collect a current FIBO snapshot and write a research-only scenario protocol."""

import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.fibo_group_cost_scenario_protocol import (
    build_protocol,
    collect_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_OUTPUT = (
    ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Current_Cost_Snapshot_V1.json"
)
PROTOCOL_OUTPUT = (
    ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Cost_Scenario_Protocol_V1.json"
)


if __name__ == "__main__":
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        snapshot = collect_snapshot(mt5)
    finally:
        mt5.shutdown()
    protocol = build_protocol(snapshot)
    SNAPSHOT_OUTPUT.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    PROTOCOL_OUTPUT.write_text(
        json.dumps(protocol, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_COST_SCENARIO_PROTOCOL_CREATED")
    print("ORDER_SEND_CALLED", protocol["safety"]["order_send_called"])
