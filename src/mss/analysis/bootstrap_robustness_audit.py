"""Deterministic bootstrap robustness analysis for frozen replay trades."""

from __future__ import annotations

import hashlib
import math
import random
from statistics import median


class BootstrapRobustnessAudit:
    SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "XAUUSD", "BTCUSD", "ETHUSD")
    ASSET_CLASSES = ("FOREX", "METAL", "CRYPTO")
    DEFAULT_SEED = 9_202_001
    DEFAULT_RESAMPLES = 10_000
    BLOCK_LENGTH = 5
    MIN_SAMPLE = 20

    @staticmethod
    def normalize_trades(payload):
        records = []
        for raw in payload["trades"]:
            if raw["status"] != "CLOSED":
                continue
            profit = float(raw["profit"])
            records.append({
                "symbol": raw["canonical_symbol"],
                "asset_class": raw["asset_class"],
                "trade_id": int(raw["trade_id"]),
                "direction": raw["direction"],
                "entry_time": raw["entry_time"],
                "exit_time": raw["exit_time"],
                "realized_pnl": profit,
                "r_multiple": float(raw["r_multiple"]),
                "outcome": "WIN" if profit > 0 else "LOSS" if profit < 0 else "BREAKEVEN",
            })
        return sorted(records, key=lambda row: (row["symbol"], row["entry_time"], row["exit_time"], row["trade_id"]))

    @staticmethod
    def percentile(values, quantile):
        if not values:
            return None
        ordered = sorted(values)
        position = (len(ordered) - 1) * quantile
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            return ordered[low]
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    @classmethod
    def interval(cls, values, level):
        alpha = (1.0 - level) / 2.0
        return {
            "level_percent": int(round(level * 100)),
            "lower": cls.percentile(values, alpha),
            "upper": cls.percentile(values, 1.0 - alpha),
        }

    @staticmethod
    def _derived_seed(seed, label):
        digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big")

    @staticmethod
    def point_metrics(trades):
        count = len(trades)
        profits = [row["realized_pnl"] for row in trades]
        rs = [row["r_multiple"] for row in trades]
        wins = [value for value in profits if value > 0]
        losses = [-value for value in profits if value < 0]
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        return {
            "trades": count,
            "expectancy_account_currency": sum(profits) / count if count else None,
            "mean_r": sum(rs) / count if count else None,
            "median_r": median(rs) if rs else None,
            "win_rate": len(wins) / count if count else None,
            "profit_factor": gross_profit / gross_loss if gross_loss else None,
            "profit_factor_status": "DEFINED" if gross_loss else "UNDEFINED_ZERO_GROSS_LOSS",
            "net_pnl_account_currency": sum(profits),
            "payoff_ratio": (sum(wins) / len(wins)) / (sum(losses) / len(losses)) if wins and losses else None,
        }

    @classmethod
    def _sample_indices(cls, rng, count, method, block_length):
        if method == "ordinary":
            return [rng.randrange(count) for _ in range(count)]
        indices = []
        while len(indices) < count:
            start = rng.randrange(count)
            indices.extend((start + offset) % count for offset in range(block_length))
        return indices[:count]

    def bootstrap(self, trades, *, seed=None, resamples=None, label="sample", method="ordinary", block_length=None):
        seed = self.DEFAULT_SEED if seed is None else seed
        resamples = self.DEFAULT_RESAMPLES if resamples is None else resamples
        block_length = self.BLOCK_LENGTH if block_length is None else block_length
        if len(trades) < self.MIN_SAMPLE:
            return {
                "available": False, "reason": f"FEWER_THAN_{self.MIN_SAMPLE}_TRADES",
                "sample_size": len(trades), "resamples": 0, "method": method,
            }
        ordered = sorted(trades, key=lambda row: (row["entry_time"], row["exit_time"], row["trade_id"]))
        rng = random.Random(self._derived_seed(seed, label))
        profits = [row["realized_pnl"] for row in ordered]
        rs = [row["r_multiple"] for row in ordered]
        n = len(ordered)
        distributions = {name: [] for name in ("expectancy", "mean_r", "win_rate", "profit_factor", "net_pnl")}
        invalid_pf = 0
        for _ in range(resamples):
            indexes = self._sample_indices(rng, n, method, block_length)
            sample_profits = [profits[index] for index in indexes]
            net = sum(sample_profits)
            gross_profit = sum(value for value in sample_profits if value > 0)
            gross_loss = -sum(value for value in sample_profits if value < 0)
            distributions["expectancy"].append(net / n)
            distributions["mean_r"].append(sum(rs[index] for index in indexes) / n)
            distributions["win_rate"].append(sum(value > 0 for value in sample_profits) / n)
            distributions["net_pnl"].append(net)
            if gross_loss:
                distributions["profit_factor"].append(gross_profit / gross_loss)
            else:
                invalid_pf += 1

        point = self.point_metrics(ordered)
        specs = {
            "expectancy": (point["expectancy_account_currency"], 0.0),
            "mean_r": (point["mean_r"], 0.0),
            "win_rate": (point["win_rate"], 0.5),
            "net_pnl": (point["net_pnl_account_currency"], 0.0),
            "profit_factor": (point["profit_factor"], 1.0),
        }
        summaries = {}
        for metric, (estimate, threshold) in specs.items():
            values = distributions[metric]
            summaries[metric] = {
                "point_estimate": estimate,
                "bootstrap_mean": sum(values) / len(values) if values else None,
                "ci_95": self.interval(values, 0.95),
                "ci_90": self.interval(values, 0.90),
                "probability_above_threshold": sum(value > threshold for value in values) / len(values) if values else None,
                "threshold": threshold,
                "valid_samples": len(values),
            }
            if metric == "profit_factor":
                summaries[metric]["invalid_zero_gross_loss_samples"] = invalid_pf
                summaries[metric]["probability_denominator"] = "VALID_PF_SAMPLES_ONLY"
        return {
            "available": True, "reason": None, "method": method,
            "block_length": block_length if method == "moving_block_circular" else None,
            "sample_size": n, "resamples": resamples,
            "seed": seed, "derived_seed_label": label,
            "point_estimates": point, "bootstrap_metrics": summaries,
        }

    @staticmethod
    def split_halves(trades):
        ordered = sorted(trades, key=lambda row: (row["entry_time"], row["exit_time"], row["trade_id"]))
        split = len(ordered) // 2
        return ordered[:split], ordered[split:]

    @staticmethod
    def group_directions(trades):
        return {
            direction: sorted(
                (row for row in trades if row["direction"] == direction),
                key=lambda row: (row["entry_time"], row["exit_time"], row["trade_id"]),
            )
            for direction in ("BUY", "SELL")
        }

    @staticmethod
    def classify(result, temporal_classification, *, block_result=None):
        if not result.get("available"):
            return "NOT_RELIABLE"
        metrics = result["bootstrap_metrics"]
        expectancy = metrics["expectancy"]
        mean_r = metrics["mean_r"]
        point_expectancy = expectancy["point_estimate"]
        robust_positive = (
            point_expectancy > 0
            and expectancy["ci_95"]["lower"] > 0
            and mean_r["ci_95"]["lower"] > 0
            and expectancy["probability_above_threshold"] >= 0.975
            and mean_r["probability_above_threshold"] >= 0.975
            and temporal_classification not in ("MIXED", "INSUFFICIENT")
        )
        if block_result is not None:
            block_expectancy = block_result["bootstrap_metrics"]["expectancy"]
            block_mean_r = block_result["bootstrap_metrics"]["mean_r"]
            robust_positive = robust_positive and block_expectancy["ci_95"]["lower"] > 0 and block_mean_r["ci_95"]["lower"] > 0
        robust_negative = (
            point_expectancy < 0
            and expectancy["ci_95"]["upper"] < 0
            and mean_r["ci_95"]["upper"] < 0
            and expectancy["probability_above_threshold"] <= 0.025
            and mean_r["probability_above_threshold"] <= 0.025
            and temporal_classification == "STABLE_NEGATIVE"
        )
        if robust_positive:
            return "ROBUST_POSITIVE"
        if robust_negative:
            return "ROBUST_NEGATIVE"
        promising = point_expectancy > 0 and (
            expectancy["probability_above_threshold"] >= 0.80
            or expectancy["ci_90"]["lower"] > 0
            or metrics["profit_factor"]["probability_above_threshold"] is not None
            and metrics["profit_factor"]["probability_above_threshold"] >= 0.80
        )
        return "PROMISING_NOT_CONFIRMED" if promising else "NOT_RELIABLE"

    @staticmethod
    def classify_pooled(result):
        if not result.get("available"):
            return "NOT_RELIABLE"
        expectancy = result["bootstrap_metrics"]["expectancy"]
        mean_r = result["bootstrap_metrics"]["mean_r"]
        if expectancy["ci_95"]["lower"] > 0 and mean_r["ci_95"]["lower"] > 0:
            return "ROBUST_POSITIVE"
        if expectancy["ci_95"]["upper"] < 0 and mean_r["ci_95"]["upper"] < 0:
            return "ROBUST_NEGATIVE"
        if expectancy["point_estimate"] > 0 and expectancy["probability_above_threshold"] >= 0.80:
            return "PROMISING_NOT_CONFIRMED"
        return "NOT_RELIABLE"

    def build(self, payload, temporal_payload, *, seed=None, resamples=None):
        seed = self.DEFAULT_SEED if seed is None else seed
        resamples = self.DEFAULT_RESAMPLES if resamples is None else resamples
        records = self.normalize_trades(payload)
        by_symbol = {symbol: [row for row in records if row["symbol"] == symbol] for symbol in self.SYMBOLS}
        temporal = {symbol: temporal_payload["temporal_classifications"][symbol]["classification"] for symbol in self.SYMBOLS}
        per_symbol = {}
        for symbol, trades in by_symbol.items():
            per_symbol[symbol] = self.bootstrap(trades, seed=seed, resamples=resamples, label=f"symbol:{symbol}")

        xau_block = self.bootstrap(
            by_symbol["XAUUSD"], seed=seed, resamples=resamples, label="block:XAUUSD",
            method="moving_block_circular", block_length=self.BLOCK_LENGTH,
        )
        direction_groups = self.group_directions(by_symbol["XAUUSD"])
        directional = {
            direction: self.bootstrap(
                direction_groups[direction],
                seed=seed, resamples=resamples, label=f"direction:XAUUSD:{direction}",
            ) for direction in ("BUY", "SELL")
        }
        half_results = {}
        for symbol in ("XAUUSD", "AUDUSD"):
            first, second = self.split_halves(by_symbol[symbol])
            half_results[symbol] = {
                "split_rule": "FIRST_FLOOR_N_OVER_2_SECOND_REMAINDER",
                "first_half": self.bootstrap(first, seed=seed, resamples=resamples, label=f"half:{symbol}:first"),
                "second_half": self.bootstrap(second, seed=seed, resamples=resamples, label=f"half:{symbol}:second"),
            }
        asset_classes = {}
        for asset_class in self.ASSET_CLASSES:
            result = self.bootstrap(
                [row for row in records if row["asset_class"] == asset_class],
                seed=seed, resamples=resamples, label=f"asset_class:{asset_class}",
            )
            asset_classes[asset_class] = {**result, "classification": self.classify_pooled(result)}
        combined = self.bootstrap(records, seed=seed, resamples=resamples, label="asset_class:COMBINED")
        asset_classes["COMBINED"] = {**combined, "classification": self.classify_pooled(combined)}

        classifications = {}
        for symbol, result in per_symbol.items():
            classifications[symbol] = self.classify(
                result, temporal[symbol], block_result=xau_block if symbol == "XAUUSD" else None,
            )
        expected = {row["canonical_symbol"]: row for row in payload["per_symbol_results"]}
        reconciliation = {
            symbol: {
                "closed_trade_count_difference": len(by_symbol[symbol]) - expected[symbol]["closed_trades"],
                "net_pnl_difference": round(sum(row["realized_pnl"] for row in by_symbol[symbol]) - expected[symbol]["net_profit"], 8),
            } for symbol in self.SYMBOLS
        }
        xau_halves_positive = all(
            half_results["XAUUSD"][name]["bootstrap_metrics"]["expectancy"]["ci_95"]["lower"] > 0
            for name in ("first_half", "second_half")
        )
        return {
            "schema_version": "MSS_SPRINT92B2_CROSS_ASSET_ROBUSTNESS_BOOTSTRAP_V1",
            "source": {
                "artifact": "reports/MSS_Multi_Asset_Historical_Replay_v2.json",
                "supporting_artifact": "reports/MSS_Sprint92B1_Temporal_Stability_Audit.json",
                "frozen_closed_trade_count": len(records), "strategy_replay_run": False,
                "history_downloaded": False, "signals_reconstructed": False,
            },
            "methodology": {
                "primary_unit": "INDIVIDUAL_CLOSED_TRADE_WITHIN_SYMBOL",
                "random_seed": seed, "resample_count": resamples,
                "confidence_intervals": "PERCENTILE_BOOTSTRAP_LINEAR_INTERPOLATION",
                "ordinary_sampling": "N_DRAWS_WITH_REPLACEMENT_FROM_N_TRADES",
                "secondary_sampling": "CIRCULAR_MOVING_BLOCK_BOOTSTRAP",
                "block_length_trades": self.BLOCK_LENGTH,
                "minimum_subgroup_trades": self.MIN_SAMPLE,
                "profit_factor_handling": "ZERO_GROSS_LOSS_SAMPLES_REPORTED_INVALID; PF_SUMMARIES_USE_VALID_SAMPLES_ONLY",
                "half_split_rule": "FIRST_FLOOR_N_OVER_2_SECOND_REMAINDER; ODD_EXTRA_TO_SECOND",
                "primary_multiple_comparison_metric": "MEAN_R_GREATER_THAN_ZERO",
                "classification_rules": {
                    "ROBUST_POSITIVE": "ordinary 95% expectancy and mean-R CI lower bounds > 0; both positive probabilities >= .975; temporal classification not MIXED/INSUFFICIENT; XAUUSD also requires positive block-CI lower bounds",
                    "ROBUST_NEGATIVE": "ordinary 95% expectancy and mean-R CI upper bounds < 0; both positive probabilities <= .025; temporal classification STABLE_NEGATIVE",
                    "PROMISING_NOT_CONFIRMED": "positive observed expectancy and >= .80 sign probability, positive 90% expectancy lower bound, or >= .80 probability PF > 1; robust-positive criteria not met",
                    "NOT_RELIABLE": "all other sufficient or insufficient cases",
                    "POOLED_CLASS_RESULTS": "descriptive analogous CI signs only; not an independent-symbol portfolio model",
                },
            },
            "frozen_trade_records": records,
            "per_symbol_results": per_symbol,
            "xauusd_deep_analysis": {
                "ordinary_bootstrap": per_symbol["XAUUSD"],
                "moving_block_bootstrap": xau_block,
                "directional_bootstrap": directional,
                "half_period_bootstrap": half_results["XAUUSD"],
                "temporal_classification": temporal["XAUUSD"],
                "positive_supported_in_both_halves_at_95_percent": xau_halves_positive,
                "effect_size_interpretation": "Observed account-currency expectancy and mean R are positive, but robustness depends on interval, temporal, directional, and dependence checks.",
            },
            "directional_analysis": {"XAUUSD": directional},
            "half_period_analysis": half_results,
            "asset_class_results": asset_classes,
            "multiple_comparison_treatment": {
                "method_requested": "BENJAMINI_HOCHBERG_FDR",
                "status": "NOT_AVAILABLE",
                "reason": "Empirical bootstrap sign probabilities are not null-hypothesis p-values; converting them to p-values would not provide a defensible BH input.",
                "action": "No FDR-adjusted significance is claimed; final labels require conservative interval and temporal consistency criteria across all eight symbols.",
            },
            "block_bootstrap_comparison": {"XAUUSD": {"ordinary": per_symbol["XAUUSD"], "moving_block": xau_block}},
            "temporal_classifications_from_sprint92b1": temporal,
            "final_classifications": classifications,
            "validation": {
                "closed_trade_count_expected": 821,
                "closed_trade_count_actual": len(records),
                "closed_trade_count_matches": len(records) == 821,
                "per_symbol_reconciliation": reconciliation,
                "all_per_symbol_reconciled": all(
                    row["closed_trade_count_difference"] == 0 and row["net_pnl_difference"] == 0
                    for row in reconciliation.values()
                ),
                "deterministic_rebuild": True,
            },
            "caveats": [
                "In-sample statistical description does not establish out-of-sample performance or causality.",
                "Trade bootstrap assumes exchangeability; the block check reduces but does not eliminate serial-dependence concerns.",
                "Pooled asset-class trades are descriptive and are not an independent-symbol portfolio allocation model.",
                "Directional and half-period results are diagnostics and do not justify production filters.",
                "Multiple-comparison FDR is unavailable because the bootstrap design does not yield defensible null p-values.",
                "No strategy, score, threshold, risk, signal, or live-execution behavior was changed.",
            ],
        }
