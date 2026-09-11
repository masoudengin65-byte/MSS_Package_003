import argparse
import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.fibo_group_forward_demo_preflight import run_preflight

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal-path", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_preflight(Path(args.terminal_path), mt5)
    output = Path(args.output)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_FORWARD_DEMO_PREFLIGHT_PASSED")
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
