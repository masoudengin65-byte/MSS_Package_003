"""Correct the common UTC start after the V4 freeze stopped safely at XAUUSD."""

from __future__ import annotations

from typing import Mapping

from mss.analysis.shared_capital_portfolio_preregistration_v4 import (
    SharedCapitalPortfolioPreregistrationV4,
)


class SharedCapitalPortfolioPreregistrationV5(
    SharedCapitalPortfolioPreregistrationV4
):
    VERSION = "MSS_SPRINT93_3A_SHARED_CAPITAL_PORTFOLIO_PREREGISTRATION_V5"
    WINDOW_START_UTC = "2021-09-23T18:30:00Z"

    def build(self, source_replay: Mapping[str, object]) -> dict[str, object]:
        protocol = super().build(source_replay)
        protocol["schema_version"] = self.VERSION
        protocol["supersedes"] = {
            "schema_version": SharedCapitalPortfolioPreregistrationV4.VERSION,
            "reason": (
                "The first timestamp common to all eight symbols with at least "
                "500 preceding M15 candles is 2021-09-23T18:30:00Z. "
                "The earlier unpublished V5 draft had only 46 crypto warmup bars."
            ),
            "v4_partial_raw_files_preserved": True,
            "v4_partial_raw_files_eligible_for_analysis": False,
            "v4_authoritative_manifest_written": False,
            "strategy_or_replay_run": False,
        }
        window = protocol["core_universe"]["historical_window"]
        window["start_utc_inclusive"] = self.WINDOW_START_UTC
        window.pop("calendar_years", None)
        window["duration_description"] = "Nearly four years; final annual block is shorter"
        window["availability_basis"] = {
            "assessed_at_symbol_level": True,
            "common_start_required": True,
            "crypto_first_available_m15_utc": "2021-09-16T13:30:00Z",
            "xauusd_first_m15_on_first_crypto_full_day_utc": "2021-09-17T01:00:00Z",
            "first_common_timestamp_with_500_preceding_candles_utc": self.WINDOW_START_UTC,
            "timestamp_preflight_report": "MSS_Sprint93_3A_Warmup_Preflight_20260909.json",
            "outcomes_or_strategy_metrics_inspected": False,
        }
        window["annual_reporting_blocks"] = [
            {"start_utc_inclusive": "2021-09-23T18:30:00Z", "end_utc_exclusive": "2022-09-23T18:30:00Z"},
            {"start_utc_inclusive": "2022-09-23T18:30:00Z", "end_utc_exclusive": "2023-09-23T18:30:00Z"},
            {"start_utc_inclusive": "2023-09-23T18:30:00Z", "end_utc_exclusive": "2024-09-23T18:30:00Z"},
            {"start_utc_inclusive": "2024-09-23T18:30:00Z", "end_utc_exclusive": "2025-09-01T00:00:00Z"},
        ]
        protocol["audit"].update({
            "live_mt5_accessed": True,
            "four_year_history_downloaded": True,
            "authoritative_raw_dataset_written": False,
            "historical_access_scope": "Timestamp preflight and preserved incomplete V4 acquisition; no strategy outcomes",
            "v4_partial_raw_files_preserved": True,
            "v4_partial_raw_files_eligible_for_analysis": False,
            "v4_authoritative_manifest_written": False,
        })
        return protocol
