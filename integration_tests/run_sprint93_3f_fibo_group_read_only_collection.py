"""Run the preregistered FIBO demo collector; it never logs in or sends orders."""

from __future__ import annotations

import argparse
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.fibo_group_read_only_collector import collect


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal-path", required=True)
    arguments = parser.parse_args()
    result = collect(ROOT, Path(arguments.terminal_path), mt5)
    print("FIBO_READ_ONLY_COLLECTION_COMPLETE")
    print("ORDER_CHECK_CALLED", result["order_check_called"])
    print("ORDER_SEND_CALLED", result["order_send_called"])
