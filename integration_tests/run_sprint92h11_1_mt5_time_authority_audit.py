"""Run Sprint 92H.11.1 MT5 time-authority audit."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.mt5_time_authority_audit import (
    Mt5TimeAuthorityAudit,
)


ROOT = Path(__file__).resolve().parents[1]

TERMINAL_PATH = Path(
    r"C:\Program Files\Alpari MT5\terminal64.exe"
)

H10 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H10_One_Time_True_OOS_Anchor_Lock.json"
)

H11 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H11_Append_Only_True_OOS_Ledger_Initialization.json"
)

OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H11_1_MT5_Time_Authority_Audit.json"
)


def load(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def sha(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"H11.1 output already exists: {OUTPUT}"
        )

    protected = {
        "h10": sha(H10),
        "h11": sha(H11),
    }

    if not TERMINAL_PATH.is_file():
        raise RuntimeError(
            f"MT5 terminal missing: {TERMINAL_PATH}"
        )

    mt5.shutdown()

    if not mt5.initialize(
        path=str(TERMINAL_PATH),
        timeout=120_000,
    ):
        raise RuntimeError(
            f"MT5 initialization failed: {mt5.last_error()}"
        )

    try:
        if not mt5.symbol_select("USDJPY", True):
            raise RuntimeError(
                f"USDJPY unavailable: {mt5.last_error()}"
            )

        tick = mt5.symbol_info_tick("USDJPY")

        bar = mt5.copy_rates_from_pos(
            "USDJPY",
            mt5.TIMEFRAME_M15,
            0,
            1,
        )

        if tick is None:
            raise RuntimeError(
                f"USDJPY tick unavailable: {mt5.last_error()}"
            )

        if bar is None or len(bar) != 1:
            raise RuntimeError(
                f"USDJPY M15 bar unavailable: {mt5.last_error()}"
            )

        windows_epoch = int(
            datetime.now(timezone.utc).timestamp()
        )

        tick_epoch = int(tick.time)
        bar_epoch = int(bar[0]["time"])

    finally:
        mt5.shutdown()

    builder = Mt5TimeAuthorityAudit()

    payload = builder.build(
        load(H10),
        load(H11),
        windows_epoch,
        tick_epoch,
        bar_epoch,
    )

    payload["source_file_sha256"] = protected

    if protected != {
        "h10": sha(H10),
        "h11": sha(H11),
    }:
        raise RuntimeError(
            "protected H10/H11 artifact changed"
        )

    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    OUTPUT.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    print(
        "STATUS",
        payload["time_authority"]["status"],
    )
    print(
        "OBSERVED_OFFSET_SEC",
        payload["observation"]
        ["observed_tick_minus_windows_seconds"],
    )
    print(
        "BAR_MATCHES_BROKER_CLOCK",
        payload["observation"]
        ["bar_matches_broker_clock"],
    )
    print(
        "BAR_M15_ALIGNED",
        payload["observation"]["bar_m15_aligned"],
    )
    print(
        "H10_ANCHOR_PRESERVED",
        payload["acceptance"]["h10_anchor_preserved"],
    )
    print(
        "H11_GENESIS_PRESERVED",
        payload["acceptance"]["h11_genesis_preserved"],
    )
    print("LEDGER_ROWS_WRITTEN 0")
    print("REPLAY_RUN False")
    print("OUTCOMES_ANALYZED False")
    print(
        "JSON_SHA256",
        hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest(),
    )


if __name__ == "__main__":
    main()
