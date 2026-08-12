"""Run Sprint 92H.8.1 eligibility check without strategy replay or outcomes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.true_oos_eligibility_audit import TrueOosEligibilityAudit


ROOT = Path(__file__).resolve().parents[1]

TERMINAL_PATH = Path(r"C:\Program Files\Alpari MT5\terminal64.exe")

PROTOCOL = (
    ROOT
    / "reports"
    / "MSS_Sprint92H7_Distinct_Future_True_OOS_Preregistration.json"
)

OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H8_1_True_OOS_Eligibility_Audit.json"
)

REQUEST_COUNT = 20_000


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"H8.1 output already exists; rerun prohibited: {OUTPUT}"
        )

    if not TERMINAL_PATH.is_file():
        raise RuntimeError(
            f"MT5 terminal missing: {TERMINAL_PATH}"
        )

    protocol_hash_before = file_sha(PROTOCOL)

    protocol = json.loads(
        PROTOCOL.read_text(encoding="utf-8")
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
            TrueOosEligibilityAudit.BROKER_SYMBOL,
            True,
        ):
            raise RuntimeError(
                "USDJPY symbol unavailable: "
                f"{mt5.last_error()}"
            )

        current = mt5.copy_rates_from_pos(
            TrueOosEligibilityAudit.BROKER_SYMBOL,
            mt5.TIMEFRAME_M15,
            0,
            1,
        )

        if current is None or len(current) != 1:
            raise RuntimeError(
                "current M15 bar unavailable: "
                f"{mt5.last_error()}"
            )

        current_bar_open_epoch = int(
            current[0]["time"]
        )

        rates = mt5.copy_rates_from_pos(
            TrueOosEligibilityAudit.BROKER_SYMBOL,
            mt5.TIMEFRAME_M15,
            1,
            REQUEST_COUNT,
        )

        if rates is None:
            raise RuntimeError(
                "completed M15 retrieval failed: "
                f"{mt5.last_error()}"
            )

        payload = TrueOosEligibilityAudit.build(
            protocol,
            rates,
            current_bar_open_epoch,
        )

    finally:
        mt5.shutdown()

    payload["source"]["requested_history_count"] = REQUEST_COUNT
    payload["source"]["returned_history_count"] = len(rates)
    payload["source"]["h7_protocol_file_sha256"] = (
        protocol_hash_before
    )

    payload["audit"]["deterministic_report_build"] = True

    if file_sha(PROTOCOL) != protocol_hash_before:
        raise RuntimeError(
            "protected H7 protocol changed"
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
        payload["eligibility"]["status"],
    )
    print(
        "AVAILABLE_COMPLETED_CANDLES",
        payload["eligibility"]["available_completed_candles"],
    )
    print(
        "REQUIRED_COMPLETED_CANDLES",
        payload["eligibility"]["required_completed_candles"],
    )
    print(
        "REMAINING_CANDLES",
        payload["eligibility"]["remaining_candles"],
    )
    print(
        "PREFIX_227_VERIFIED",
        payload["acceptance"]["frozen_227_prefix_verified"],
    )
    print(
        "SOURCE_INTEGRITY_PASS",
        payload["acceptance"]["source_integrity_passed"],
    )
    print(
        "SNAPSHOT_EXPORTED",
        payload["eligibility"]["snapshot_exported"],
    )
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
