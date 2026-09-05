"""Correct the historical MT5 UTC contract before any price acquisition."""

from __future__ import annotations

from typing import Mapping

from mss.analysis.shared_capital_portfolio_preregistration_v2 import (
    SharedCapitalPortfolioPreregistrationV2,
)


class SharedCapitalPortfolioPreregistrationV3(
    SharedCapitalPortfolioPreregistrationV2
):
    VERSION = "MSS_SPRINT93_3A_SHARED_CAPITAL_PORTFOLIO_PREREGISTRATION_V3"

    def build(self, source_replay: Mapping[str, object]) -> dict[str, object]:
        protocol = super().build(source_replay)
        protocol["schema_version"] = self.VERSION
        protocol["supersedes"] = {
            "schema_version": SharedCapitalPortfolioPreregistrationV2.VERSION,
            "reason": (
                "MetaTrader5 copy_rates_range returns UTC epochs; V2 broker-offset "
                "normalization was corrected before historical data access"
            ),
            "v2_history_downloaded": False,
            "v2_results_accessed": False,
        }
        acquisition = protocol["data_acquisition"]
        acquisition["timezone_contract"] = {
            "request_datetime_timezone": "UTC_AWARE",
            "returned_bar_epoch_domain": "UTC_PER_OFFICIAL_METATRADER5_API",
            "manual_broker_offset_applied": False,
            "local_timezone_conversion_applied": False,
            "start_inclusive_epoch_required": True,
            "end_exclusive_enforced_after_inclusive_API_response": True,
        }
        acquisition.pop("timezone_normalization")
        protocol["audit"].update({
            "manual_broker_offset_applied": False,
            "v2_history_downloaded": False,
        })
        return protocol
