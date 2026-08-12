"""Lock the one-time post-preregistration USDJPY M15 true-OOS anchor."""

from __future__ import annotations

from mss.analysis.historical_depth_audit import HistoricalDepthAudit


class TrueOosAnchorLock:
    VERSION = "MSS_SPRINT92H10_ONE_TIME_TRUE_OOS_ANCHOR_LOCK_V1"

    SYMBOL = "USDJPY"
    BROKER_SYMBOL = "USDJPY"
    TIMEFRAME = "M15"
    TIMEFRAME_SECONDS = 900

    def build(self, h9, anchor_epoch):
        if h9["schema_version"] != (
            "MSS_SPRINT92H9_RAW_IMMUTABLE_TRUE_OOS_PREREGISTRATION_V2"
        ):
            raise RuntimeError("unexpected H9 schema")

        if h9["execution_id"] != (
            "MSS_92H9_USDJPY_RAW_IMMUTABLE_TRUE_OOS_V2"
        ):
            raise RuntimeError("unexpected H9 execution id")

        if h9["new_boundary_contract"]["exact_timestamp_locked_in_h9"]:
            raise RuntimeError("H9 unexpectedly already locked the boundary")

        anchor_epoch = int(anchor_epoch)

        if anchor_epoch <= 0:
            raise RuntimeError("invalid anchor epoch")

        if anchor_epoch % self.TIMEFRAME_SECONDS != 0:
            raise RuntimeError("USDJPY M15 anchor is not aligned to 15 minutes")

        anchor_iso = HistoricalDepthAudit._iso(anchor_epoch)

        return {
            "schema_version": self.VERSION,
            "mode": (
                "ONE_TIME_POST_PREREGISTRATION_MT5_ANCHOR_LOCK_ONLY"
            ),
            "baseline_commit": "1011c0f",
            "execution_id": h9["execution_id"],

            "anchor": {
                "canonical_symbol": self.SYMBOL,
                "broker_symbol": self.BROKER_SYMBOL,
                "timeframe": self.TIMEFRAME,
                "boundary_epoch": anchor_epoch,
                "boundary_timestamp": anchor_iso,
                "boundary_source": (
                    "ALPARI_MT5_CURRENT_USDJPY_M15_BAR_OPEN"
                ),
                "observation_stage": "SPRINT92H10",
                "observed_after_h9_commit": True,
                "first_eligible_completed_candle_rule": (
                    "CANDLE_OPEN_TIMESTAMP_GREATER_THAN_OR_EQUAL_TO_"
                    "THE_LOCKED_H10_BOUNDARY"
                ),
            },

            "future_ledger_contract": {
                "required_completed_candles": (
                    h9["immutable_accrual_contract"]
                    ["required_completed_candles"]
                ),
                "first_eligible_open_timestamp": anchor_iso,
                "storage_model": (
                    h9["immutable_accrual_contract"]["storage_model"]
                ),
                "ledger_created_in_h10": False,
                "completed_true_oos_rows_written_in_h10": 0,
                "next_stage": (
                    "SPRINT92H11_APPEND_ONLY_TRUE_OOS_LEDGER_INITIALIZATION"
                ),
            },

            "data_access": {
                "mt5_accessed": True,
                "purpose": "CURRENT_BAR_OPEN_TIMESTAMP_ANCHOR_ONLY",
                "current_bar_record_requested": True,
                "current_bar_ohlcv_retained": False,
                "completed_history_requested": False,
                "completed_true_oos_candles_acquired": 0,
                "true_oos_ledger_rows_written": 0,
            },

            "governance": {
                "anchor_acquisition_count": 1,
                "anchor_replacement_prohibited": True,
                "anchor_refresh_prohibited": True,
                "legacy_h7_boundary_reuse": False,
                "legacy_h7_prefix_reuse": False,
                "strategy_replay_authorized": False,
                "outcome_access_authorized": False,
                "production_change_authorized": False,
            },

            "audit": {
                "strategy_pipeline_imported": False,
                "strategy_replay_run": False,
                "signals_generated": False,
                "trades_generated": False,
                "pnl_computed": False,
                "outcomes_analyzed": False,
                "orders_sent": False,
                "production_behavior_changed": False,
            },

            "acceptance": {
                "new_boundary_locked": True,
                "boundary_m15_aligned": True,
                "boundary_observed_after_h9_commit": True,
                "one_time_anchor_only": True,
                "no_completed_true_oos_data_acquired": True,
                "no_strategy_replay": True,
                "no_outcome_inspection": True,
                "no_orders": True,
                "production_change_justified": False,
            },
        }
