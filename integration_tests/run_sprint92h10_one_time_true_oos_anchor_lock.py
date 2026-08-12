"""Run the one-time Sprint 92H.10 USDJPY M15 anchor lock."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.true_oos_anchor_lock import TrueOosAnchorLock


ROOT = Path(__file__).resolve().parents[1]

TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")

H9 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H9_Raw_Immutable_True_OOS_Preregistration.json"
)

OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H10_One_Time_True_OOS_Anchor_Lock.json"
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"H10 output already exists; anchor refresh prohibited: {OUTPUT}"
        )

    if not TERMINAL_PATH.is_file():
        raise RuntimeError(
            f"MT5 terminal missing: {TERMINAL_PATH}"
        )

    h9_hash_before = sha(H9)

    h9 = json.loads(
        H9.read_text(encoding="utf-8")
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
        if not mt5.symbol_select(
            TrueOosAnchorLock.BROKER_SYMBOL,
            True,
        ):
            raise RuntimeError(
                f"USDJPY unavailable: {mt5.last_error()}"
            )

        current = mt5.copy_rates_from_pos(
            TrueOosAnchorLock.BROKER_SYMBOL,
            mt5.TIMEFRAME_M15,
            0,
            1,
        )

        if current is None or len(current) != 1:
            raise RuntimeError(
                "USDJPY current M15 bar unavailable: "
                f"{mt5.last_error()}"
            )

        anchor_epoch = int(current[0]["time"])

    finally:
        mt5.shutdown()

    builder = TrueOosAnchorLock()

    first = builder.build(
        h9,
        anchor_epoch,
    )

    second = builder.build(
        h9,
        anchor_epoch,
    )

    if first != second:
        raise RuntimeError("H10 deterministic rebuild failed")

    first["source_file_sha256"] = {
        "h9": h9_hash_before,
    }

    first["audit"]["deterministic_rebuild"] = True

    if sha(H9) != h9_hash_before:
        raise RuntimeError("protected H9 protocol changed")

    text = json.dumps(
        first,
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
        "EXECUTION_ID",
        first["execution_id"],
    )
    print(
        "TRUE_OOS_BOUNDARY",
        first["anchor"]["boundary_timestamp"],
    )
    print(
        "ANCHOR_SOURCE",
        first["anchor"]["boundary_source"],
    )
    print("MT5_ACCESSED True")
    print("COMPLETED_TRUE_OOS_CANDLES_ACQUIRED 0")
    print("LEDGER_ROWS_WRITTEN 0")
    print("REPLAY_RUN False")
    print("OUTCOMES_ANALYZED False")
    print("ORDERS_SENT False")
    print(
        "JSON_SHA256",
        hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest(),
    )


if __name__ == "__main__":
    main()
