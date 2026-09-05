"""Record the availability-constrained common window before the authoritative freeze."""

from __future__ import annotations

from typing import Mapping

from mss.analysis.shared_capital_portfolio_preregistration_v3 import (
    SharedCapitalPortfolioPreregistrationV3,
)


class SharedCapitalPortfolioPreregistrationV4(
    SharedCapitalPortfolioPreregistrationV3
):
    VERSION = "MSS_SPRINT93_3A_SHARED_CAPITAL_PORTFOLIO_PREREGISTRATION_V4"
    WINDOW_START_UTC = "2021-09-17T00:00:00Z"

    def build(self, source_replay: Mapping[str, object]) -> dict[str, object]:
        protocol = super().build(source_replay)
        protocol["schema_version"] = self.VERSION
        protocol["mode"] = "PREREGISTRATION_ONLY_NO_AUTHORITATIVE_DATASET_FREEZE_NO_REPLAY"
        protocol["supersedes"] = {
            "schema_version": SharedCapitalPortfolioPreregistrationV3.VERSION,
            "reason": (
                "The broker begins BITCOIN and ETHEREUM M15 history at "
                "2021-09-16T13:30:00Z; the first full common UTC day is used "
                "without inspecting any strategy outcome"
            ),
            "availability_assessment_read_only": True,
            "authoritative_raw_dataset_written": False,
            "strategy_or_replay_run": False,
        }
        window = protocol["core_universe"]["historical_window"]
        window["start_utc_inclusive"] = self.WINDOW_START_UTC
        window["calendar_years"] = "3_years_349_days"
        window["availability_basis"] = {
            "assessed_at_symbol_level": True,
            "common_start_required": True,
            "crypto_first_available_m15_utc": "2021-09-16T13:30:00Z",
            "first_full_common_utc_day": self.WINDOW_START_UTC,
            "outcomes_or_strategy_metrics_inspected": False,
        }
        window["annual_reporting_blocks"] = [
            {"start_utc_inclusive": "2021-09-17T00:00:00Z", "end_utc_exclusive": "2022-09-17T00:00:00Z"},
            {"start_utc_inclusive": "2022-09-17T00:00:00Z", "end_utc_exclusive": "2023-09-17T00:00:00Z"},
            {"start_utc_inclusive": "2023-09-17T00:00:00Z", "end_utc_exclusive": "2024-09-17T00:00:00Z"},
            {"start_utc_inclusive": "2024-09-17T00:00:00Z", "end_utc_exclusive": "2025-09-01T00:00:00Z"},
        ]
        protocol["audit"].update({
            "availability_assessment_read_only": True,
            "authoritative_raw_dataset_written": False,
            "outcomes_or_strategy_metrics_inspected": False,
        })
        return protocol
