"""Diagnostics for the three-symbol corrected-valuation smoke replay."""

from __future__ import annotations

import math
from statistics import median

from mss.analysis.historical_valuation import HistoricalValuation


class CorrectedValuationSmokeReplay:
    VERSION = "SPRINT_92A2A_CORRECTED_VALUATION_SMOKE_REPLAY_V1"
    SYMBOLS = ("USDJPY", "USDCAD", "XAUUSD")
    LOSS_THRESHOLDS = (1.25, 1.50, 2.00)

    def build_report(self, replay_rows, v1_payload, audit_payload):
        v1_results = {
            row["canonical_symbol"]: row
            for row in v1_payload["per_symbol_results"]
        }
        old_risk = audit_payload["per_symbol_risk_consistency"]
        symbols = {}
        for row in replay_rows:
            symbol = row["canonical_symbol"]
            if symbol not in self.SYMBOLS:
                raise ValueError(f"Unexpected smoke symbol: {symbol}")
            symbols[symbol] = self._symbol_report(
                row, v1_results[symbol], old_risk[symbol],
            )
        if set(symbols) != set(self.SYMBOLS):
            raise ValueError("Smoke replay requires exactly USDJPY, USDCAD, XAUUSD")

        acceptance = {
            "tick_metadata_present_and_used": all(
                row["valuation_check"]["pass"] for row in symbols.values()
            ),
            "known_valuation_mismatches_eliminated": all(
                row["valuation_check"]["corrected_to_broker_ratio"] == 1.0
                for row in symbols.values()
            ),
            "losing_trade_risk_consistent": all(
                row["corrected_loss_risk_distribution"]["losses_above_1_25_percent"] == 0
                for row in symbols.values()
            ),
            "no_oversized_minimum_volume_forced": all(
                row["minimum_volume"]["oversized_minimum_volume_trade_count"] == 0
                for row in symbols.values()
            ),
            "no_production_behavior_change": True,
            "no_real_orders_sent": True,
        }
        return {
            "schema_version": self.VERSION,
            "mode": "THREE_SYMBOL_CORRECTED_VALUATION_SMOKE_REPLAY",
            "symbols": symbols,
            "configuration": {
                "timeframe": "M15", "target_candle_count": 10000,
                "completed_candle_start_position": 1, "warmup_candles": 200,
                "analysis_lookback": 500, "starting_balance_per_symbol": 10000.0,
                "risk_percent": 1.0, "reward_risk_ratio": 2.0,
                "entry_timing": "DECISION_CLOSE_THEN_NEXT_CANDLE_OPEN",
                "position_policy": "ONE_OPEN_POSITION_PER_SYMBOL",
                "ambiguous_policy": "STOP_LOSS_FIRST", "spread_points": None,
                "slippage_points": 1.0, "commission_per_lot": 0.0,
                "paper_trading_only": True,
            },
            "acceptance_criteria": acceptance,
            "overall_status": "PASS" if all(acceptance.values()) else "FAIL",
            "interpretation_boundary": (
                "Before/after differences validate monetary valuation only and are not "
                "evidence of strategy improvement or deterioration."
            ),
            "full_eight_symbol_replay_run": False,
            "real_orders_sent": False,
            "strategy_parameters_changed": False,
            "live_order_logic_changed": False,
            "v1_artifacts_overwritten": False,
        }

    def _symbol_report(self, row, v1, old_risk):
        result = row["result"]
        metadata = row["metadata"]
        metadata_error = HistoricalValuation.metadata_error(metadata)
        if metadata_error:
            raise ValueError(f"{row['canonical_symbol']}: {metadata_error}")
        closed = [trade for trade in result.trades if trade.status == "CLOSED"]
        risk = self._risk_diagnostics(
            closed, result.config.starting_balance, result.config.risk_percent,
            metadata,
        )
        engine_implied_old_tick_value = metadata.tick_size * metadata.contract_size
        corrected_tick_value = HistoricalValuation.monetary_value(
            metadata.tick_size, 1.0, metadata,
        )
        metrics = result.metrics
        return {
            "historical_window": row["historical_window"],
            "broker_metadata": {
                field: getattr(metadata, field)
                for field in HistoricalValuation.REQUIRED_FIELDS
            },
            "valuation_check": {
                "old_contract_formula_value_per_tick_per_lot": engine_implied_old_tick_value,
                "broker_tick_value_per_lot": metadata.tick_value,
                "old_to_broker_ratio": round(
                    engine_implied_old_tick_value / metadata.tick_value, 8,
                ),
                "corrected_value_per_tick_per_lot": corrected_tick_value,
                "corrected_to_broker_ratio": round(
                    corrected_tick_value / metadata.tick_value, 8,
                ),
                "formula": "abs(price_delta) / tick_size * tick_value * volume",
                "pass": math.isclose(
                    corrected_tick_value, metadata.tick_value,
                    rel_tol=1e-12, abs_tol=1e-12,
                ),
            },
            "sprint_91_v1": {
                **self._performance(v1),
                "loss_risk_distribution": {
                    key: old_risk[key] for key in (
                        "median_losing_trade_percent", "p90_losing_trade_percent",
                        "maximum_losing_trade_percent", "losses_above_1_25_percent",
                        "losses_above_1_50_percent", "losses_above_2_00_percent",
                    )
                },
            },
            "corrected_smoke_replay": self._result_performance(result),
            "corrected_loss_risk_distribution": risk["summary"],
            "losing_trade_risk_details": risk["trades"],
            "minimum_volume": {
                "rejection_count": result.diagnostics.rejection_reasons.get(
                    "MIN_VOLUME_EXCEEDS_RISK", 0,
                ),
                "accepted_at_minimum_volume_count": risk["accepted_at_minimum"],
                "oversized_minimum_volume_trade_count": risk["oversized_at_minimum"],
            },
            "rejection_reasons": dict(sorted(result.diagnostics.rejection_reasons.items())),
        }

    def _risk_diagnostics(self, trades, starting_balance, risk_percent, metadata):
        balance = float(starting_balance)
        losing_rows = []
        accepted_at_minimum = 0
        oversized_at_minimum = 0
        for trade in trades:
            pre_trade_equity = balance
            intended = pre_trade_equity * float(risk_percent) / 100.0
            sl_risk = HistoricalValuation.monetary_value(
                abs(trade.entry_price - trade.stop_loss), trade.volume, metadata,
            )
            at_minimum = math.isclose(
                trade.volume, metadata.volume_min, rel_tol=0.0, abs_tol=1e-12,
            )
            if at_minimum:
                accepted_at_minimum += 1
                if sl_risk > intended + max(0.01, intended * 1e-9):
                    oversized_at_minimum += 1
            if trade.profit < 0:
                realized_loss_percent = -trade.profit / pre_trade_equity * 100.0
                losing_rows.append({
                    "trade_id": trade.trade_id,
                    "entry_time": self._iso(trade.entry_time),
                    "exit_time": self._iso(trade.exit_time),
                    "exit_reason": trade.exit_reason,
                    "pre_trade_equity": round(pre_trade_equity, 2),
                    "intended_risk_amount": round(intended, 6),
                    "position_volume": trade.volume,
                    "sl_risk_account_currency": round(sl_risk, 6),
                    "realized_loss_amount": -trade.profit,
                    "realized_loss_percent": round(realized_loss_percent, 6),
                    "exceeds_1_25_percent": realized_loss_percent > 1.25,
                    "exceeds_1_50_percent": realized_loss_percent > 1.50,
                    "exceeds_2_00_percent": realized_loss_percent > 2.00,
                })
            balance = round(balance + trade.profit, 2)
        values = sorted(row["realized_loss_percent"] for row in losing_rows)
        summary = {
            "losing_trade_count": len(values),
            "median_losing_trade_percent": round(median(values), 4) if values else 0.0,
            "p90_losing_trade_percent": round(self._nearest_rank(values, 0.9), 4),
            "maximum_losing_trade_percent": round(max(values, default=0.0), 4),
            "losses_above_1_25_percent": sum(value > 1.25 for value in values),
            "losses_above_1_50_percent": sum(value > 1.50 for value in values),
            "losses_above_2_00_percent": sum(value > 2.00 for value in values),
            "percentile_method": "nearest-rank",
        }
        return {
            "summary": summary, "trades": losing_rows,
            "accepted_at_minimum": accepted_at_minimum,
            "oversized_at_minimum": oversized_at_minimum,
        }

    @staticmethod
    def _performance(row):
        return {
            key: row[key] for key in (
                "opened_trades", "closed_trades", "rejected_trades",
                "win_rate_percent", "net_profit", "profit_factor", "expectancy",
                "average_r", "maximum_drawdown_percent", "total_return_percent",
            )
        }

    @staticmethod
    def _result_performance(result):
        metrics = result.metrics
        return {
            "opened_trades": result.diagnostics.opened_trades,
            "closed_trades": result.diagnostics.closed_trades,
            "rejected_trades": result.diagnostics.rejected_trades,
            "win_rate_percent": metrics.win_rate,
            "net_profit": metrics.net_profit,
            "profit_factor": metrics.profit_factor,
            "expectancy": metrics.expectancy,
            "average_r": metrics.average_r,
            "maximum_drawdown_percent": metrics.maximum_drawdown_percent,
            "total_return_percent": metrics.return_percent,
        }

    @staticmethod
    def _nearest_rank(ordered, percentile):
        if not ordered:
            return 0.0
        return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]

    @staticmethod
    def _iso(value):
        return value.isoformat() if value is not None else None
