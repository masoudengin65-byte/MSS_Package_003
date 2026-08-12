"""Offline immutable Development-only replay for Sprint 92H.4."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path

from mss.analysis.historical_depth_audit import HistoricalDepthAudit
from mss.analysis.immutable_research_data_store import ImmutableResearchDataStore
from mss.analysis.multi_asset_historical_replay_v2 import MultiAssetHistoricalReplayV2
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata, HistoricalBacktestConfig


class ImmutableDevelopmentReplay:
    VERSION = "MSS_SPRINT92H4_IMMUTABLE_DEVELOPMENT_REPLAY_V1"

    def __init__(self):
        self.replay = MultiAssetHistoricalReplayV2()

    @staticmethod
    def config():
        return HistoricalBacktestConfig(
            warmup_candles=200,
            analysis_lookback=500,
            starting_balance=10000.0,
            risk_percent=1.0,
            reward_risk_ratio=2.0,
            spread_points=None,
            commission_per_lot=0.0,
            slippage_points=1.0,
            ambiguous_policy="STOP_LOSS_FIRST",
        )

    @staticmethod
    def candle(row):
        return Candle(
            time=datetime.fromtimestamp(int(row["time"])),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            tick_volume=int(row["tick_volume"]),
            spread=int(row["spread"]),
            real_volume=int(row["real_volume"]),
        )

    @staticmethod
    def metadata(row):
        return BacktestSymbolMetadata(
            account_currency=row["account_currency"],
            currency_base=row["currency_base"],
            currency_profit=row["currency_profit"],
            currency_margin=row["currency_margin"],
            trade_calc_mode=int(row["trade_calc_mode"]),
            point=float(row["point"]),
            digits=int(row["digits"]),
            tick_size=float(row["tick_size"]),
            tick_value=float(row["tick_value"]),
            contract_size=float(row["contract_size"]),
            volume_min=float(row["volume_min"]),
            volume_max=float(row["volume_max"]),
            volume_step=float(row["volume_step"]),
            spread_points=float(row["spread_points"]),
        )

    def load_verified_sources(self, root, protocol):
        histories = {}
        verification = []

        for spec in protocol["dataset_contract"]["symbols"]:
            symbol = spec["canonical_symbol"]
            path = Path(root) / spec["relative_path"]

            if not path.exists():
                raise RuntimeError(f"{symbol}: immutable source missing: {path}")

            actual_file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_file_hash != spec["file_sha256"]:
                raise RuntimeError(f"{symbol}: pre-parse file SHA256 mismatch")

            rows = ImmutableResearchDataStore.read_jsonl(path)

            actual_ohlcv_hash = HistoricalDepthAudit.candle_hash(rows)

            checks = {
                "file_sha256_match": actual_file_hash == spec["file_sha256"],
                "row_count_match": len(rows) == spec["row_count"] == 30000,
                "first_epoch_match": bool(rows) and rows[0]["time"] == spec["first_epoch"],
                "last_epoch_match": bool(rows) and rows[-1]["time"] == spec["last_epoch"],
                "ohlcv_sha256_match": actual_ohlcv_hash == spec["ohlcv_sha256"],
                "strictly_chronological": all(
                    rows[i]["time"] < rows[i + 1]["time"]
                    for i in range(len(rows) - 1)
                ),
            }

            if not all(checks.values()):
                raise RuntimeError(
                    f"{symbol}: immutable source verification failed: {checks}"
                )

            histories[symbol] = [self.candle(row) for row in rows]

            verification.append(
                {
                    "canonical_symbol": symbol,
                    "relative_path": spec["relative_path"],
                    "file_sha256": actual_file_hash,
                    "ohlcv_sha256": actual_ohlcv_hash,
                    "row_count": len(rows),
                    "first_epoch": rows[0]["time"],
                    "last_epoch": rows[-1]["time"],
                    **checks,
                }
            )

        if set(histories) != set(self.replay.SYMBOLS):
            raise RuntimeError("all-eight immutable source gate failed")

        return histories, verification

    def frozen_metadata(self, protocol):
        rows = {
            row["canonical_symbol"]: row
            for row in protocol["broker_metadata_contract"]["symbols"]
        }

        if set(rows) != set(self.replay.SYMBOLS):
            raise RuntimeError("frozen metadata universe mismatch")

        return {
            symbol: self.metadata(rows[symbol])
            for symbol in self.replay.SYMBOLS
        }

    def summarize(self, histories, metadata, results, source_verification, protocol):
        config = self.config()
        per_symbol = []
        trades = []
        risk_rows = []
        fx_rows = []

        protocol_rows = {
            row["canonical_symbol"]: row
            for row in protocol["dataset_contract"]["symbols"]
        }

        for symbol in self.replay.SYMBOLS:
            result = results[symbol]
            closed = [
                trade for trade in result.trades
                if trade.status == "CLOSED"
            ]

            metrics = self.replay.metrics(
                result,
                closed,
                config.starting_balance,
            )
            risk = self.replay.risk(
                closed,
                config.starting_balance,
                config.risk_percent,
            )

            meta = metadata[symbol]
            source = protocol_rows[symbol]

            row = {
                "canonical_symbol": symbol,
                "broker_symbol": source["broker_symbol"],
                "asset_class": self.replay.CLASSES[symbol],
                "source_candles": len(histories[symbol]),
                "data_start": histories[symbol][0].time.isoformat(),
                "data_end": histories[symbol][-1].time.isoformat(),
                "decisions": result.diagnostics.decisions_generated,
                "buy_signals": result.diagnostics.buy_signals,
                "sell_signals": result.diagnostics.sell_signals,
                "wait_results": result.diagnostics.wait_results,
                "opened_trades": result.diagnostics.opened_trades,
                "closed_trades": result.diagnostics.closed_trades,
                "unresolved_trades": result.diagnostics.unresolved_trades,
                "rejected_trades": result.diagnostics.rejected_trades,
                "rejection_reasons": dict(
                    sorted(result.diagnostics.rejection_reasons.items())
                ),
                **metrics,
                "risk_audit": risk,
            }

            per_symbol.append(row)
            risk_rows.append(
                {"canonical_symbol": symbol, **risk}
            )

            fx_rows.append(
                self.replay.fx_audit(
                    symbol,
                    meta,
                    closed,
                    histories[symbol],
                )
            )

            trades.extend(
                self.replay.trade_rows(
                    symbol,
                    source["broker_symbol"],
                    result.trades,
                )
            )

        groups = [
            self.replay.aggregate(
                name,
                [row for row in per_symbol if row["asset_class"] == name],
            )
            for name in ("FOREX", "METAL", "CRYPTO")
        ]

        combined = self.replay.aggregate("COMBINED", per_symbol)

        for row in per_symbol:
            row.pop("_r_multiples", None)

        return {
            "schema_version": self.VERSION,
            "mode": "IMMUTABLE_OFFLINE_DEVELOPMENT_ONLY_REPLAY",
            "baseline_commit": "5602790",
            "configuration": {
                **asdict(config),
                "timeframe": "M15",
                "segment": "DEVELOPMENT_ONLY",
                "symbols": 8,
                "candles_per_symbol": 30000,
                "combined_starting_capital": 80000.0,
                "parameter_optimization_performed": False,
                "paper_trading_only": True,
                "real_orders_sent": False,
            },
            "source": {
                "authority": "SPRINT_92H3_PREREGISTERED_IMMUTABLE_SOURCES",
                "storage_root": protocol["dataset_contract"]["storage_root"],
                "total_candles": 240000,
                "source_verification": source_verification,
                "mt5_fallback_used": False,
                "fresh_broker_history_used": False,
                "validation_accessed": False,
                "external_history_accessed": False,
                "true_future_oos_used": False,
            },
            "broker_metadata": [
                {
                    "canonical_symbol": symbol,
                    **asdict(metadata[symbol]),
                }
                for symbol in self.replay.SYMBOLS
            ],
            "per_symbol_results": per_symbol,
            "asset_class_results": groups,
            "combined_independent_results": combined,
            "risk_audit": risk_rows,
            "historical_fx_conversion": fx_rows,
            "trades": trades,
            "diagnostics": {
                "symbol_count": 8,
                "source_candle_count": sum(len(x) for x in histories.values()),
                "closed_trade_count": sum(
                    x["closed_trades"] for x in per_symbol
                ),
                "unresolved_trade_count": sum(
                    x["unresolved_trades"] for x in per_symbol
                ),
                "strategy_replay_count": 1,
                "symbol_runs": 8,
            },
            "audit": {
                "preregistration_schema": protocol["schema_version"],
                "strategy_parameters_changed": False,
                "strategy_implementation_changed": False,
                "metadata_source_frozen": True,
                "mt5_import_or_adapter_used": False,
                "current_symbol_info_used": False,
                "fresh_history_used": False,
                "validation_accessed": False,
                "external_history_accessed": False,
                "true_future_oos_used": False,
                "outcome_peeking_before_authoritative_run": False,
                "authoritative_development_replay_runs": 1,
                "real_orders_sent": False,
            },
            "acceptance": {
                "all_eight_sources_verified": len(source_verification) == 8
                    and all(
                        all(
                            value is True
                            for key, value in row.items()
                            if key.endswith("_match")
                            or key == "strictly_chronological"
                        )
                        for row in source_verification
                    ),
                "all_eight_symbols_replayed": len(per_symbol) == 8,
                "all_sources_exactly_30000": all(
                    row["source_candles"] == 30000
                    for row in per_symbol
                ),
                "mt5_fallback_used": False,
                "validation_accessed": False,
                "external_history_accessed": False,
                "true_future_oos_used": False,
                "strategy_behavior_unchanged": True,
                "real_orders_sent": False,
            },
        }
