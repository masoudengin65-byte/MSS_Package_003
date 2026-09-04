"""Preregister the shared-capital multi-asset historical replay."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping


class SharedCapitalPortfolioPreregistration:
    VERSION = "MSS_SPRINT93_3A_SHARED_CAPITAL_PORTFOLIO_PREREGISTRATION_V1"
    CORE_SYMBOLS = (
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "XAUUSD",
        "BTCUSD", "ETHUSD",
    )
    EXTENSION_CANDIDATES = ("WTI", "NAS100", "SPX500", "XAGUSD")
    SYMBOL_PRIORITY = CORE_SYMBOLS

    @staticmethod
    def digest(value: object) -> str:
        payload = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def build(self, source_replay: Mapping[str, object]) -> dict[str, object]:
        universe = source_replay["universe"]
        symbols = tuple(row["canonical_symbol"] for row in universe)
        if symbols != self.CORE_SYMBOLS:
            raise RuntimeError("core universe or ordering differs from frozen replay")
        if source_replay.get("acceptance_status") != "PASS":
            raise RuntimeError("frozen replay source did not pass its integrity gate")

        return {
            "schema_version": self.VERSION,
            "mode": "PREREGISTRATION_ONLY_NO_SHARED_CAPITAL_REPLAY_RUN",
            "objective": (
                "Compare the frozen baseline and candidate under one chronological "
                "shared-capital account without post-outcome parameter selection."
            ),
            "core_universe": {
                "symbols": list(self.CORE_SYMBOLS),
                "symbol_priority": list(self.SYMBOL_PRIORITY),
                "timeframe": "M15",
                "source_windows": source_replay["source_windows"],
            },
            "account_model": {
                "currency": "USD",
                "primary_starting_balance": 100.0,
                "primary_risk_percent": 0.5,
                "maximum_risk_per_trade_percent": 1.0,
                "maximum_total_open_risk_percent": 2.0,
                "maximum_simultaneous_positions": 2,
                "maximum_positions_per_asset_class": 1,
                "shared_equity_updates_chronologically": True,
                "independent_symbol_accounts": False,
            },
            "sensitivity_scenarios": {
                "risk_percent": [0.25, 1.0],
                "starting_balance_usd": [500.0],
                "decision_use": "ROBUSTNESS_DESCRIPTION_ONLY_NO_PARAMETER_SELECTION",
            },
            "execution_contract": {
                "candidate_selection": "EARLIEST_UTC_THEN_FROZEN_SYMBOL_PRIORITY",
                "same_candle_exit_policy": "STOP_LOSS_FIRST",
                "entry": "NEXT_CANDLE_OPEN",
                "reward_risk_ratio": 2.0,
                "minimum_volume_policy": "REJECT_IF_BROKER_MINIMUM_EXCEEDS_RISK_CAP",
                "volume_step_policy": "ROUND_DOWN_AND_REJECT_IF_BELOW_MINIMUM",
                "missing_or_invalid_contract_metadata": "FAIL_CLOSED",
                "weekend_closed_symbols": "NO_SYNTHETIC_CANDLES_NO_BACKFILL",
                "parameter_optimization": False,
                "real_orders": False,
            },
            "extension_universe": {
                "candidates": list(self.EXTENSION_CANDIDATES),
                "status": "CONDITIONAL_SECONDARY_REPLAY_NOT_YET_AUTHORIZED",
                "required_before_inclusion": [
                    "exact broker symbol resolved",
                    "M15 historical depth and continuity pass",
                    "contract size tick size tick value minimum volume and volume step frozen",
                    "USD valuation path verified without current-value lookahead",
                ],
                "failure_policy": "EXCLUDE_FAILED_EXTENSION_WITH_REASON_CORE_REPLAY_UNCHANGED",
            },
            "reporting": {
                "primary": [
                    "ending_balance", "return_percent", "profit_factor",
                    "maximum_drawdown_percent", "closed_trades", "rejection_counts",
                ],
                "report_baseline_and_candidate": True,
                "report_all_sensitivity_results": True,
                "no_post_hoc_symbol_exclusion": True,
            },
            "execution_policy": {
                "authoritative_primary_runs": 1,
                "interim_peeking": False,
                "parameter_tuning_after_results": False,
                "failed_and_null_results_preserved": True,
                "rerun_after_outcome_access": False,
            },
            "source_hashes": {
                "source_replay_payload_sha256": self.digest(source_replay),
            },
            "audit": {
                "shared_capital_replay_run": False,
                "extension_market_data_accessed": False,
                "live_mt5_accessed": False,
                "real_orders_sent": False,
                "active_sprint93_2b_forward_modified": False,
            },
        }
