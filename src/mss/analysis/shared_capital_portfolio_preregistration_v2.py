"""Preregister the four-year shared-capital replay before data acquisition."""

from __future__ import annotations

from typing import Mapping

from mss.analysis.shared_capital_portfolio_preregistration import (
    SharedCapitalPortfolioPreregistration,
)


class SharedCapitalPortfolioPreregistrationV2(
    SharedCapitalPortfolioPreregistration
):
    VERSION = "MSS_SPRINT93_3A_SHARED_CAPITAL_PORTFOLIO_PREREGISTRATION_V2"
    WINDOW_START_UTC = "2021-09-01T00:00:00Z"
    WINDOW_END_EXCLUSIVE_UTC = "2025-09-01T00:00:00Z"
    ANNUAL_BLOCKS = (
        ("2021-09-01T00:00:00Z", "2022-09-01T00:00:00Z"),
        ("2022-09-01T00:00:00Z", "2023-09-01T00:00:00Z"),
        ("2023-09-01T00:00:00Z", "2024-09-01T00:00:00Z"),
        ("2024-09-01T00:00:00Z", "2025-09-01T00:00:00Z"),
    )

    def build(self, source_replay: Mapping[str, object]) -> dict[str, object]:
        protocol = super().build(source_replay)
        protocol["schema_version"] = self.VERSION
        protocol["mode"] = (
            "PREREGISTRATION_ONLY_NO_FOUR_YEAR_DATA_ACCESS_NO_REPLAY"
        )
        protocol["supersedes"] = {
            "schema_version": SharedCapitalPortfolioPreregistration.VERSION,
            "reason": "V1 historical windows were too short for final robustness use",
            "v1_results_accessed": False,
        }
        core = protocol["core_universe"]
        core.pop("source_windows")
        core["historical_window"] = {
            "start_utc_inclusive": self.WINDOW_START_UTC,
            "end_utc_exclusive": self.WINDOW_END_EXCLUSIVE_UTC,
            "calendar_years": 4,
            "annual_reporting_blocks": [
                {"start_utc_inclusive": start, "end_utc_exclusive": end}
                for start, end in self.ANNUAL_BLOCKS
            ],
            "common_window_required_for_all_core_symbols": True,
            "completed_m15_candles_only": True,
            "warmup_candles_before_window": 500,
            "warmup_excluded_from_performance": True,
        }
        protocol["data_acquisition"] = {
            "status": "NOT_STARTED",
            "source": "DIRECT_MT5_READ_ONLY_HISTORICAL",
            "exact_broker_symbol_and_contract_metadata_frozen_per_symbol": True,
            "raw_rows_preserved_before_analysis": True,
            "per_symbol_raw_sha256_required": True,
            "duplicate_or_non_monotonic_epoch_policy": "FAIL",
            "missing_candle_policy": "REPORT_MARKET_CLOSURE_ELSE_FAIL",
            "insufficient_common_window_policy": "FAIL_CORE_REPLAY_NO_SHORTENING",
            "timezone_normalization": "BROKER_EPOCH_TO_UTC_WITH_FROZEN_OFFSET_EVIDENCE",
            "current_tick_values_as_historical_substitute": False,
        }
        protocol["validation_design"] = {
            "classification": "HISTORICAL_ROBUSTNESS_NOT_TRUE_FUTURE_OOS",
            "full_window_result": True,
            "annual_block_results": True,
            "baseline_candidate_paired_comparison": True,
            "minimum_closed_trades_full_window": 200,
            "minimum_closed_trades_per_annual_block": 30,
            "catastrophic_vetoes": [
                "balance_nonpositive",
                "maximum_drawdown_percent_above_35",
                "lookahead_or_timestamp_failure",
                "risk_limit_or_valuation_failure",
            ],
            "true_future_oos_authority": "SEPARATE_SPRINT93_2B_FORWARD_ONLY",
        }
        protocol["execution_policy"]["authoritative_primary_runs"] = 1
        protocol["execution_policy"]["window_shortening_after_data_access"] = False
        protocol["audit"].update({
            "four_year_history_downloaded": False,
            "four_year_prices_inspected": False,
            "four_year_replay_run": False,
            "sprint93_2b_forward_accessed_or_modified": False,
        })
        return protocol
