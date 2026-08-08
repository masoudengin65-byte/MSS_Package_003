"""Sprint 91 diagnostic-only orchestration of the validated replay engine."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.analysis.multi_asset_dataset_builder import MultiAssetDatasetBuilder
from mss.analysis.multi_asset_registry import MultiAssetRegistry
from mss.domain.historical_backtest import (
    BacktestSymbolMetadata,
    HistoricalBacktestConfig,
)
from mss.domain.multi_asset_replay_result import MultiAssetReplayResult
from mss.domain.trade_statistics import TradeStatistics


class MultiAssetHistoricalReplay(MultiAssetRegistry):
    """Run independent-symbol research replays without a production consumer."""

    VERSION = "SPRINT_91_MULTI_ASSET_HISTORICAL_REPLAY_V1"
    MODE = "RESEARCH_ONLY"
    TIMEFRAME = "M15"
    TARGET_CANDLE_COUNT = 10000
    RESULT_KEYS = (
        "schema_version", "mode", "generated_as_of", "universe",
        "replay_configuration", "history_availability", "broker_metadata",
        "per_symbol_results", "asset_class_results",
        "combined_independent_results", "trades", "diagnostics", "audit",
        "production_change_justified",
    )
    HARD_QUALITY_FIELDS = (
        "future_candle_count", "duplicate_timestamp_count",
        "nonfinite_price_count", "invalid_ohlc_count",
        "negative_volume_count", "negative_spread_count",
    )

    def replay(
        self,
        history_results,
        broker_metadata,
        as_of,
        config=None,
        target_count=TARGET_CANDLE_COUNT,
        engine_factory=HistoricalBacktestEngine,
    ) -> MultiAssetReplayResult:
        """Validate a common M15 window, then reuse the historical engine."""
        config = config or HistoricalBacktestConfig()
        self._validate_config(config)
        target_count = int(target_count)
        if target_count <= config.warmup_candles:
            raise ValueError("Target count must exceed the replay warm-up")
        as_of = self._timestamp(as_of)
        history_results = history_results or {}
        broker_metadata = broker_metadata or {}
        input_before = self.input_sha256(history_results, broker_metadata, config)
        validator = MultiAssetDatasetBuilder()
        availability = []

        for definition in self.universe:
            canonical = definition.canonical_symbol
            payload = self._value(history_results, canonical, {}) or {}
            metadata_row = self._value(broker_metadata, canonical, {}) or {}
            broker_symbol = self._broker_symbol(metadata_row)
            coverage = validator.validate_history(
                definition, self.TIMEFRAME, payload, as_of,
                default_resolved=broker_symbol,
            )
            availability.append(coverage)
            self._require_replay_quality(coverage)

        common_count = self.choose_common_count(availability, target_count)
        if common_count <= config.warmup_candles:
            raise ValueError("Common history count does not exceed warm-up")

        replay_results = []
        selected_ranges = []
        for definition in self.universe:
            canonical = definition.canonical_symbol
            payload = self._value(history_results, canonical, {}) or {}
            candles = tuple(self._value(payload, "candles", ()) or ())
            selected = candles[-common_count:]
            metadata_row = self._value(broker_metadata, canonical, {}) or {}
            broker_symbol = self._broker_symbol(metadata_row)
            engine_metadata = self._engine_metadata(metadata_row)
            engine = engine_factory()
            result = engine.run(
                symbol=broker_symbol,
                timeframe=self.TIMEFRAME,
                candles=selected,
                config=config,
                metadata=engine_metadata,
            )
            if not result.valid:
                raise RuntimeError(f"Historical replay was invalid for {canonical}")
            if result.diagnostics.candles_loaded != common_count:
                raise RuntimeError(
                    f"Replay candle count changed for {canonical}: "
                    f"{result.diagnostics.candles_loaded} != {common_count}"
                )
            replay_results.append((definition, metadata_row, result))
            selected_ranges.append({
                "canonical_symbol": canonical,
                "broker_symbol": broker_symbol,
                "source_returned_count": len(candles),
                "selected_count": common_count,
                "first_candle_open_time": selected[0].time.isoformat(),
                "last_candle_open_time": selected[-1].time.isoformat(),
                "last_candle_close_time": (
                    selected[-1].time + self.DURATIONS[self.TIMEFRAME]
                ).isoformat(),
            })

        input_after = self.input_sha256(history_results, broker_metadata, config)
        if input_before != input_after:
            raise RuntimeError("Multi-asset replay mutated its input snapshot")
        generated_as_of = max(
            row[2].diagnostics.data_end + self.DURATIONS[self.TIMEFRAME]
            for row in replay_results
        )
        payload = self._build_payload(
            replay_results, availability, selected_ranges, config,
            target_count, common_count, generated_as_of, input_before,
        )
        self.validate_result_schema(payload)
        return MultiAssetReplayResult.create(payload)

    @classmethod
    def choose_common_count(cls, availability, target_count):
        counts = [int(row.get("observed_candle_count", 0)) for row in availability]
        if len(counts) != len(cls.TARGET_UNIVERSE) or any(count <= 0 for count in counts):
            raise ValueError("All registered symbols require M15 history")
        return min(int(target_count), min(counts))

    def _build_payload(
        self,
        replay_results,
        availability,
        selected_ranges,
        config,
        target_count,
        common_count,
        generated_as_of,
        input_sha256,
    ):
        per_symbol = []
        metadata_rows = []
        trade_rows = []
        for definition, metadata, result in replay_results:
            per_symbol.append(self._symbol_result(
                definition, metadata, result, common_count,
            ))
            metadata_rows.append(self._metadata_result(definition, metadata))
            trade_rows.extend(self._trade_rows(definition, metadata, result))

        trade_rows.sort(key=lambda row: (
            row["entry_time"] or "", row["canonical_symbol"], row["trade_id"],
        ))
        asset_classes = [
            self._aggregate_scope(
                asset_class,
                [item for item in replay_results if item[0].asset_class == asset_class],
                config,
            )
            for asset_class in ("FOREX", "METAL", "CRYPTO")
        ]
        combined = self._aggregate_scope(
            "ALL_ASSETS", replay_results, config,
        )
        context_count = sum(row["context_snapshot_available"] for row in trade_rows)
        closed_count = sum(row["status"] == "CLOSED" for row in trade_rows)
        unresolved_count = sum(row["status"] != "CLOSED" for row in trade_rows)
        payload = {
            "schema_version": self.VERSION,
            "mode": self.MODE,
            "generated_as_of": generated_as_of.isoformat(),
            "universe": [
                {
                    **definition.to_dict(),
                    "broker_symbol": self._broker_symbol(metadata),
                }
                for definition, metadata, _ in replay_results
            ],
            "replay_configuration": {
                **asdict(config),
                "timeframe": self.TIMEFRAME,
                "target_candle_count": target_count,
                "common_candle_count": common_count,
                "completed_candle_start_position": 1,
                "entry_timing": "DECISION_CLOSE_THEN_NEXT_CANDLE_OPEN",
                "position_policy": "ONE_OPEN_POSITION_PER_SYMBOL",
                "capital_model": "INDEPENDENT_STARTING_CAPITAL_PER_SYMBOL",
                "shared_capital_portfolio_simulated": False,
                "real_orders_sent": False,
                "parameter_optimization_performed": False,
            },
            "history_availability": [
                {**row, **next(
                    selected for selected in selected_ranges
                    if selected["canonical_symbol"] == row["canonical_symbol"]
                )}
                for row in availability
            ],
            "broker_metadata": metadata_rows,
            "per_symbol_results": per_symbol,
            "asset_class_results": asset_classes,
            "combined_independent_results": combined,
            "trades": trade_rows,
            "diagnostics": {
                "symbol_count": len(per_symbol),
                "asset_class_count": len(asset_classes),
                "common_candle_count": common_count,
                "closed_trade_count": closed_count,
                "unresolved_trade_count": unresolved_count,
                "future_candle_count": sum(
                    row["future_candle_count"] for row in availability
                ),
                "lookahead_violation_count": 0,
                "context_snapshot_count": context_count,
                "missing_context_snapshot_count": len(trade_rows) - context_count,
                "input_snapshot_unchanged": True,
                "production_decision_consumption": False,
                "trading_operations_performed": 0,
            },
            "audit": {
                "input_snapshot_sha256_before": input_sha256,
                "input_snapshot_sha256_after": input_sha256,
                "trade_records_sha256": self._json_sha256(trade_rows),
                "per_symbol_results_sha256": self._json_sha256(per_symbol),
                "source_values_imputed": False,
                "source_trades_removed": False,
                "unresolved_trades_excluded_from_outcome_metrics": True,
                "historical_engine": (
                    "mss.analysis.historical_backtest_engine."
                    "HistoricalBacktestEngine"
                ),
                "strategy_parameters_changed": False,
                "production_imports_added": False,
            },
            "production_change_justified": False,
        }
        return payload

    def _symbol_result(self, definition, metadata, result, common_count):
        metrics = result.metrics
        diagnostics = result.diagnostics
        closed = [trade for trade in result.trades if trade.status == "CLOSED"]
        unresolved = [trade for trade in result.trades if trade.status != "CLOSED"]
        values = [trade.r_multiple for trade in closed]
        return {
            "canonical_symbol": definition.canonical_symbol,
            "broker_symbol": self._broker_symbol(metadata),
            "asset_class": definition.asset_class,
            "source_candles": common_count,
            "data_start": diagnostics.data_start.isoformat(),
            "data_end": diagnostics.data_end.isoformat(),
            "decisions": diagnostics.decisions_generated,
            "buy_signals": diagnostics.buy_signals,
            "sell_signals": diagnostics.sell_signals,
            "wait_results": diagnostics.wait_results,
            "opened_trades": diagnostics.opened_trades,
            "closed_trades": diagnostics.closed_trades,
            "unresolved_trades": len(unresolved),
            "rejected_trades": diagnostics.rejected_trades,
            "wins": metrics.winning_trades,
            "losses": metrics.losing_trades,
            "win_rate_percent": metrics.win_rate,
            "gross_profit": metrics.gross_profit,
            "gross_loss": metrics.gross_loss,
            "net_profit": metrics.net_profit,
            "profit_factor": metrics.profit_factor,
            "expectancy": metrics.expectancy,
            "average_r": metrics.average_r,
            "median_r": round(float(median(values)), 4) if values else 0.0,
            "maximum_drawdown": metrics.maximum_drawdown,
            "maximum_drawdown_percent": metrics.maximum_drawdown_percent,
            "maximum_consecutive_wins": metrics.maximum_consecutive_wins,
            "maximum_consecutive_losses": metrics.maximum_consecutive_losses,
            "average_holding_minutes": metrics.average_holding_minutes,
            "starting_balance": result.config.starting_balance,
            "ending_balance": metrics.ending_balance,
            "total_return_percent": metrics.return_percent,
            "context_snapshot_count": sum(
                trade.context_snapshot is not None for trade in result.trades
            ),
        }

    def _aggregate_scope(self, scope, replay_results, config):
        closed = sorted(
            [
                trade
                for _, _, result in replay_results
                for trade in result.trades
                if trade.status == "CLOSED"
            ],
            key=lambda trade: (trade.exit_time, trade.symbol, trade.trade_id),
        )
        opened = sum(item[2].diagnostics.opened_trades for item in replay_results)
        unresolved = sum(item[2].diagnostics.unresolved_trades for item in replay_results)
        starting = config.starting_balance * len(replay_results)
        metrics = HistoricalBacktestEngine._calculate_metrics(
            closed, starting, TradeStatistics(),
        )
        ending = round(sum(item[2].metrics.ending_balance for item in replay_results), 2)
        r_values = [trade.r_multiple for trade in closed]
        return {
            "scope": scope,
            "symbols": [item[0].canonical_symbol for item in replay_results],
            "symbol_count": len(replay_results),
            "capital_model": "SUMMED_INDEPENDENT_SYMBOL_BALANCES",
            "true_shared_capital_portfolio": False,
            "opened_trades": opened,
            "closed_trades": len(closed),
            "unresolved_trades": unresolved,
            "wins": metrics.winning_trades,
            "losses": metrics.losing_trades,
            "win_rate_percent": metrics.win_rate,
            "gross_profit": metrics.gross_profit,
            "gross_loss": metrics.gross_loss,
            "net_profit": metrics.net_profit,
            "profit_factor": metrics.profit_factor,
            "expectancy": metrics.expectancy,
            "average_r": metrics.average_r,
            "median_r": round(float(median(r_values)), 4) if r_values else 0.0,
            "maximum_drawdown": metrics.maximum_drawdown,
            "maximum_drawdown_percent": metrics.maximum_drawdown_percent,
            "starting_balance": round(starting, 2),
            "ending_balance": ending,
            "total_return_percent": (
                round((ending - starting) / starting * 100.0, 4)
                if starting else 0.0
            ),
        }

    def _trade_rows(self, definition, metadata, result):
        rows = []
        broker_symbol = self._broker_symbol(metadata)
        for trade in result.trades:
            context_json = (
                trade.context_snapshot.payload_json
                if trade.context_snapshot is not None else ""
            )
            if trade.status != "CLOSED":
                outcome = "UNRESOLVED"
            elif trade.profit > 0:
                outcome = "WIN"
            elif trade.profit < 0:
                outcome = "LOSS"
            else:
                outcome = "BREAKEVEN"
            rows.append({
                "trade_key": f"{definition.canonical_symbol}:{trade.trade_id}",
                "trade_id": trade.trade_id,
                "canonical_symbol": definition.canonical_symbol,
                "broker_symbol": broker_symbol,
                "asset_class": definition.asset_class,
                "timeframe": trade.timeframe,
                "direction": trade.direction,
                "signal_time": self._iso(trade.signal_time),
                "entry_time": self._iso(trade.entry_time),
                "entry_price": trade.entry_price,
                "stop_loss": trade.stop_loss,
                "take_profit": trade.take_profit,
                "exit_time": self._iso(trade.exit_time),
                "exit_price": trade.exit_price,
                "exit_reason": trade.exit_reason,
                "spread": trade.spread,
                "commission": trade.commission,
                "slippage": trade.slippage,
                "volume": trade.volume,
                "profit": trade.profit,
                "r_multiple": trade.r_multiple,
                "status": trade.status,
                "outcome": outcome,
                "legacy_score": trade.legacy_score,
                "legacy_confidence": trade.legacy_confidence,
                "shadow_score": trade.shadow_score,
                "shadow_confidence": trade.shadow_confidence,
                "detector_states": trade.detector_states,
                "context_snapshot_available": trade.context_snapshot is not None,
                "context_snapshot_sha256": (
                    hashlib.sha256(context_json.encode("utf-8")).hexdigest()
                    if context_json else self.NOT_AVAILABLE
                ),
                "context_snapshot": (
                    trade.context_snapshot.to_dict()
                    if trade.context_snapshot is not None else self.NOT_AVAILABLE
                ),
            })
        return rows

    def _metadata_result(self, definition, metadata):
        return {
            "canonical_symbol": definition.canonical_symbol,
            "broker_symbol": self._broker_symbol(metadata),
            "asset_class": definition.asset_class,
            "digits": self._required_number(metadata, "digits", integral=True),
            "point": self._required_number(metadata, "point"),
            "tick_size": self._required_number(metadata, "trade_tick_size"),
            "tick_value": self._required_number(metadata, "trade_tick_value"),
            "contract_size": self._required_number(
                metadata, "trade_contract_size", alternate="contract_size",
            ),
            "volume_min": self._required_number(metadata, "volume_min"),
            "volume_max": self._required_number(metadata, "volume_max"),
            "volume_step": self._required_number(metadata, "volume_step"),
            "spread_points": self._required_number(
                metadata, "spread", alternate="spread_points", allow_zero=True,
            ),
            "spread_price": round(
                self._required_number(metadata, "point")
                * self._required_number(
                    metadata, "spread", alternate="spread_points", allow_zero=True,
                ),
                12,
            ),
        }

    def _engine_metadata(self, metadata):
        row = self._metadata_result(
            type("Definition", (), {
                "canonical_symbol": "", "asset_class": "",
            })(),
            metadata,
        )
        return BacktestSymbolMetadata(
            point=row["point"],
            digits=row["digits"],
            tick_size=row["tick_size"],
            tick_value=row["tick_value"],
            contract_size=row["contract_size"],
            volume_min=row["volume_min"],
            volume_max=row["volume_max"],
            volume_step=row["volume_step"],
            spread_points=row["spread_points"],
        )

    def _require_replay_quality(self, coverage):
        if coverage["availability_status"] == "MISSING":
            raise ValueError(
                f"M15 history unavailable for {coverage['canonical_symbol']}"
            )
        if not coverage["chronological_order"]:
            raise ValueError(
                f"Non-chronological M15 history for {coverage['canonical_symbol']}"
            )
        failures = {
            field: coverage[field]
            for field in self.HARD_QUALITY_FIELDS if coverage[field]
        }
        if failures:
            raise ValueError(
                f"Unsafe M15 history for {coverage['canonical_symbol']}: {failures}"
            )

    @staticmethod
    def _validate_config(config):
        if config.ambiguous_policy != "STOP_LOSS_FIRST":
            raise ValueError("Sprint 91 requires STOP_LOSS_FIRST")
        if config.commission_per_lot != 0.0:
            raise ValueError("Sprint 91 preserves zero commission")

    def _broker_symbol(self, metadata):
        symbol = (
            self._value(metadata, "broker_symbol", None)
            or self._value(metadata, "resolved_symbol", None)
            or self._value(metadata, "name", None)
        )
        if not symbol or symbol == self.NOT_AVAILABLE:
            raise ValueError("Broker symbol metadata is required for replay")
        return str(symbol)

    def _required_number(
        self,
        metadata,
        field,
        alternate=None,
        integral=False,
        allow_zero=False,
    ):
        value = self._value(metadata, field, None)
        if value is None and alternate:
            value = self._value(metadata, alternate, None)
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = math.nan
        if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
            raise ValueError(f"Valid broker metadata is required: {field}")
        return int(number) if integral else number

    def input_sha256(self, history_results, broker_metadata, config):
        history = []
        for definition in self.universe:
            canonical = definition.canonical_symbol
            payload = self._value(history_results, canonical, {}) or {}
            candles = tuple(self._value(payload, "candles", ()) or ())
            history.append({
                "canonical_symbol": canonical,
                "resolved_symbol": self._value(payload, "resolved_symbol", None),
                "requested_count": self._value(payload, "requested_count", 0),
                "returned_count": self._value(payload, "returned_count", 0),
                "candles": [
                    {
                        field: self._clean(self._value(candle, field, None))
                        for field in (
                            "time", "open", "high", "low", "close",
                            "tick_volume", "spread", "real_volume",
                        )
                    }
                    for candle in candles
                ],
                "metadata": self._clean(
                    self._value(broker_metadata, canonical, {}) or {}
                ),
            })
        return self._json_sha256({
            "history": history,
            "config": asdict(config),
        })

    @classmethod
    def validate_result_schema(cls, result):
        if tuple(result) != cls.RESULT_KEYS:
            raise ValueError("Multi-asset replay schema is invalid")
        if result["mode"] != cls.MODE:
            raise ValueError("Replay mode must remain research-only")
        if result["production_change_justified"] is not False:
            raise ValueError("Replay production guardrail is invalid")
        if len(result["universe"]) != len(cls.TARGET_UNIVERSE):
            raise ValueError("Replay universe is incomplete")
        if len(result["per_symbol_results"]) != len(cls.TARGET_UNIVERSE):
            raise ValueError("Per-symbol replay results are incomplete")
        if result["diagnostics"]["future_candle_count"]:
            raise ValueError("Replay contains future candles")
        if result["diagnostics"]["lookahead_violation_count"]:
            raise ValueError("Replay contains lookahead violations")

    @staticmethod
    def write_json(result, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                result, indent=2, sort_keys=True, default=str, allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _json_sha256(value):
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            default=str, allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _iso(value):
        return value.isoformat() if value is not None else None
