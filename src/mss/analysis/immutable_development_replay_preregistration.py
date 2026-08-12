"""Preregister an immutable Development-only replay before outcome inspection."""

from __future__ import annotations

import hashlib
import json


class ImmutableDevelopmentReplayPreregistration:
    VERSION = "MSS_SPRINT92H3_IMMUTABLE_DEVELOPMENT_REPLAY_PREREGISTRATION_V1"

    SYMBOLS = (
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "XAUUSD",
        "BTCUSD",
        "ETHUSD",
    )

    METADATA_FIELDS = (
        "canonical_symbol",
        "broker_symbol",
        "asset_class",
        "account_currency",
        "currency_base",
        "currency_profit",
        "currency_margin",
        "trade_calc_mode",
        "point",
        "digits",
        "tick_size",
        "tick_value",
        "contract_size",
        "volume_min",
        "volume_max",
        "volume_step",
        "spread_points",
    )

    @staticmethod
    def digest(value):
        return hashlib.sha256(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()

    def build(
        self,
        h1,
        h2,
        v2,
        h1_file_sha256,
        h2_file_sha256,
        v2_file_sha256,
    ):
        h1_rows = {
            row["canonical_symbol"]: row
            for row in h1["dataset_scope"]["symbols"]
        }
        h2_rows = {
            row["canonical_symbol"]: row
            for row in h2["symbols"]
        }
        metadata_rows = {
            row["canonical_symbol"]: row
            for row in v2["broker_metadata"]
        }

        expected = set(self.SYMBOLS)

        if set(h1_rows) != expected:
            raise RuntimeError("H1 symbol universe mismatch")
        if set(h2_rows) != expected:
            raise RuntimeError("H2 symbol universe mismatch")
        if set(metadata_rows) != expected:
            raise RuntimeError("v2 broker metadata universe mismatch")

        if h2["summary"]["total_rows"] != 240000:
            raise RuntimeError("H2 total row count mismatch")
        if h2["summary"]["symbol_count"] != 8:
            raise RuntimeError("H2 symbol count mismatch")
        if not h2["summary"]["all_files_verified"]:
            raise RuntimeError("H2 files are not all verified")

        dataset = []
        frozen_metadata = []

        for symbol in self.SYMBOLS:
            prereg = h1_rows[symbol]
            stored = h2_rows[symbol]
            meta = metadata_rows[symbol]

            if stored["row_count"] != 30000:
                raise RuntimeError(f"{symbol}: expected 30000 rows")
            if not stored["verified"]:
                raise RuntimeError(f"{symbol}: H2 verification is false")
            if stored["ohlcv_sha256"] != prereg["expected_ohlcv_sha256"]:
                raise RuntimeError(f"{symbol}: H1/H2 OHLCV hash mismatch")
            if stored["canonical_symbol"] != prereg["canonical_symbol"]:
                raise RuntimeError(f"{symbol}: canonical symbol mismatch")
            if stored["broker_symbol"] != prereg["broker_symbol"]:
                raise RuntimeError(f"{symbol}: broker symbol mismatch")

            dataset.append(
                {
                    "canonical_symbol": symbol,
                    "broker_symbol": stored["broker_symbol"],
                    "asset_class": stored["asset_class"],
                    "relative_path": stored["relative_path"],
                    "row_count": stored["row_count"],
                    "first_epoch": stored["first_epoch"],
                    "last_epoch": stored["last_epoch"],
                    "ohlcv_sha256": stored["ohlcv_sha256"],
                    "file_sha256": stored["file_sha256"],
                    "file_size_bytes": stored["file_size_bytes"],
                }
            )

            frozen_metadata.append(
                {
                    field: meta.get(field)
                    for field in self.METADATA_FIELDS
                }
            )

        return {
            "schema_version": self.VERSION,
            "mode": "PREREGISTRATION_ONLY_NO_REPLAY_NO_OUTCOME_INSPECTION",
            "baseline_commit": "16b8530",
            "purpose": (
                "PREREGISTER_ONE_AUTHORITATIVE_REPLAY_USING_ONLY_"
                "IMMUTABLE_DEVELOPMENT_DATA_AND_FROZEN_BROKER_METADATA"
            ),
            "dataset_contract": {
                "segment": "DEVELOPMENT_ONLY",
                "timeframe": "M15",
                "symbol_count": 8,
                "candles_per_symbol": 30000,
                "total_candles": 240000,
                "storage_root": h2["storage_root"],
                "symbols": dataset,
            },
            "source_verification_contract": {
                "verify_file_sha256_before_parse": True,
                "verify_row_count_after_parse": True,
                "verify_first_epoch_after_parse": True,
                "verify_last_epoch_after_parse": True,
                "verify_ohlcv_sha256_after_parse": True,
                "all_eight_or_fail": True,
                "mt5_fallback_prohibited": True,
                "substitute_history_prohibited": True,
                "partial_replay_prohibited": True,
            },
            "broker_metadata_contract": {
                "source": "MSS_Multi_Asset_Historical_Replay_v2.json",
                "metadata_is_frozen": True,
                "current_mt5_symbol_info_access_prohibited": True,
                "current_tick_value_is_not_historical_valuation_authority": True,
                "symbols": frozen_metadata,
            },
            "strategy_contract": {
                "timeframe": "M15",
                "warmup_candles": 200,
                "analysis_lookback": 500,
                "starting_balance": 10000.0,
                "risk_percent": 1.0,
                "reward_risk_ratio": 2.0,
                "spread_points": None,
                "commission_per_lot": 0.0,
                "slippage_points": 1.0,
                "ambiguous_policy": "STOP_LOSS_FIRST",
                "entry": "NEXT_CANDLE_OPEN",
                "completed_candles_only": True,
                "historical_currency_conversion": True,
                "parameter_optimization": False,
                "score_tuning": False,
                "threshold_tuning": False,
                "signal_logic_changes": False,
                "paper_trading_only": True,
                "real_orders": False,
            },
            "execution_policy": {
                "authoritative_development_replay_runs": 1,
                "symbol_runs": 8,
                "all_eight_or_fail": True,
                "interim_peeking": False,
                "rerun_after_outcome_inspection_prohibited": True,
                "validation_access_prohibited": True,
                "external_history_access_prohibited": True,
                "true_future_oos_access_prohibited": True,
                "fresh_mt5_history_access_prohibited": True,
                "current_broker_metadata_access_prohibited": True,
            },
            "source_hashes": {
                "h1_payload_sha256": self.digest(h1),
                "h2_payload_sha256": self.digest(h2),
                "v2_payload_sha256": self.digest(v2),
                "h1_file_sha256": h1_file_sha256,
                "h2_file_sha256": h2_file_sha256,
                "v2_file_sha256": v2_file_sha256,
            },
            "audit": {
                "mt5_accessed": False,
                "broker_history_accessed": False,
                "current_broker_metadata_accessed": False,
                "strategy_replay_run": False,
                "outcomes_analyzed": False,
                "validation_accessed": False,
                "external_history_accessed": False,
                "true_future_oos_used": False,
                "strategy_behavior_changed": False,
                "real_orders_sent": False,
            },
        }
