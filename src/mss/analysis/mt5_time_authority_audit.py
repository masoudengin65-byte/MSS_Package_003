"""Formalize MT5 broker-clock authority before True-OOS accrual."""

from __future__ import annotations


class Mt5TimeAuthorityAudit:
    VERSION = "MSS_SPRINT92H11_1_MT5_TIME_AUTHORITY_AUDIT_V1"

    EXPECTED_OFFSET_SECONDS = 10800
    OFFSET_TOLERANCE_SECONDS = 15
    M15_SECONDS = 900

    def build(
        self,
        h10,
        h11,
        windows_utc_epoch,
        tick_epoch,
        current_bar_epoch,
    ):
        if h10["schema_version"] != (
            "MSS_SPRINT92H10_ONE_TIME_TRUE_OOS_ANCHOR_LOCK_V1"
        ):
            raise RuntimeError("unexpected H10 schema")

        if h11["schema_version"] != (
            "MSS_SPRINT92H11_APPEND_ONLY_TRUE_OOS_LEDGER_INITIALIZATION_V1"
        ):
            raise RuntimeError("unexpected H11 schema")

        if h10["execution_id"] != h11["execution_id"]:
            raise RuntimeError("H10/H11 execution identity mismatch")

        windows_utc_epoch = int(windows_utc_epoch)
        tick_epoch = int(tick_epoch)
        current_bar_epoch = int(current_bar_epoch)

        observed_offset = tick_epoch - windows_utc_epoch

        offset_near_three_hours = (
            abs(
                observed_offset
                - self.EXPECTED_OFFSET_SECONDS
            )
            <= self.OFFSET_TOLERANCE_SECONDS
        )

        expected_bar_epoch = (
            tick_epoch // self.M15_SECONDS
        ) * self.M15_SECONDS

        bar_matches_broker_clock = (
            current_bar_epoch
            == expected_bar_epoch
        )

        bar_m15_aligned = (
            current_bar_epoch % self.M15_SECONDS
            == 0
        )

        raw_anchor_epoch = int(
            h10["anchor"]["boundary_epoch"]
        )

        normalized_anchor_epoch = (
            raw_anchor_epoch
            - self.EXPECTED_OFFSET_SECONDS
        )

        if not offset_near_three_hours:
            status = "BROKER_OFFSET_UNRESOLVED"
        elif not bar_matches_broker_clock:
            status = "BROKER_BAR_TIME_DOMAIN_MISMATCH"
        elif not bar_m15_aligned:
            status = "BROKER_BAR_ALIGNMENT_FAILURE"
        else:
            status = "BROKER_TIME_DOMAIN_CONFIRMED"

        return {
            "schema_version": self.VERSION,
            "mode": (
                "READ_ONLY_MT5_TIME_AUTHORITY_AUDIT_"
                "NO_CANDLE_ACCRUAL_NO_REPLAY_NO_OUTCOMES"
            ),
            "baseline_commit": "c57ab9b",
            "execution_id": h10["execution_id"],

            "observation": {
                "windows_utc_epoch": windows_utc_epoch,
                "mt5_tick_epoch": tick_epoch,
                "mt5_current_m15_bar_epoch": current_bar_epoch,
                "observed_tick_minus_windows_seconds": observed_offset,
                "expected_broker_offset_seconds": (
                    self.EXPECTED_OFFSET_SECONDS
                ),
                "offset_tolerance_seconds": (
                    self.OFFSET_TOLERANCE_SECONDS
                ),
                "offset_near_three_hours": (
                    offset_near_three_hours
                ),
                "expected_current_bar_epoch_from_tick": (
                    expected_bar_epoch
                ),
                "bar_matches_broker_clock": (
                    bar_matches_broker_clock
                ),
                "bar_m15_aligned": bar_m15_aligned,
            },

            "time_authority": {
                "status": status,
                "execution_time_domain": (
                    "RAW_MT5_BROKER_EPOCH_DOMAIN"
                ),
                "candle_ordering_authority": (
                    "RAW_MT5_TIME_FIELD"
                ),
                "boundary_comparison_authority": (
                    "RAW_MT5_TIME_FIELD"
                ),
                "broker_clock_observed_offset": (
                    "UTC_PLUS_03_APPROXIMATELY"
                ),
                "do_not_treat_raw_mt5_epoch_as_true_utc": True,
                "utc_normalization_for_human_reporting_only": True,
            },

            "h10_anchor_interpretation": {
                "raw_boundary_epoch": raw_anchor_epoch,
                "legacy_reported_label": (
                    h10["anchor"]["boundary_timestamp"]
                ),
                "legacy_z_suffix_is_true_utc_authority": False,
                "approx_normalized_utc_epoch": (
                    normalized_anchor_epoch
                ),
                "raw_anchor_remains_execution_boundary": True,
                "h10_anchor_replacement_required": False,
            },

            "h11_ledger_interpretation": {
                "genesis_manifest_remains_valid": True,
                "ledger_reinitialization_required": False,
                "future_rows_use_raw_mt5_time": True,
                "future_timestamp_comparisons_use_raw_mt5_time": True,
            },

            "h12_requirements": {
                "may_start_only_if_status_confirmed": (
                    status
                    == "BROKER_TIME_DOMAIN_CONFIRMED"
                ),
                "must_preserve_raw_mt5_time_field": True,
                "must_not_shift_stored_candle_epochs": True,
                "must_not_rewrite_h10_anchor": True,
                "may_add_normalized_utc_display_field_to_reports": True,
                "normalized_utc_must_not_drive_eligibility": True,
            },

            "audit": {
                "mt5_accessed": True,
                "market_time_metadata_only": True,
                "completed_true_oos_rows_written": 0,
                "ledger_modified": False,
                "strategy_replay_run": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
            },

            "acceptance": {
                "broker_offset_characterized": (
                    offset_near_three_hours
                ),
                "m15_bar_same_broker_time_domain": (
                    bar_matches_broker_clock
                ),
                "h10_anchor_preserved": True,
                "h11_genesis_preserved": True,
                "no_true_oos_candles_written": True,
                "no_replay": True,
                "no_outcome_inspection": True,
            },
        }
