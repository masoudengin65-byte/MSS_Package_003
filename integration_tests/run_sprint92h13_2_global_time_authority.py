"""Run Sprint 92H.13.2 broker-agnostic global time authority audit."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import MetaTrader5 as mt5

from mss.analysis.global_time_authority import (
    GlobalTimeAuthority,
)


ROOT = Path(__file__).resolve().parents[1]

OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint92H13_2_Global_Time_Authority.json"
)

SYMBOL = "USDJPY"

SYNC_TIMEOUT_SECONDS = 15.0
SYNC_POLL_SECONDS = 0.25
M15_SECONDS = 900


def json_safe(value):
    if value is None:
        return None

    if hasattr(value, "_asdict"):
        return {
            key: json_safe(item)
            for key, item in value._asdict().items()
        }

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return str(value)


def find_previous_global_authority():
    candidates = sorted(
        ROOT.glob(
            "reports/"
            "MSS_Sprint92H13_2_Global_Time_Authority_*.json"
        )
    )

    candidates = [
        path
        for path in candidates
        if "PreSync_Failure" not in path.name
    ]

    if not candidates:
        return None

    latest = candidates[-1]

    payload = json.loads(
        latest.read_text(
            encoding="utf-8"
        )
    )

    offset = (
        payload
        .get("observation", {})
        .get(
            "detected_broker_offset_seconds"
        )
    )

    if offset is None:
        return None

    return {
        "path": str(
            latest.relative_to(ROOT)
        ).replace("\\", "/"),
        "sha256": hashlib.sha256(
            latest.read_bytes()
        ).hexdigest(),
        "broker_offset_seconds": int(
            offset
        ),
    }


def synchronized_mt5_snapshot():
    started = time.monotonic()

    attempts = 0
    first_observation = None
    last_observation = None

    while True:
        attempts += 1

        utc_before = time.time()

        tick = mt5.symbol_info_tick(
            SYMBOL
        )

        bars = mt5.copy_rates_from_pos(
            SYMBOL,
            mt5.TIMEFRAME_M15,
            0,
            3,
        )

        utc_after = time.time()

        if tick is None:
            raise RuntimeError(
                f"{SYMBOL} tick unavailable: "
                f"{mt5.last_error()}"
            )

        if bars is None or len(bars) < 1:
            raise RuntimeError(
                f"{SYMBOL} M15 bars unavailable: "
                f"{mt5.last_error()}"
            )

        tick_epoch = int(
            tick.time
        )

        expected_bar_epoch = (
            tick_epoch // M15_SECONDS
        ) * M15_SECONDS

        returned_epochs = [
            int(row["time"])
            for row in bars
        ]

        current_bar_epoch = max(
            returned_epochs
        )

        observation = {
            "attempt": attempts,
            "tick_epoch": tick_epoch,
            "expected_current_bar_epoch": (
                expected_bar_epoch
            ),
            "returned_bar_epochs": (
                returned_epochs
            ),
            "selected_current_bar_epoch": (
                current_bar_epoch
            ),
            "bar_lag_seconds": (
                expected_bar_epoch
                - current_bar_epoch
            ),
            "bar_lag_m15_candles": (
                (
                    expected_bar_epoch
                    - current_bar_epoch
                )
                // M15_SECONDS
            ),
        }

        if first_observation is None:
            first_observation = dict(
                observation
            )

        last_observation = dict(
            observation
        )

        if (
            current_bar_epoch
            == expected_bar_epoch
        ):
            elapsed = (
                time.monotonic()
                - started
            )

            return {
                "utc_before": utc_before,
                "utc_after": utc_after,
                "tick_epoch": tick_epoch,
                "current_bar_epoch": (
                    current_bar_epoch
                ),
                "sync": {
                    "status": (
                        "MT5_BAR_SYNCHRONIZED"
                    ),
                    "attempts": attempts,
                    "elapsed_seconds": elapsed,
                    "timeout_seconds": (
                        SYNC_TIMEOUT_SECONDS
                    ),
                    "poll_seconds": (
                        SYNC_POLL_SECONDS
                    ),
                    "first_observation": (
                        first_observation
                    ),
                    "final_observation": (
                        last_observation
                    ),
                },
            }

        elapsed = (
            time.monotonic()
            - started
        )

        if elapsed >= SYNC_TIMEOUT_SECONDS:
            return {
                "utc_before": utc_before,
                "utc_after": utc_after,
                "tick_epoch": tick_epoch,
                "current_bar_epoch": (
                    current_bar_epoch
                ),
                "sync": {
                    "status": (
                        "MT5_BAR_SYNC_TIMEOUT"
                    ),
                    "attempts": attempts,
                    "elapsed_seconds": elapsed,
                    "timeout_seconds": (
                        SYNC_TIMEOUT_SECONDS
                    ),
                    "poll_seconds": (
                        SYNC_POLL_SECONDS
                    ),
                    "first_observation": (
                        first_observation
                    ),
                    "final_observation": (
                        last_observation
                    ),
                },
            }

        time.sleep(
            SYNC_POLL_SECONDS
        )


def main():
    if OUTPUT.exists():
        raise RuntimeError(
            f"H13.2 output already exists: {OUTPUT}"
        )

    previous = (
        find_previous_global_authority()
    )

    previous_offset = (
        None
        if previous is None
        else previous[
            "broker_offset_seconds"
        ]
    )

    system_context = (
        GlobalTimeAuthority.system_context()
    )

    mt5.shutdown()

    # Intentionally no terminal path and no broker hardcoding.
    if not mt5.initialize(
        timeout=120_000,
    ):
        raise RuntimeError(
            "MT5 auto-discovery/initialization failed: "
            f"{mt5.last_error()}"
        )

    try:
        terminal_info = (
            mt5.terminal_info()
        )

        account_info = (
            mt5.account_info()
        )

        if terminal_info is None:
            raise RuntimeError(
                "MT5 terminal information unavailable"
            )

        if not mt5.symbol_select(
            SYMBOL,
            True,
        ):
            raise RuntimeError(
                f"{SYMBOL} unavailable: "
                f"{mt5.last_error()}"
            )

        snapshot = (
            synchronized_mt5_snapshot()
        )

        terminal_metadata = {
            "terminal": json_safe(
                terminal_info
            ),
            "account": json_safe(
                account_info
            ),
        }

    finally:
        mt5.shutdown()

    authority = (
        GlobalTimeAuthority()
    )

    payload = authority.build(
        utc_epoch_before_tick=(
            snapshot["utc_before"]
        ),
        utc_epoch_after_tick=(
            snapshot["utc_after"]
        ),
        tick_epoch=(
            snapshot["tick_epoch"]
        ),
        current_bar_epoch=(
            snapshot[
                "current_bar_epoch"
            ]
        ),
        previous_broker_offset_seconds=(
            previous_offset
        ),
    )

    payload["baseline_commit"] = (
        "a4320fe"
    )

    payload["symbol"] = SYMBOL

    payload["system_context"] = (
        system_context
    )

    payload["mt5_bar_synchronization"] = (
        snapshot["sync"]
    )

    payload["mt5_environment"] = {
        "terminal_auto_discovered": True,
        "hardcoded_terminal_path": False,
        "hardcoded_broker_name": False,
        "metadata": (
            terminal_metadata
        ),
    }

    payload["previous_authority"] = (
        previous
    )

    payload["governance"] = {
        "raw_mt5_time_preserved": True,
        "existing_h10_anchor_modified": False,
        "existing_true_oos_ledger_modified": False,
        "utc_normalization_used_for_eligibility": False,
        "local_system_time_used_for_eligibility": False,
        "time_authority_required_before_trading": True,
        "single_shot_bar_read_trusted": False,
        "bar_sync_required_before_confirmation": True,
    }

    if (
        snapshot["sync"]["status"]
        != "MT5_BAR_SYNCHRONIZED"
    ):
        payload["time_authority"][
            "status"
        ] = "BROKER_BAR_SYNCHRONIZATION_UNRESOLVED"

        payload["time_authority"][
            "confirmed"
        ] = False

        payload["fail_safe"][
            "trading_allowed_by_time_authority"
        ] = False

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
        "SYSTEM_TIMEZONE",
        payload["system_context"]
        ["system_timezone_name"],
    )

    print(
        "SYSTEM_UTC_OFFSET",
        payload["system_context"]
        ["system_utc_offset_label"],
    )

    print(
        "BROKER_OFFSET",
        payload["observation"]
        ["detected_broker_offset_label"],
    )

    print(
        "BROKER_OFFSET_SECONDS",
        payload["observation"]
        ["detected_broker_offset_seconds"],
    )

    print(
        "OFFSET_RESIDUAL_SECONDS",
        payload["observation"]
        ["offset_residual_seconds"],
    )

    print(
        "BAR_SYNC_STATUS",
        payload["mt5_bar_synchronization"]
        ["status"],
    )

    print(
        "BAR_SYNC_ATTEMPTS",
        payload["mt5_bar_synchronization"]
        ["attempts"],
    )

    print(
        "BAR_MATCHES_BROKER_CLOCK",
        payload["observation"]
        ["bar_matches_broker_clock"],
    )

    print(
        "OFFSET_CHANGE_CLASS",
        payload["offset_change_monitor"]
        ["classification"],
    )

    print(
        "TRADING_ALLOWED_BY_TIME_AUTHORITY",
        payload["fail_safe"]
        ["trading_allowed_by_time_authority"],
    )

    print(
        "TERMINAL_AUTO_DISCOVERED",
        payload["mt5_environment"]
        ["terminal_auto_discovered"],
    )

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
