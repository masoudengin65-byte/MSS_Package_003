"""Development-only outcome analysis of the immutable Sprint 92H.4 replay."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit
from mss.analysis.temporal_stability_audit import TemporalStabilityAudit


class ImmutableDevelopmentOutcomeAnalysis:
    VERSION = "MSS_SPRINT92H5_IMMUTABLE_DEVELOPMENT_OUTCOME_ANALYSIS_V1"

    SYMBOLS = BootstrapRobustnessAudit.SYMBOLS
    SEED = 9_205_001
    RESAMPLES = 10_000
    BLOCK_LENGTH = 5

    def __init__(self):
        self.bootstrap_engine = BootstrapRobustnessAudit()
        self.temporal_engine = TemporalStabilityAudit()

    @staticmethod
    def _rolling_summary(rolling):
        if not rolling.get("available"):
            return {
                "available": False,
                "reason": rolling.get("reason"),
                "window_size": rolling.get("window_size"),
            }

        windows = rolling["windows"]
        expectations = [row["expectancy"] for row in windows]

        return {
            "available": True,
            "window_size": rolling["window_size"],
            "window_count": len(windows),
            "minimum_expectancy": min(expectations),
            "maximum_expectancy": max(expectations),
            "mean_rolling_expectancy": mean(expectations),
            "positive_window_count": sum(x > 0 for x in expectations),
            "negative_window_count": sum(x < 0 for x in expectations),
            "positive_window_share": (
                sum(x > 0 for x in expectations) / len(expectations)
                if expectations else None
            ),
        }

    @staticmethod
    def _classification(ordinary, block, temporal_classification):
        if not ordinary.get("available") or not block.get("available"):
            return "DEVELOPMENT_NOT_RELIABLE"

        o = ordinary["bootstrap_metrics"]
        b = block["bootstrap_metrics"]

        robust_positive = (
            temporal_classification == "STABLE_POSITIVE"
            and o["expectancy"]["ci_95"]["lower"] > 0
            and o["mean_r"]["ci_95"]["lower"] > 0
            and b["expectancy"]["ci_95"]["lower"] > 0
            and b["mean_r"]["ci_95"]["lower"] > 0
            and o["expectancy"]["probability_above_threshold"] >= 0.975
            and b["expectancy"]["probability_above_threshold"] >= 0.975
        )

        robust_negative = (
            temporal_classification == "STABLE_NEGATIVE"
            and o["expectancy"]["ci_95"]["upper"] < 0
            and o["mean_r"]["ci_95"]["upper"] < 0
            and b["expectancy"]["ci_95"]["upper"] < 0
            and b["mean_r"]["ci_95"]["upper"] < 0
            and o["expectancy"]["probability_above_threshold"] <= 0.025
            and b["expectancy"]["probability_above_threshold"] <= 0.025
        )

        if robust_positive:
            return "DEVELOPMENT_ROBUST_POSITIVE"

        if robust_negative:
            return "DEVELOPMENT_ROBUST_NEGATIVE"

        positive_point = (
            ordinary["point_estimates"]["expectancy_account_currency"] > 0
        )

        promising = (
            positive_point
            and o["expectancy"]["probability_above_threshold"] >= 0.80
            and b["expectancy"]["probability_above_threshold"] >= 0.80
        )

        if promising:
            return "DEVELOPMENT_PROMISING_NOT_CONFIRMED"

        return "DEVELOPMENT_NOT_RELIABLE"

    def build(self, payload):
        if payload["schema_version"] != "MSS_SPRINT92H4_IMMUTABLE_DEVELOPMENT_REPLAY_V1":
            raise RuntimeError("unexpected H4 source schema")

        if not payload["acceptance"]["all_eight_sources_verified"]:
            raise RuntimeError("H4 immutable source verification did not pass")

        if payload["audit"]["authoritative_development_replay_runs"] != 1:
            raise RuntimeError("H4 authoritative replay count is not exactly one")

        bootstrap_records = self.bootstrap_engine.normalize_trades(payload)
        temporal_records = self.temporal_engine.normalize_trades(payload)

        if len(bootstrap_records) != 2766:
            raise RuntimeError(
                f"expected 2766 closed trades, got {len(bootstrap_records)}"
            )

        b_by_symbol = {
            symbol: [
                row for row in bootstrap_records
                if row["symbol"] == symbol
            ]
            for symbol in self.SYMBOLS
        }

        t_by_symbol = {
            symbol: [
                row for row in temporal_records
                if row["symbol"] == symbol
            ]
            for symbol in self.SYMBOLS
        }

        expected = {
            row["canonical_symbol"]: row
            for row in payload["per_symbol_results"]
        }

        per_symbol = {}
        reconciliation = {}

        for symbol in self.SYMBOLS:
            btrades = b_by_symbol[symbol]
            ttrades = t_by_symbol[symbol]

            point = self.bootstrap_engine.point_metrics(btrades)

            monthly = self.temporal_engine.monthly(ttrades)
            halves = self.temporal_engine.halves(ttrades)
            rolling = self.temporal_engine.rolling(ttrades)
            directional_temporal = self.temporal_engine.directional(ttrades)
            temporal_class = self.temporal_engine.classify(
                ttrades,
                halves,
                monthly,
            )

            ordinary = self.bootstrap_engine.bootstrap(
                btrades,
                seed=self.SEED,
                resamples=self.RESAMPLES,
                label=f"H5:{symbol}:ordinary",
                method="ordinary",
            )

            block = self.bootstrap_engine.bootstrap(
                btrades,
                seed=self.SEED,
                resamples=self.RESAMPLES,
                label=f"H5:{symbol}:block",
                method="moving_block_circular",
                block_length=self.BLOCK_LENGTH,
            )

            direction_groups = self.bootstrap_engine.group_directions(btrades)

            directional_bootstrap = {
                direction: self.bootstrap_engine.bootstrap(
                    trades,
                    seed=self.SEED,
                    resamples=self.RESAMPLES,
                    label=f"H5:{symbol}:{direction}",
                    method="ordinary",
                )
                for direction, trades in direction_groups.items()
            }

            first, second = self.bootstrap_engine.split_halves(btrades)

            half_bootstrap = {
                "split_rule": "FIRST_FLOOR_N_OVER_2_SECOND_REMAINDER",
                "first_half": self.bootstrap_engine.bootstrap(
                    first,
                    seed=self.SEED,
                    resamples=self.RESAMPLES,
                    label=f"H5:{symbol}:half:first",
                    method="ordinary",
                ),
                "second_half": self.bootstrap_engine.bootstrap(
                    second,
                    seed=self.SEED,
                    resamples=self.RESAMPLES,
                    label=f"H5:{symbol}:half:second",
                    method="ordinary",
                ),
            }

            final_classification = self._classification(
                ordinary,
                block,
                temporal_class["classification"],
            )

            per_symbol[symbol] = {
                "point_metrics": point,
                "monthly_results": monthly,
                "half_period_temporal": halves,
                "rolling_summary": self._rolling_summary(rolling),
                "directional_temporal": directional_temporal,
                "temporal_classification": temporal_class,
                "ordinary_bootstrap": ordinary,
                "moving_block_bootstrap": block,
                "directional_bootstrap": directional_bootstrap,
                "half_period_bootstrap": half_bootstrap,
                "development_evidence_classification": final_classification,
            }

            reconciliation[symbol] = {
                "expected_closed_trades": expected[symbol]["closed_trades"],
                "actual_closed_trades": len(btrades),
                "closed_trade_count_difference": (
                    len(btrades) - expected[symbol]["closed_trades"]
                ),
                "expected_net_pnl": expected[symbol]["net_profit"],
                "actual_net_pnl": round(
                    sum(row["realized_pnl"] for row in btrades),
                    2,
                ),
                "net_pnl_difference": round(
                    sum(row["realized_pnl"] for row in btrades)
                    - expected[symbol]["net_profit"],
                    8,
                ),
            }

        asset_groups = defaultdict(list)

        for row in bootstrap_records:
            asset_groups[row["asset_class"]].append(row)

        asset_groups["COMBINED"] = list(bootstrap_records)

        pooled = {}

        for name in ("FOREX", "METAL", "CRYPTO", "COMBINED"):
            trades = asset_groups[name]

            ordinary = self.bootstrap_engine.bootstrap(
                trades,
                seed=self.SEED,
                resamples=self.RESAMPLES,
                label=f"H5:pooled:{name}:ordinary",
            )

            block = self.bootstrap_engine.bootstrap(
                trades,
                seed=self.SEED,
                resamples=self.RESAMPLES,
                label=f"H5:pooled:{name}:block",
                method="moving_block_circular",
                block_length=self.BLOCK_LENGTH,
            )

            pooled[name] = {
                "point_metrics": self.bootstrap_engine.point_metrics(trades),
                "ordinary_bootstrap": ordinary,
                "moving_block_bootstrap": block,
            }

        deep_symbols = {}

        for symbol in ("GBPUSD", "USDJPY", "XAUUSD"):
            row = per_symbol[symbol]

            deep_symbols[symbol] = {
                "point_metrics": row["point_metrics"],
                "temporal_classification": row["temporal_classification"],
                "monthly_results": row["monthly_results"],
                "half_period_temporal": row["half_period_temporal"],
                "rolling_summary": row["rolling_summary"],
                "directional_temporal": row["directional_temporal"],
                "ordinary_bootstrap": row["ordinary_bootstrap"],
                "moving_block_bootstrap": row["moving_block_bootstrap"],
                "directional_bootstrap": row["directional_bootstrap"],
                "half_period_bootstrap": row["half_period_bootstrap"],
                "development_evidence_classification": (
                    row["development_evidence_classification"]
                ),
            }

        classifications = {
            symbol: per_symbol[symbol]["development_evidence_classification"]
            for symbol in self.SYMBOLS
        }

        return {
            "schema_version": self.VERSION,
            "mode": "IMMUTABLE_DEVELOPMENT_OUTCOME_ANALYSIS_ONLY",
            "baseline_commit": "87657dd",
            "source": {
                "artifact": (
                    "reports/"
                    "MSS_Sprint92H4_Immutable_Development_Replay.json"
                ),
                "closed_trade_count": len(bootstrap_records),
                "strategy_replay_run": False,
                "mt5_accessed": False,
                "candles_loaded": False,
                "validation_accessed": False,
                "external_history_accessed": False,
                "true_future_oos_used": False,
            },
            "methodology": {
                "analysis_scope": "DEVELOPMENT_ONLY_ALREADY_EXPOSED_OUTCOMES",
                "bootstrap_seed": self.SEED,
                "bootstrap_resamples": self.RESAMPLES,
                "ordinary_bootstrap": True,
                "moving_block_bootstrap": True,
                "moving_block_length": self.BLOCK_LENGTH,
                "monthly_assignment": "ENTRY_TIMESTAMP_CALENDAR_MONTH",
                "half_split": (
                    "FIRST_FLOOR_N_OVER_2_SECOND_REMAINDER"
                ),
                "rolling_window_trades": 20,
                "classification_rules": {
                    "DEVELOPMENT_ROBUST_POSITIVE": (
                        "STABLE_POSITIVE temporal classification plus "
                        "ordinary and block 95% expectancy and mean-R "
                        "lower bounds above zero and positive expectancy "
                        "probabilities >= 0.975"
                    ),
                    "DEVELOPMENT_ROBUST_NEGATIVE": (
                        "STABLE_NEGATIVE temporal classification plus "
                        "ordinary and block 95% expectancy and mean-R "
                        "upper bounds below zero and positive expectancy "
                        "probabilities <= 0.025"
                    ),
                    "DEVELOPMENT_PROMISING_NOT_CONFIRMED": (
                        "positive observed expectancy with ordinary and "
                        "block probability expectancy > 0 both >= 0.80, "
                        "without satisfying robust-positive criteria"
                    ),
                    "DEVELOPMENT_NOT_RELIABLE": "all other cases",
                },
            },
            "per_symbol_results": per_symbol,
            "deep_audit": deep_symbols,
            "asset_class_results": pooled,
            "final_classifications": classifications,
            "reconciliation": {
                "expected_closed_trade_count": 2766,
                "actual_closed_trade_count": len(bootstrap_records),
                "closed_trade_count_matches": len(bootstrap_records) == 2766,
                "per_symbol": reconciliation,
                "all_symbols_reconciled": all(
                    row["closed_trade_count_difference"] == 0
                    and row["net_pnl_difference"] == 0
                    for row in reconciliation.values()
                ),
            },
            "production_governance": {
                "strategy_change_authorized": False,
                "symbol_filter_change_authorized": False,
                "direction_filter_change_authorized": False,
                "risk_change_authorized": False,
                "reason": (
                    "H5 uses consumed Development outcomes only; "
                    "no Development-only finding can authorize "
                    "production behavior."
                ),
            },
            "data_governance": {
                "development_outcomes_exposed": True,
                "validation_remains_closed": True,
                "external_history_not_accessed": True,
                "true_future_oos_remains_sealed": True,
            },
            "audit": {
                "strategy_replay_run": False,
                "outcomes_recomputed": False,
                "mt5_accessed": False,
                "candles_loaded": False,
                "validation_accessed": False,
                "external_history_accessed": False,
                "true_future_oos_used": False,
                "strategy_code_changed": False,
                "production_change_justified": False,
            },
            "caveats": [
                "Development outcomes are already exposed and are not confirmatory evidence.",
                "Bootstrap intervals do not establish future out-of-sample profitability.",
                "Ordinary bootstrap assumes exchangeability of trades.",
                "Moving-block bootstrap reduces but does not eliminate serial-dependence concerns.",
                "Directional, monthly, half-period, and rolling analyses are diagnostic only.",
                "No post-hoc direction or symbol filter may be promoted from H5 without a new preregistered validation protocol.",
            ],
        }
