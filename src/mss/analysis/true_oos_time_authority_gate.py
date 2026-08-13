"""Global-time gate for broker-agnostic True-OOS accrual."""

from __future__ import annotations

import time

import MetaTrader5 as mt5

from mss.analysis.global_time_authority import (
    GlobalTimeAuthority,
)


class TrueOosTimeAuthorityGate:
    VERSION = "MSS_SPRINT92H13_3_TRUE_OOS_TIME_AUTHORITY_GATE_V1"

    SYMBOL = "USDJPY"
    TIMEFRAME_SECONDS = 900

    SYNC_TIMEOUT_SECONDS = 15.0
    SYNC_POLL_SECONDS = 0.25

    @classmethod
    def synchronized_snapshot(
        cls,
        previous_broker_offset_seconds=None,
    ):
        started = time.monotonic()

        attempts = 0
        first_observation = None
        final_observation = None

        while True:
            attempts += 1

            utc_before = time.time()

            tick = mt5.symbol_info_tick(
                cls.SYMBOL
            )

            bars = mt5.copy_rates_from_pos(
                cls.SYMBOL,
                mt5.TIMEFRAME_M15,
                0,
                3,
            )

            utc_after = time.time()

            if tick is None:
                raise RuntimeError(
                    f"{cls.SYMBOL} tick unavailable: "
                    f"{mt5.last_error()}"
                )

            if bars is None or len(bars) < 1:
                raise RuntimeError(
                    f"{cls.SYMBOL} M15 bars unavailable: "
                    f"{mt5.last_error()}"
                )

            tick_epoch = int(
                tick.time
            )

            expected_bar_epoch = (
                tick_epoch
                // cls.TIMEFRAME_SECONDS
            ) * cls.TIMEFRAME_SECONDS

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
                    // cls.TIMEFRAME_SECONDS
                ),
            }

            if first_observation is None:
                first_observation = dict(
                    observation
                )

            final_observation = dict(
                observation
            )

            synchronized = (
                current_bar_epoch
                == expected_bar_epoch
            )

            elapsed = (
                time.monotonic()
                - started
            )

            if synchronized:
                sync_status = (
                    "MT5_BAR_SYNCHRONIZED"
                )
                break

            if (
                elapsed
                >= cls.SYNC_TIMEOUT_SECONDS
            ):
                sync_status = (
                    "MT5_BAR_SYNC_TIMEOUT"
                )
                break

            time.sleep(
                cls.SYNC_POLL_SECONDS
            )

        authority = (
            GlobalTimeAuthority()
            .build(
                utc_epoch_before_tick=(
                    utc_before
                ),
                utc_epoch_after_tick=(
                    utc_after
                ),
                tick_epoch=(
                    tick_epoch
                ),
                current_bar_epoch=(
                    current_bar_epoch
                ),
                previous_broker_offset_seconds=(
                    previous_broker_offset_seconds
                ),
            )
        )

        if (
            sync_status
            != "MT5_BAR_SYNCHRONIZED"
        ):
            authority[
                "time_authority"
            ]["status"] = (
                "BROKER_BAR_SYNCHRONIZATION_UNRESOLVED"
            )

            authority[
                "time_authority"
            ]["confirmed"] = False

            authority[
                "fail_safe"
            ][
                "trading_allowed_by_time_authority"
            ] = False

        confirmed = (
            authority[
                "time_authority"
            ]["status"]
            == "BROKER_TIME_DOMAIN_CONFIRMED"
            and authority[
                "time_authority"
            ]["confirmed"]
            is True
            and authority[
                "fail_safe"
            ][
                "trading_allowed_by_time_authority"
            ]
            is True
            and sync_status
            == "MT5_BAR_SYNCHRONIZED"
        )

        return {
            "schema_version": (
                cls.VERSION
            ),

            "gate_confirmed": confirmed,

            "sync": {
                "status": sync_status,
                "attempts": attempts,
                "elapsed_seconds": elapsed,
                "timeout_seconds": (
                    cls.SYNC_TIMEOUT_SECONDS
                ),
                "poll_seconds": (
                    cls.SYNC_POLL_SECONDS
                ),
                "first_observation": (
                    first_observation
                ),
                "final_observation": (
                    final_observation
                ),
            },

            "current_bar_epoch": (
                current_bar_epoch
            ),

            "detected_broker_offset_seconds": (
                authority[
                    "observation"
                ][
                    "detected_broker_offset_seconds"
                ]
            ),

            "detected_broker_offset_label": (
                authority[
                    "observation"
                ][
                    "detected_broker_offset_label"
                ]
            ),

            "authority": authority,

            "fail_safe": {
                "ledger_write_allowed": (
                    confirmed
                ),
                "unresolved_time_blocks_accrual": (
                    True
                ),
                "raw_mt5_time_preserved": (
                    True
                ),
            },
        }

    @staticmethod
    def require_confirmed(
        gate,
    ):
        if not gate["gate_confirmed"]:
            status = (
                gate["authority"]
                ["time_authority"]
                ["status"]
            )

            sync_status = (
                gate["sync"]["status"]
            )

            raise RuntimeError(
                "TRUE_OOS_TIME_AUTHORITY_GATE_BLOCKED: "
                f"authority={status}; "
                f"sync={sync_status}; "
                "NO_LEDGER_WRITE"
            )

        return True
