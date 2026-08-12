"""Statistical robustness audit for frozen development/validation trades."""

from __future__ import annotations

from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit


class DevelopmentValidationRobustness:
    VERSION = "MSS_SPRINT92C4_DEVELOPMENT_VALIDATION_ROBUSTNESS_V1"
    SEGMENTS = ("DEVELOPMENT", "VALIDATION")

    def __init__(self):
        self.bootstrap = BootstrapRobustnessAudit()

    @staticmethod
    def normalize(payload, segment):
        records = []
        for raw in payload["segments"][segment]["trades"]:
            if raw["status"] != "CLOSED":
                continue
            profit = float(raw["profit"])
            records.append({
                "symbol": raw["canonical_symbol"], "asset_class": raw["asset_class"],
                "trade_id": int(raw["trade_id"]), "direction": raw["direction"],
                "entry_time": raw["entry_time"], "exit_time": raw["exit_time"],
                "realized_pnl": profit, "r_multiple": float(raw["r_multiple"]),
                "outcome": "WIN" if profit > 0 else "LOSS" if profit < 0 else "BREAKEVEN",
            })
        return sorted(records, key=lambda row: (row["symbol"], row["entry_time"], row["exit_time"], row["trade_id"]))

    @staticmethod
    def classify(development, validation, development_block, validation_block):
        results = (development, validation, development_block, validation_block)
        if not all(result.get("available") for result in results):
            return "NOT_RELIABLE"
        def positive(result):
            metrics = result["bootstrap_metrics"]
            return metrics["expectancy"]["ci_95"]["lower"] > 0 and metrics["mean_r"]["ci_95"]["lower"] > 0
        def negative(result):
            metrics = result["bootstrap_metrics"]
            return metrics["expectancy"]["ci_95"]["upper"] < 0 and metrics["mean_r"]["ci_95"]["upper"] < 0
        if all(positive(result) for result in results):
            return "ROBUST_POSITIVE"
        if all(negative(result) for result in results):
            return "ROBUST_NEGATIVE"
        point_positive_both = all(
            result["point_estimates"]["expectancy_account_currency"] > 0
            for result in (development, validation)
        )
        return "PROMISING_NOT_CONFIRMED" if point_positive_both else "NOT_RELIABLE"

    def build(self, payload, *, seed=None, resamples=None):
        seed = self.bootstrap.DEFAULT_SEED if seed is None else seed
        resamples = self.bootstrap.DEFAULT_RESAMPLES if resamples is None else resamples
        normalized = {segment: self.normalize(payload, segment) for segment in self.SEGMENTS}
        source_rows = {
            segment: {row["canonical_symbol"]: row for row in payload["segments"][segment]["per_symbol_results"]}
            for segment in self.SEGMENTS
        }
        per_symbol = {}
        reconciliation = {}
        for symbol in self.bootstrap.SYMBOLS:
            ordinary, blocks = {}, {}
            reconciliation[symbol] = {}
            for segment in self.SEGMENTS:
                trades = [row for row in normalized[segment] if row["symbol"] == symbol]
                ordinary[segment] = self.bootstrap.bootstrap(
                    trades, seed=seed, resamples=resamples, label=f"92c4:{segment}:{symbol}:ordinary",
                )
                blocks[segment] = self.bootstrap.bootstrap(
                    trades, seed=seed, resamples=resamples, label=f"92c4:{segment}:{symbol}:block",
                    method="moving_block_circular", block_length=self.bootstrap.BLOCK_LENGTH,
                )
                expected = source_rows[segment][symbol]
                reconciliation[symbol][segment] = {
                    "closed_trade_count_difference": len(trades) - expected["closed_trades"],
                    "net_pnl_difference": round(sum(row["realized_pnl"] for row in trades) - expected["net_profit"], 8),
                }
            per_symbol[symbol] = {
                "ordinary_bootstrap": ordinary,
                "moving_block_bootstrap": blocks,
                "classification": self.classify(
                    ordinary["DEVELOPMENT"], ordinary["VALIDATION"],
                    blocks["DEVELOPMENT"], blocks["VALIDATION"],
                ),
            }
        classifications = {symbol: row["classification"] for symbol, row in per_symbol.items()}
        return {
            "schema_version": self.VERSION,
            "mode": "FROZEN_TRADES_STATISTICAL_AUDIT_ONLY",
            "source": {
                "artifact": "reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json",
                "development_closed_trades": len(normalized["DEVELOPMENT"]),
                "validation_closed_trades": len(normalized["VALIDATION"]),
                "strategy_replay_run": False, "history_downloaded": False,
                "research_exposed_candles_used": 0, "true_oos_candles_used": 0,
            },
            "methodology": {
                "random_seed": seed, "resample_count": resamples,
                "ordinary_bootstrap": "N_DRAWS_WITH_REPLACEMENT_FROM_N_TRADES_WITHIN_SYMBOL_AND_SEGMENT",
                "dependence_check": "CIRCULAR_MOVING_BLOCK_BOOTSTRAP",
                "block_length_trades": self.bootstrap.BLOCK_LENGTH,
                "confidence_interval": "95_PERCENT_PERCENTILE_LINEAR_INTERPOLATION",
                "classification_rules": {
                    "ROBUST_POSITIVE": "ordinary and moving-block expectancy and mean-R 95% CI lower bounds > 0 in both Development and Validation",
                    "ROBUST_NEGATIVE": "ordinary and moving-block expectancy and mean-R 95% CI upper bounds < 0 in both Development and Validation",
                    "PROMISING_NOT_CONFIRMED": "observed expectancy > 0 in both segments but robust criteria not met",
                    "NOT_RELIABLE": "all other cases",
                },
                "multiple_comparison_policy": "NO_NULL_P_VALUES_MANUFACTURED_FROM_BOOTSTRAP_SIGN_PROBABILITIES; NO_FDR_SIGNIFICANCE_CLAIM",
            },
            "per_symbol_results": per_symbol,
            "final_classifications": classifications,
            "reconciliation": reconciliation,
            "validation": {
                "all_trade_counts_and_pnl_reconcile": all(
                    values[segment]["closed_trade_count_difference"] == 0
                    and values[segment]["net_pnl_difference"] == 0
                    for values in reconciliation.values() for segment in self.SEGMENTS
                ),
                "strategy_replay_run": False, "true_oos_used": False,
                "research_exposed_used": False,
            },
            "caveats": [
                "Development and Validation are pre-OOS historical segments; neither is True OOS.",
                "Bootstrap intervals describe uncertainty under resampling assumptions and do not prove future profitability.",
                "Moving-block resampling reduces but does not eliminate serial-dependence risk.",
                "Eight-symbol screening creates multiple-comparison risk; no formal FDR significance is claimed.",
                "No strategy, scoring, threshold, risk, or live-execution behavior was changed.",
            ],
        }
