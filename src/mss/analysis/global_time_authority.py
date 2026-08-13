"""Broker-agnostic global time authority for MSS."""

from __future__ import annotations

from datetime import datetime, timezone


class GlobalTimeAuthority:
    VERSION = "MSS_SPRINT92H13_2_GLOBAL_TIME_AUTHORITY_V1"

    M15_SECONDS = 900

    # Worldwide civil offsets are safely representable on a 15-minute grid.
    OFFSET_GRID_SECONDS = 900

    # Broker/server UTC offset must remain within a plausible world range.
    MAX_ABS_OFFSET_SECONDS = 14 * 3600

    # Allows normal tick/network latency while rejecting stale time authority.
    MAX_TICK_RESIDUAL_SECONDS = 120

    # Standard seasonal broker/DST movement normally occurs in one-hour steps.
    NORMAL_OFFSET_CHANGE_SECONDS = {
        -3600,
        0,
        3600,
    }

    @staticmethod
    def round_offset(observed_seconds):
        observed_seconds = float(observed_seconds)

        return int(
            round(
                observed_seconds
                / GlobalTimeAuthority.OFFSET_GRID_SECONDS
            )
            * GlobalTimeAuthority.OFFSET_GRID_SECONDS
        )

    @staticmethod
    def offset_label(offset_seconds):
        offset_seconds = int(offset_seconds)

        sign = "+" if offset_seconds >= 0 else "-"

        absolute = abs(offset_seconds)

        hours = absolute // 3600
        minutes = (absolute % 3600) // 60

        return f"UTC{sign}{hours:02d}:{minutes:02d}"

    @staticmethod
    def system_context():
        local_now = datetime.now().astimezone()
        utc_now = datetime.now(timezone.utc)

        offset = local_now.utcoffset()

        if offset is None:
            raise RuntimeError(
                "system local UTC offset unavailable"
            )

        offset_seconds = int(
            offset.total_seconds()
        )

        return {
            "local_iso": local_now.isoformat(),
            "utc_iso": utc_now.isoformat(),
            "system_timezone_name": (
                local_now.tzname()
                or str(local_now.tzinfo)
            ),
            "system_utc_offset_seconds": (
                offset_seconds
            ),
            "system_utc_offset_label": (
                GlobalTimeAuthority.offset_label(
                    offset_seconds
                )
            ),
        }

    def build(
        self,
        utc_epoch_before_tick,
        utc_epoch_after_tick,
        tick_epoch,
        current_bar_epoch,
        previous_broker_offset_seconds=None,
    ):
        utc_epoch_before_tick = float(
            utc_epoch_before_tick
        )

        utc_epoch_after_tick = float(
            utc_epoch_after_tick
        )

        tick_epoch = int(tick_epoch)
        current_bar_epoch = int(
            current_bar_epoch
        )

        if (
            utc_epoch_after_tick
            < utc_epoch_before_tick
        ):
            raise RuntimeError(
                "UTC observation order failure"
            )

        utc_midpoint = (
            utc_epoch_before_tick
            + utc_epoch_after_tick
        ) / 2.0

        raw_observed_offset = (
            tick_epoch
            - utc_midpoint
        )

        detected_offset = self.round_offset(
            raw_observed_offset
        )

        residual_seconds = abs(
            raw_observed_offset
            - detected_offset
        )

        offset_plausible = (
            abs(detected_offset)
            <= self.MAX_ABS_OFFSET_SECONDS
        )

        tick_fresh_enough = (
            residual_seconds
            <= self.MAX_TICK_RESIDUAL_SECONDS
        )

        normalized_tick_utc_epoch = (
            tick_epoch
            - detected_offset
        )

        normalized_tick_age_seconds = (
            utc_midpoint
            - normalized_tick_utc_epoch
        )

        expected_bar_epoch = (
            tick_epoch // self.M15_SECONDS
        ) * self.M15_SECONDS

        bar_m15_aligned = (
            current_bar_epoch
            % self.M15_SECONDS
            == 0
        )

        bar_matches_broker_clock = (
            current_bar_epoch
            == expected_bar_epoch
        )

        offset_changed = False
        offset_change_seconds = 0
        offset_change_classification = (
            "NO_PREVIOUS_AUTHORITY"
        )

        previous_offset = None

        if previous_broker_offset_seconds is not None:
            previous_offset = int(
                previous_broker_offset_seconds
            )

            offset_change_seconds = (
                detected_offset
                - previous_offset
            )

            offset_changed = (
                offset_change_seconds != 0
            )

            if offset_change_seconds == 0:
                offset_change_classification = (
                    "UNCHANGED"
                )

            elif (
                offset_change_seconds
                in self.NORMAL_OFFSET_CHANGE_SECONDS
            ):
                offset_change_classification = (
                    "NORMAL_SEASONAL_OR_DST_CHANGE"
                )

            else:
                offset_change_classification = (
                    "NONSTANDARD_OFFSET_CHANGE"
                )

        if not offset_plausible:
            status = (
                "BROKER_OFFSET_OUTSIDE_PLAUSIBLE_RANGE"
            )

        elif not tick_fresh_enough:
            status = (
                "BROKER_TIME_AUTHORITY_STALE_OR_AMBIGUOUS"
            )

        elif not bar_m15_aligned:
            status = (
                "BROKER_BAR_ALIGNMENT_FAILURE"
            )

        elif not bar_matches_broker_clock:
            status = (
                "BROKER_BAR_TIME_DOMAIN_MISMATCH"
            )

        elif (
            offset_change_classification
            == "NONSTANDARD_OFFSET_CHANGE"
        ):
            status = (
                "BROKER_OFFSET_CHANGE_REQUIRES_REVIEW"
            )

        else:
            status = (
                "BROKER_TIME_DOMAIN_CONFIRMED"
            )

        authority_confirmed = (
            status
            == "BROKER_TIME_DOMAIN_CONFIRMED"
        )

        return {
            "schema_version": self.VERSION,

            "mode": (
                "BROKER_AGNOSTIC_GLOBAL_TIME_AUTHORITY_"
                "NO_REPLAY_NO_OUTCOMES"
            ),

            "observation": {
                "utc_epoch_before_tick": (
                    utc_epoch_before_tick
                ),
                "utc_epoch_after_tick": (
                    utc_epoch_after_tick
                ),
                "utc_midpoint_epoch": (
                    utc_midpoint
                ),
                "mt5_raw_tick_epoch": (
                    tick_epoch
                ),
                "mt5_raw_current_m15_bar_epoch": (
                    current_bar_epoch
                ),
                "raw_tick_minus_true_utc_seconds": (
                    raw_observed_offset
                ),
                "detected_broker_offset_seconds": (
                    detected_offset
                ),
                "detected_broker_offset_label": (
                    self.offset_label(
                        detected_offset
                    )
                ),
                "offset_rounding_grid_seconds": (
                    self.OFFSET_GRID_SECONDS
                ),
                "offset_residual_seconds": (
                    residual_seconds
                ),
                "normalized_tick_utc_epoch": (
                    normalized_tick_utc_epoch
                ),
                "normalized_tick_age_seconds": (
                    normalized_tick_age_seconds
                ),
                "offset_plausible": (
                    offset_plausible
                ),
                "tick_fresh_enough": (
                    tick_fresh_enough
                ),
                "expected_current_bar_epoch": (
                    expected_bar_epoch
                ),
                "bar_matches_broker_clock": (
                    bar_matches_broker_clock
                ),
                "bar_m15_aligned": (
                    bar_m15_aligned
                ),
            },

            "offset_change_monitor": {
                "previous_broker_offset_seconds": (
                    previous_offset
                ),
                "current_broker_offset_seconds": (
                    detected_offset
                ),
                "offset_changed": (
                    offset_changed
                ),
                "offset_change_seconds": (
                    offset_change_seconds
                ),
                "classification": (
                    offset_change_classification
                ),
            },

            "time_authority": {
                "status": status,
                "confirmed": authority_confirmed,

                "execution_time_domain": (
                    "RAW_MT5_BROKER_EPOCH_DOMAIN"
                ),

                "candle_ordering_authority": (
                    "RAW_MT5_TIME_FIELD"
                ),

                "boundary_comparison_authority": (
                    "RAW_MT5_TIME_FIELD"
                ),

                "broker_offset_detection": (
                    "AUTOMATIC_RUNTIME_DETECTION"
                ),

                "hardcoded_broker_offset": False,
                "hardcoded_system_timezone": False,
                "hardcoded_broker_identity": False,

                "utc_normalization_for_reporting_only": (
                    True
                ),

                "system_local_time_for_display_only": (
                    True
                ),

                "raw_mt5_timestamp_must_not_be_shifted": (
                    True
                ),
            },

            "portability": {
                "broker_agnostic": True,
                "country_agnostic": True,
                "system_timezone_agnostic": True,
                "dst_change_detectable": True,
                "broker_offset_change_detectable": True,
            },

            "fail_safe": {
                "trading_allowed_by_time_authority": (
                    authority_confirmed
                ),
                "unresolved_time_authority_blocks_trading": (
                    True
                ),
                "nonstandard_offset_change_blocks_trading": (
                    True
                ),
            },

            "audit": {
                "strategy_replay_run": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },
        }
