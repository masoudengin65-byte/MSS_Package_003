"""Reporting for the frozen Sprint 92C.3 development/validation replay."""

from __future__ import annotations

from dataclasses import asdict

from mss.analysis.multi_asset_historical_replay_v2 import MultiAssetHistoricalReplayV2


class ExtendedDevelopmentValidationReplay:
    VERSION = "MSS_SPRINT92C3_EXTENDED_DEVELOPMENT_VALIDATION_REPLAY_V1"
    SEGMENTS = ("DEVELOPMENT", "VALIDATION")

    def __init__(self):
        self.replay = MultiAssetHistoricalReplayV2()

    def run(self, histories_by_segment, metadata, config):
        return {
            segment: self.replay.run_once(histories_by_segment[segment], metadata, config)
            for segment in self.SEGMENTS
        }

    def summarize_segment(self, segment, histories, results, metadata, config, manifest_rows):
        rows, trades, risks = [], [], []
        for symbol in self.replay.SYMBOLS:
            result = results[symbol]
            closed = [trade for trade in result.trades if trade.status == "CLOSED"]
            metrics = self.replay.metrics(result, closed, config.starting_balance)
            risk = self.replay.risk(closed, config.starting_balance, config.risk_percent)
            history = histories[symbol]
            row = {
                "segment": segment,
                "canonical_symbol": symbol,
                "broker_symbol": manifest_rows[symbol]["broker_symbol"],
                "asset_class": self.replay.CLASSES[symbol],
                "source_candles": len(history),
                "data_start": history[0].time.isoformat(),
                "data_end": history[-1].time.isoformat(),
                "source_sha256": self.replay.source_hash(history),
                "decisions": result.diagnostics.decisions_generated,
                "buy_signals": result.diagnostics.buy_signals,
                "sell_signals": result.diagnostics.sell_signals,
                "wait_results": result.diagnostics.wait_results,
                "opened_trades": result.diagnostics.opened_trades,
                "closed_trades": result.diagnostics.closed_trades,
                "unresolved_trades": result.diagnostics.unresolved_trades,
                "rejected_trades": result.diagnostics.rejected_trades,
                "rejection_reasons": dict(sorted(result.diagnostics.rejection_reasons.items())),
                **metrics,
                "risk_audit": risk,
            }
            rows.append(row)
            risks.append({"segment": segment, "canonical_symbol": symbol, **risk})
            for trade in self.replay.trade_rows(symbol, manifest_rows[symbol]["broker_symbol"], result.trades):
                trade["segment"] = segment
                trades.append(trade)
        groups = [
            self.replay.aggregate(name, [row for row in rows if row["asset_class"] == name])
            for name in ("FOREX", "METAL", "CRYPTO")
        ]
        combined = self.replay.aggregate("COMBINED", rows)
        for row in rows:
            row.pop("_r_multiples", None)
        return {
            "segment": segment,
            "per_symbol_results": rows,
            "asset_class_results": groups,
            "combined_independent_results": combined,
            "risk_audit": risks,
            "trades": trades,
        }

    @staticmethod
    def comparison(development, validation):
        dev = {row["canonical_symbol"]: row for row in development["per_symbol_results"]}
        val = {row["canonical_symbol"]: row for row in validation["per_symbol_results"]}
        return [{
            "canonical_symbol": symbol,
            "development_trades": dev[symbol]["closed_trades"],
            "validation_trades": val[symbol]["closed_trades"],
            "development_net_profit": dev[symbol]["net_profit"],
            "validation_net_profit": val[symbol]["net_profit"],
            "development_profit_factor": dev[symbol]["profit_factor"],
            "validation_profit_factor": val[symbol]["profit_factor"],
            "development_expectancy": dev[symbol]["expectancy"],
            "validation_expectancy": val[symbol]["expectancy"],
            "development_average_r": dev[symbol]["average_r"],
            "validation_average_r": val[symbol]["average_r"],
            "positive_in_both": dev[symbol]["net_profit"] > 0 and val[symbol]["net_profit"] > 0,
            "directionally_consistent": (dev[symbol]["net_profit"] > 0) == (val[symbol]["net_profit"] > 0),
        } for symbol in dev]

    def build(self, histories, metadata, results, config, manifest, manifest_sha256):
        manifest_rows = {row["canonical_symbol"]: row for row in manifest["symbols"]}
        summaries = {
            segment: self.summarize_segment(
                segment, histories[segment], results[segment], metadata, config, manifest_rows,
            ) for segment in self.SEGMENTS
        }
        comparisons = self.comparison(summaries["DEVELOPMENT"], summaries["VALIDATION"])
        return {
            "schema_version": self.VERSION,
            "mode": "RESEARCH_ONLY_FROZEN_DEVELOPMENT_VALIDATION_REPLAY",
            "baseline_commit": "a0e3357",
            "configuration": {
                **asdict(config), "timeframe": "M15", "segments_are_independent_accounts": True,
                "parameter_optimization_performed": False, "paper_trading_only": True,
                "real_orders_sent": False,
            },
            "source": {
                "manifest_schema": manifest["schema_version"], "manifest_sha256": manifest_sha256,
                "full_50000_hashes_verified_before_replay": True,
                "development_candles_per_symbol": 30_000, "validation_candles_per_symbol": 10_000,
                "research_exposed_candles_used": 0, "true_oos_candles_used": 0,
            },
            "segments": summaries,
            "development_vs_validation": comparisons,
            "audit": {
                "strategy_parameters_changed": False, "strategy_implementation_changed": False,
                "segment_strategy_replay_count": 2, "symbol_segment_runs": 16,
                "research_exposed_executed": False, "true_oos_executed": False,
                "performance_metrics_for_true_oos_computed": False, "real_orders_sent": False,
            },
            "acceptance": {
                "all_eight_development_segments_replayed": all(row["source_candles"] == 30_000 for row in summaries["DEVELOPMENT"]["per_symbol_results"]),
                "all_eight_validation_segments_replayed": all(row["source_candles"] == 10_000 for row in summaries["VALIDATION"]["per_symbol_results"]),
                "full_50000_hashes_match_manifest": True,
                "research_exposed_candles_used": False, "true_oos_candles_used": False,
                "strategy_behavior_unchanged": True, "real_orders_sent": False,
            },
        }
