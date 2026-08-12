"""Run the first append-only True-OOS candle accrual."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.true_oos_first_accrual import TrueOosFirstAccrual
from mss.analysis.true_oos_ledger_store import TrueOosLedgerStore


ROOT = Path(__file__).resolve().parents[1]

TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")

H10 = ROOT / "reports/MSS_Sprint92H10_One_Time_True_OOS_Anchor_Lock.json"
H11 = ROOT / "reports/MSS_Sprint92H11_Append_Only_True_OOS_Ledger_Initialization.json"
H111 = ROOT / "reports/MSS_Sprint92H11_1_MT5_Time_Authority_Audit.json"

LEDGER_ROOT = (
    ROOT
    / "research_data"
    / "sprint92h_true_oos_v2"
    / "USDJPY_M15"
)

GENESIS = LEDGER_ROOT / "manifest_000000.json"
CHUNK = LEDGER_ROOT / "chunks/chunk_000001.jsonl"
MANIFEST_1 = LEDGER_ROOT / "manifest_000001.json"

OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H12_First_Append_Only_True_OOS_Accrual.json"
)

REQUEST_COUNT = 20000


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for path in (OUTPUT, CHUNK, MANIFEST_1):
        if path.exists():
            raise RuntimeError(
                f"H12 write-once artifact already exists: {path}"
            )

    protected_before = {
        "h10": sha(H10),
        "h11": sha(H11),
        "h111": sha(H111),
        "genesis": sha(GENESIS),
    }

    h10 = load(H10)
    h11 = load(H11)
    h111 = load(H111)
    genesis = load(GENESIS)

    if not TERMINAL_PATH.is_file():
        raise RuntimeError(f"MT5 terminal missing: {TERMINAL_PATH}")

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

        current = mt5.copy_rates_from_pos(
            "USDJPY",
            mt5.TIMEFRAME_M15,
            0,
            1,
        )

        if current is None or len(current) != 1:
            raise RuntimeError(
                f"current M15 bar unavailable: {mt5.last_error()}"
            )

        current_bar_epoch = int(current[0]["time"])

        rates = mt5.copy_rates_from_pos(
            "USDJPY",
            mt5.TIMEFRAME_M15,
            1,
            REQUEST_COUNT,
        )

        if rates is None:
            raise RuntimeError(
                f"M15 history unavailable: {mt5.last_error()}"
            )

    finally:
        mt5.shutdown()

    chunk_relative = (
        "research_data/sprint92h_true_oos_v2/"
        "USDJPY_M15/chunks/chunk_000001.jsonl"
    )

    result = TrueOosFirstAccrual.build(
        h10,
        h11,
        h111,
        genesis,
        rates,
        current_bar_epoch,
        chunk_relative,
        protected_before["genesis"],
    )

    eligible_rows = result.pop("_eligible_rows")

    chunk_write = TrueOosLedgerStore.write_chunk(
        CHUNK,
        eligible_rows,
    )

    if (
        chunk_write["file_sha256"]
        != result["chunk"]["file_sha256"]
    ):
        raise RuntimeError(
            "written chunk SHA does not match preregistered payload"
        )

    if chunk_write["row_count"] != result["chunk"]["row_count"]:
        raise RuntimeError("written chunk row count mismatch")

    manifest_sha = TrueOosLedgerStore.write_manifest(
        MANIFEST_1,
        result["next_manifest"],
    )

    result["created_artifacts"] = {
        "chunk_path": chunk_relative,
        "chunk_sha256": chunk_write["file_sha256"],
        "chunk_rows": chunk_write["row_count"],
        "manifest_path": (
            "research_data/sprint92h_true_oos_v2/"
            "USDJPY_M15/manifest_000001.json"
        ),
        "manifest_sha256": manifest_sha,
    }

    result["source_file_sha256"] = protected_before

    if protected_before != {
        "h10": sha(H10),
        "h11": sha(H11),
        "h111": sha(H111),
        "genesis": sha(GENESIS),
    }:
        raise RuntimeError(
            "protected source artifact changed during H12"
        )

    text = json.dumps(
        result,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    OUTPUT.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    print("STATUS", result["accrual"]["eligibility_status"])
    print("ROWS_APPENDED", result["accrual"]["completed_rows_appended"])
    print("FIRST_EPOCH", result["accrual"]["first_appended_epoch"])
    print("LAST_EPOCH", result["accrual"]["last_appended_epoch"])
    print("REMAINING_ROWS", result["accrual"]["remaining_rows"])
    print("CHUNK_SHA256", chunk_write["file_sha256"])
    print("MANIFEST_SHA256", manifest_sha)
    print("MT5_ACCESSED True")
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
