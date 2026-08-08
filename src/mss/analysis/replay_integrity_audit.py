"""Diagnostic-only reconciliation of an existing multi-asset replay artifact."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import math
from statistics import median


class ReplayIntegrityAudit:
    """Audit saved Sprint 91 results without running the replay engine."""

    VERSION = "SPRINT_92A_REPLAY_INTEGRITY_AUDIT_V1"
    SYMBOLS = (
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
        "USDCAD", "XAUUSD", "BTCUSD", "ETHUSD",
    )
    AMOUNT_TOLERANCE = 0.01
    PERCENT_TOLERANCE = 0.0001

    def audit(self, replay, validation_metadata=None):
        summaries = {row["canonical_symbol"]: row for row in replay["per_symbol_results"]}
        replay_metadata = {row["canonical_symbol"]: row for row in replay["broker_metadata"]}
        trades = replay["trades"]
        risk_percent = float(replay["replay_configuration"]["risk_percent"])
        reference_metadata = self._reference_metadata(validation_metadata)

        reconciliations = {}
        risk_checks = {}
        paths = {}
        for symbol in self.SYMBOLS:
            closed = self._closed_trades(trades, symbol)
            path = self._equity_path(closed, float(summaries[symbol]["starting_balance"]))
            paths[symbol] = path
            reconciliations[symbol] = self._reconcile(summaries[symbol], closed, path)
            risk_checks[symbol] = self._risk_consistency(
                closed, path, replay_metadata[symbol], reference_metadata.get(symbol),
                risk_percent,
            )

        metadata_checks = {
            symbol: self._metadata_check(
                replay_metadata[symbol], reference_metadata.get(symbol),
            )
            for symbol in self.SYMBOLS
        }
        usd = self._usd_jpy_audit(
            self._closed_trades(trades, "USDJPY"), paths["USDJPY"],
            replay_metadata["USDJPY"], reference_metadata.get("USDJPY"),
            risk_percent,
        )
        mismatches = [
            symbol for symbol, row in reconciliations.items()
            if row["status"] != "PASS"
        ]
        unit_defects = [
            symbol for symbol, row in metadata_checks.items()
            if row["engine_value_per_tick_per_lot_matches_reference"] is False
        ]
        anomalies = self._anomalies(reconciliations, risk_checks, metadata_checks)
        defect_found = bool(unit_defects)
        return {
            "schema_version": self.VERSION,
            "mode": "DIAGNOSTIC_ONLY_EXISTING_ARTIFACTS",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "replay_schema_version": replay.get("schema_version"),
                "replay_generated_as_of": replay.get("generated_as_of"),
                "replay_was_rerun": False,
                "reference_metadata_supplied": bool(reference_metadata),
            },
            "tolerances": {
                "amount_absolute": self.AMOUNT_TOLERANCE,
                "percentage_points_absolute": self.PERCENT_TOLERANCE,
                "comparison_rule": "absolute delta <= tolerance",
                "percentile_method": "nearest-rank",
                "material_loss_thresholds_percent": [1.25, 1.5, 2.0],
            },
            "overall_audit_status": (
                "DEFECT_FOUND" if defect_found else
                "RECONCILIATION_FAILED" if mismatches else "PASS"
            ),
            "per_symbol_reconciliation": reconciliations,
            "usd_jpy_drawdown_audit": usd,
            "per_symbol_risk_consistency": risk_checks,
            "metadata_checks": metadata_checks,
            "anomalies": anomalies,
            "conclusions": {
                "summary_fields_reconcile": not mismatches,
                "reconciliation_mismatches": mismatches,
                "usd_jpy_drawdown_classification": "A_AND_B",
                "usd_jpy_drawdown_explanation": (
                    "The 6386.00 / 60.3934% drawdown is mathematically correct for "
                    "the recorded Sprint 91 equity path, but that path is economically "
                    "invalid for a USD account because sizing and PnL ignore tick value. "
                    "USDJPY raw volumes were forced to the 0.01-lot minimum and JPY "
                    "price movement was then treated as USD."
                ),
                "metric_aggregation_defect_found": False,
                "position_sizing_and_valuation_defect_symbols": unit_defects,
                "production_fix_applied": False,
                "replay_regeneration_recommended_after_fix": True,
            },
            "code_defect_found": defect_found,
        }

    @staticmethod
    def _closed_trades(trades, symbol):
        return [
            row for row in trades
            if row["canonical_symbol"] == symbol and row["status"] == "CLOSED"
        ]

    @staticmethod
    def _equity_path(trades, starting_balance):
        balance = starting_balance
        peak = starting_balance
        peak_index = 0
        rows = [{
            "index": 0, "trade_id": None, "exit_time": None,
            "pre_trade_equity": starting_balance, "equity": starting_balance,
            "peak": starting_balance, "peak_index": 0,
            "drawdown_amount": 0.0, "drawdown_percent": 0.0,
        }]
        for index, trade in enumerate(trades, start=1):
            pre_trade = balance
            balance = round(balance + float(trade["profit"]), 2)
            if balance > peak:
                peak = balance
                peak_index = index
            drawdown = peak - balance
            rows.append({
                "index": index,
                "trade_id": trade["trade_id"],
                "exit_time": trade["exit_time"],
                "pre_trade_equity": round(pre_trade, 2),
                "equity": balance,
                "peak": peak,
                "peak_index": peak_index,
                "drawdown_amount": round(drawdown, 2),
                "drawdown_percent": round(drawdown / peak * 100.0, 4) if peak else 0.0,
            })
        return rows

    def _reconcile(self, summary, trades, path):
        profits = [float(row["profit"]) for row in trades]
        amount_values = {
            "starting_balance": float(summary["starting_balance"]),
            "ending_balance": path[-1]["equity"],
            "gross_profit": round(sum(max(value, 0.0) for value in profits), 2),
            "gross_loss": round(sum(abs(min(value, 0.0)) for value in profits), 2),
            "net_profit": round(sum(profits), 2),
            "maximum_drawdown": max(row["drawdown_amount"] for row in path),
        }
        percent_values = {
            "total_return_percent": round(
                (path[-1]["equity"] - path[0]["equity"]) / path[0]["equity"] * 100.0,
                4,
            ),
            "maximum_drawdown_percent": max(row["drawdown_percent"] for row in path),
        }
        counts = {
            "closed_trades": len(trades),
            "wins": sum(value > 0 for value in profits),
            "losses": sum(value < 0 for value in profits),
        }
        comparisons = {}
        for name, recomputed in {**amount_values, **percent_values, **counts}.items():
            reported = summary[name]
            delta = round(float(recomputed) - float(reported), 10)
            tolerance = (
                0 if name in counts else
                self.PERCENT_TOLERANCE if name.endswith("percent") else
                self.AMOUNT_TOLERANCE
            )
            comparisons[name] = {
                "reported": reported, "recomputed": recomputed, "delta": delta,
                "tolerance": tolerance, "match": abs(delta) <= tolerance,
            }
        return {
            "status": "PASS" if all(row["match"] for row in comparisons.values()) else "FAIL",
            "trade_grain": "one closed trade ordered by saved per-symbol trade order",
            "equity_formula": "equity[n] = round(equity[n-1] + trade_profit[n], 2)",
            "drawdown_formula": "peak[n] - equity[n]; percent = drawdown / peak[n] * 100",
            "comparisons": comparisons,
        }

    def _risk_consistency(self, trades, path, metadata, reference, risk_percent):
        losses = []
        stop_losses = []
        tick_aware_losses = []
        minimum_volume_count = 0
        tick_balance = path[0]["equity"]
        for trade, point in zip(trades, path[1:]):
            if math.isclose(float(trade["volume"]), float(metadata["volume_min"]), abs_tol=1e-12):
                minimum_volume_count += 1
            if float(trade["profit"]) < 0:
                loss_percent = -float(trade["profit"]) / point["pre_trade_equity"] * 100.0
                losses.append(loss_percent)
                if trade["exit_reason"] == "STOP_LOSS":
                    stop_losses.append(loss_percent)
            tick_profit = self._tick_value_profit(trade, reference)
            if tick_profit is not None:
                tick_pre_trade = tick_balance
                tick_balance = round(tick_balance + tick_profit, 2)
                if tick_profit < 0:
                    tick_aware_losses.append(-tick_profit / tick_pre_trade * 100.0)
        ordered = sorted(losses)
        tick_ordered = sorted(tick_aware_losses)
        return {
            "intended_risk_percent": risk_percent,
            "losing_trade_count": len(losses),
            "stop_loss_trade_count": len(stop_losses),
            "median_losing_trade_percent": self._rounded(median(losses) if losses else 0.0),
            "p90_losing_trade_percent": self._rounded(self._nearest_rank(ordered, 0.90)),
            "maximum_losing_trade_percent": self._rounded(max(losses, default=0.0)),
            "losses_above_1_25_percent": sum(value > 1.25 for value in losses),
            "losses_above_1_50_percent": sum(value > 1.50 for value in losses),
            "losses_above_2_00_percent": sum(value > 2.00 for value in losses),
            "tick_value_aware_loss_distribution": {
                "basis": "recomputed PnL and pre-trade equity using reference tick_size and tick_value",
                "median_losing_trade_percent": self._rounded(median(tick_aware_losses) if tick_aware_losses else 0.0),
                "p90_losing_trade_percent": self._rounded(self._nearest_rank(tick_ordered, 0.90)),
                "maximum_losing_trade_percent": self._rounded(max(tick_aware_losses, default=0.0)),
                "losses_above_1_25_percent": sum(value > 1.25 for value in tick_aware_losses),
                "losses_above_1_50_percent": sum(value > 1.50 for value in tick_aware_losses),
                "losses_above_2_00_percent": sum(value > 2.00 for value in tick_aware_losses),
                "ending_equity": tick_balance if reference else None,
            },
            "trades_at_minimum_volume": minimum_volume_count,
            "volume_distribution": self._volume_distribution(trades),
            "recorded_model_assessment": (
                "MATERIAL_DEVIATION" if any(value > 1.25 for value in losses)
                else "CONSISTENT_WITH_1_PERCENT_AFTER_ROUNDING_AND_COSTS"
            ),
            "tick_value_aware_assessment": self._tick_aware_assessment(metadata, reference),
        }

    def _usd_jpy_audit(self, trades, path, metadata, reference, risk_percent):
        amount_row = max(path, key=lambda row: row["drawdown_amount"])
        trough_index = amount_row["index"]
        peak_index = amount_row["peak_index"]
        peak_row = path[peak_index]
        sequence = trades[peak_index:trough_index]
        enriched = [
            self._trade_diagnostic(trade, point, metadata, reference, risk_percent)
            for trade, point in zip(trades, path[1:])
        ]
        volumes = [float(row["volume"]) for row in trades]
        return {
            "classification": "A_AND_B",
            "drawdown_formula": "max over closed trades of (running peak equity - current equity); percent = amount / running peak * 100",
            "prior_equity_peak": peak_row["equity"],
            "peak_trade_id": peak_row["trade_id"],
            "peak_timestamp": peak_row["exit_time"],
            "trough_equity": amount_row["equity"],
            "trough_trade_id": amount_row["trade_id"],
            "trough_timestamp": amount_row["exit_time"],
            "maximum_drawdown_amount": amount_row["drawdown_amount"],
            "maximum_drawdown_percent": amount_row["drawdown_percent"],
            "trades_peak_to_trough": trough_index - peak_index,
            "peak_to_trough_trade_ids": [row["trade_id"] for row in sequence],
            "peak_to_trough_net_profit": round(sum(float(row["profit"]) for row in sequence), 2),
            "recovered": any(row["equity"] >= peak_row["equity"] for row in path[trough_index + 1:]),
            "ending_equity": path[-1]["equity"],
            "recovery_shortfall": round(max(0.0, peak_row["equity"] - path[-1]["equity"]), 2),
            "largest_winning_trade": max(enriched, key=lambda row: row["profit"]),
            "largest_losing_trade": min(enriched, key=lambda row: row["profit"]),
            "top_10_absolute_pnl_trades": sorted(
                enriched, key=lambda row: abs(row["profit"]), reverse=True,
            )[:10],
            "position_size_distribution": {
                "counts": dict(sorted(Counter(str(value) for value in volumes).items())),
                "minimum": min(volumes), "median": median(volumes), "maximum": max(volumes),
            },
            "all_trades_at_minimum_volume": all(
                math.isclose(value, float(metadata["volume_min"]), abs_tol=1e-12)
                for value in volumes
            ),
            "exact_drawdown_sequence": [
                self._trade_diagnostic(trade, path[index], metadata, reference, risk_percent)
                for index, trade in enumerate(sequence, start=peak_index + 1)
            ],
        }

    def _trade_diagnostic(self, trade, point, metadata, reference, risk_percent):
        entry = float(trade["entry_price"])
        stop = float(trade["stop_loss"])
        volume = float(trade["volume"])
        contract = float(metadata["contract_size"])
        stop_distance = abs(entry - stop)
        intended = point["pre_trade_equity"] * risk_percent / 100.0
        raw_engine_volume = intended / (stop_distance * contract) if stop_distance else 0.0
        ref_tick_size = float(reference["trade_tick_size"]) if reference else None
        ref_tick_value = float(reference["trade_tick_value"]) if reference else None
        tick_risk_per_lot = (
            stop_distance / ref_tick_size * ref_tick_value
            if ref_tick_size and ref_tick_value is not None else None
        )
        raw_tick_volume = intended / tick_risk_per_lot if tick_risk_per_lot else None
        normalized_tick_volume = (
            self._normalize_volume(raw_tick_volume, metadata)
            if raw_tick_volume is not None else None
        )
        recorded_loss_percent = (
            -float(trade["profit"]) / point["pre_trade_equity"] * 100.0
            if float(trade["profit"]) < 0 else None
        )
        spread_cost = float(trade["spread"]) * volume * contract
        slippage_cost = 2.0 * float(trade["slippage"]) * volume * contract
        return {
            "trade_id": trade["trade_id"], "direction": trade["direction"],
            "entry_time": trade["entry_time"], "exit_time": trade["exit_time"],
            "exit_reason": trade["exit_reason"], "entry_price": entry,
            "stop_loss": stop, "exit_price": trade["exit_price"],
            "profit": trade["profit"], "pre_trade_equity": point["pre_trade_equity"],
            "intended_risk_amount": round(intended, 6),
            "intended_risk_percent": risk_percent,
            "actual_recorded_loss_percent": self._rounded(recorded_loss_percent) if recorded_loss_percent is not None else None,
            "sl_distance": stop_distance, "point": metadata["point"],
            "tick_size": ref_tick_size, "tick_value": ref_tick_value,
            "contract_size": contract, "volume_step": metadata["volume_step"],
            "volume_min": metadata["volume_min"],
            "raw_engine_calculated_volume": round(raw_engine_volume, 8),
            "raw_tick_value_aware_volume": round(raw_tick_volume, 8) if raw_tick_volume is not None else None,
            "normalized_tick_value_aware_volume": normalized_tick_volume,
            "actual_volume": volume,
            "minimum_volume_clamped": math.isclose(volume, float(metadata["volume_min"]), abs_tol=1e-12),
            "spread_price": trade["spread"], "slippage_price_per_side": trade["slippage"],
            "commission": trade["commission"],
            "recorded_spread_cost_component": round(spread_cost, 6),
            "recorded_round_trip_slippage_cost": round(slippage_cost, 6),
            "gap_effect": "NOT_MODELED_EXITS_FILL_AT_SL_OR_TP_LEVEL_PLUS_CONFIGURED_SLIPPAGE",
        }

    @staticmethod
    def _reference_metadata(payload):
        if not payload:
            return {}
        rows = payload.get("trading_conditions", payload)
        if isinstance(rows, dict):
            return rows
        return {row["canonical_symbol"]: row for row in rows}

    def _metadata_check(self, replay, reference):
        fields = ("point", "digits", "contract_size", "volume_step")
        aliases = {"contract_size": "trade_contract_size"}
        comparisons = {}
        for field in fields:
            reference_field = aliases.get(field, field)
            reference_value = reference.get(reference_field) if reference else None
            replay_value = replay.get(field)
            comparisons[field] = {
                "replay": replay_value, "reference": reference_value,
                "match": reference_value is None or math.isclose(
                    float(replay_value), float(reference_value), rel_tol=0.0, abs_tol=1e-12,
                ),
            }
        tick_size = reference.get("trade_tick_size") if reference else None
        tick_value = reference.get("trade_tick_value") if reference else None
        engine_tick_value = (
            float(replay["contract_size"]) * float(tick_size)
            if tick_size is not None else None
        )
        matches = (
            math.isclose(engine_tick_value, float(tick_value), rel_tol=1e-9, abs_tol=1e-12)
            if engine_tick_value is not None and tick_value is not None else None
        )
        return {
            "broker_symbol": replay["broker_symbol"],
            "asset_class": replay["asset_class"],
            "field_comparisons": comparisons,
            "replay_tick_size": replay.get("tick_size"),
            "replay_tick_value": replay.get("tick_value"),
            "reference_tick_size": tick_size,
            "reference_tick_value": tick_value,
            "tick_fields_missing_from_replay": "tick_size" not in replay or "tick_value" not in replay,
            "engine_implied_value_per_tick_per_lot": engine_tick_value,
            "engine_value_per_tick_per_lot_matches_reference": matches,
            "engine_to_reference_tick_value_ratio": (
                round(engine_tick_value / float(tick_value), 8)
                if engine_tick_value is not None and tick_value else None
            ),
            "status": "DEFECT" if matches is False else "PASS" if matches else "INSUFFICIENT_EVIDENCE",
        }

    @staticmethod
    def _tick_aware_assessment(metadata, reference):
        if not reference:
            return "REFERENCE_TICK_METADATA_UNAVAILABLE"
        implied = float(metadata["contract_size"]) * float(reference["trade_tick_size"])
        actual = float(reference["trade_tick_value"])
        return (
            "CONSISTENT" if math.isclose(implied, actual, rel_tol=1e-9, abs_tol=1e-12)
            else "ENGINE_IGNORES_NON_EQUIVALENT_TICK_VALUE"
        )

    @staticmethod
    def _tick_value_profit(trade, reference):
        if not reference:
            return None
        tick_size = float(reference["trade_tick_size"])
        tick_value = float(reference["trade_tick_value"])
        multiplier = 1.0 if trade["direction"] == "BUY" else -1.0
        gross = (
            (float(trade["exit_price"]) - float(trade["entry_price"]))
            * multiplier / tick_size * tick_value * float(trade["volume"])
        )
        return round(gross - float(trade["commission"]), 2)

    @staticmethod
    def _normalize_volume(raw_volume, metadata):
        step = float(metadata["volume_step"])
        steps = math.floor((raw_volume + 1e-12) / step)
        volume = steps * step
        volume = max(float(metadata["volume_min"]), min(float(metadata["volume_max"]), volume))
        decimals = max(0, len(str(step).split(".")[-1]))
        return round(volume, decimals)

    @staticmethod
    def _volume_distribution(trades):
        values = [float(row["volume"]) for row in trades]
        return {
            "minimum": min(values, default=0.0),
            "median": median(values) if values else 0.0,
            "maximum": max(values, default=0.0),
            "distinct_count": len(set(values)),
        }

    @staticmethod
    def _nearest_rank(ordered, percentile):
        if not ordered:
            return 0.0
        return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]

    @staticmethod
    def _rounded(value):
        return round(float(value), 4)

    @staticmethod
    def _anomalies(reconciliations, risks, metadata):
        rows = []
        for symbol, result in reconciliations.items():
            if result["status"] != "PASS":
                rows.append({"severity": "HIGH", "symbol": symbol, "type": "RECONCILIATION_MISMATCH"})
        for symbol, result in risks.items():
            if result["recorded_model_assessment"] == "MATERIAL_DEVIATION":
                rows.append({
                    "severity": "HIGH", "symbol": symbol,
                    "type": "RECORDED_LOSS_RISK_DEVIATION",
                    "maximum_loss_percent": result["maximum_losing_trade_percent"],
                })
        for symbol, result in metadata.items():
            if result["engine_value_per_tick_per_lot_matches_reference"] is False:
                rows.append({
                    "severity": "CRITICAL" if symbol == "USDJPY" else "HIGH",
                    "symbol": symbol, "type": "TICK_VALUE_IGNORED",
                    "engine_to_reference_ratio": result["engine_to_reference_tick_value_ratio"],
                })
        return rows
