"""Sprint 92H.14.1 live read-only MT5 observation validation."""

from __future__ import annotations

import json
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.live_market_observer import (
    LiveMarketObserver,
)


ROOT = Path(__file__).resolve().parents[1]

REPORT_PATH = (
    ROOT
    / "reports"
    / "MSS_Sprint92H14_1_Live_Market_Observation_Attempt_000002.json"
)

SYMBOL = "USDJPY"


def prohibited_execution_call(*args, **kwargs):
    raise RuntimeError(
        "SHADOW_LIVE_EXECUTION_GUARD_TRIGGERED"
    )


def main() -> None:
    original_order_send = getattr(
        mt5,
        "order_send",
        None,
    )

    original_order_check = getattr(
        mt5,
        "order_check",
        None,
    )

    try:
        mt5.order_send = (
            prohibited_execution_call
        )

        if hasattr(mt5, "order_check"):
            mt5.order_check = (
                prohibited_execution_call
            )

        result = LiveMarketObserver.observe(
            symbol=SYMBOL,
        )

        safety = result["safety"]
        audit = result["audit"]
        authority = result["time_authority"]

        if not safety["shadow_observation_allowed"]:
            authority_status = (
                authority[
                    "time_authority"
                ]["status"]
            )

            sync_status = (
                result[
                    "time_synchronization"
                ]["status"]
            )

            raise RuntimeError(
                "SHADOW_LIVE_TIME_AUTHORITY_BLOCKED: "
                f"authority={authority_status}; "
                f"sync={sync_status}"
            )

        if not safety["read_only_mode"]:
            raise RuntimeError(
                "READ_ONLY_MODE_NOT_CONFIRMED"
            )

        if safety["real_order_send_allowed"]:
            raise RuntimeError(
                "REAL_ORDER_SEND_MUST_BE_DISABLED"
            )

        if safety["virtual_order_send_allowed"]:
            raise RuntimeError(
                "VIRTUAL_ORDER_SEND_MUST_BE_DISABLED_IN_H14_1"
            )

        if audit["order_send_called"]:
            raise RuntimeError(
                "ORDER_SEND_CALL_DETECTED"
            )

        if audit["orders_sent"]:
            raise RuntimeError(
                "ORDER_SENT_DETECTED"
            )

        if audit["positions_modified"]:
            raise RuntimeError(
                "POSITION_MODIFICATION_DETECTED"
            )

        if audit["true_oos_data_accessed"]:
            raise RuntimeError(
                "TRUE_OOS_ACCESS_DETECTED"
            )

        if audit["true_oos_artifacts_modified"]:
            raise RuntimeError(
                "TRUE_OOS_MODIFICATION_DETECTED"
            )

        report = {
            "sprint": "92H.14.1",
            "mode": "SHADOW_LIVE_READ_ONLY",
            "symbol": SYMBOL,
            "observer": result,
            "hard_execution_guard": {
                "order_send_guard_installed": True,
                "order_check_guard_installed": (
                    original_order_check
                    is not None
                ),
                "guard_triggered": False,
            },
            "audit": {
                "real_order_send_allowed": False,
                "virtual_order_send_allowed": False,
                "orders_sent": False,
                "positions_modified": False,
                "true_oos_data_accessed": False,
                "true_oos_artifacts_modified": False,
            },
        }

        REPORT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if REPORT_PATH.exists():
            raise RuntimeError(
                "H14_1_REPORT_ALREADY_EXISTS"
            )

        REPORT_PATH.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            "STATUS",
            "SHADOW_LIVE_OBSERVATION_PASS",
        )
        print(
            "SYMBOL",
            result["symbol"],
        )
        print(
            "BID",
            result["tick"]["bid"],
        )
        print(
            "ASK",
            result["tick"]["ask"],
        )
        print(
            "SPREAD_POINTS",
            result["tick"][
                "spread_points_observed"
            ],
        )
        print(
            "TIME_AUTHORITY_STATUS",
            authority[
                "time_authority"
            ]["status"],
        )
        print(
            "BROKER_OFFSET",
            authority[
                "observation"
            ][
                "detected_broker_offset_label"
            ],
        )
        print(
            "BAR_SYNC_STATUS",
            result[
                "time_synchronization"
            ]["status"],
        )
        print(
            "BAR_SYNC_ATTEMPTS",
            result[
                "time_synchronization"
            ]["attempts"],
        )
        print(
            "M15_BAR_TIME",
            result[
                "current_m15_bar"
            ]["time"],
        )
        print(
            "OPEN_POSITIONS",
            result[
                "exposure_observation"
            ][
                "open_position_count"
            ],
        )
        print(
            "PENDING_ORDERS",
            result[
                "exposure_observation"
            ][
                "pending_order_count"
            ],
        )
        print(
            "REAL_ORDER_SEND_ALLOWED",
            False,
        )
        print(
            "ORDER_SEND_CALLED",
            False,
        )
        print(
            "ORDERS_SENT",
            False,
        )
        print(
            "TRUE_OOS_ACCESSED",
            False,
        )
        print(
            "REPORT",
            str(REPORT_PATH),
        )

    finally:
        if original_order_send is not None:
            mt5.order_send = (
                original_order_send
            )

        if original_order_check is not None:
            mt5.order_check = (
                original_order_check
            )


if __name__ == "__main__":
    main()
