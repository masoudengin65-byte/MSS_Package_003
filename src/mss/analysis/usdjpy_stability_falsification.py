"""Frozen-trade USDJPY stability and concentration diagnostics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit


class UsdJpyStabilityFalsification:
    VERSION = "MSS_SPRINT92C5_USDJPY_STABILITY_FALSIFICATION_V1"
    SEGMENTS = ("DEVELOPMENT", "VALIDATION")
    SYMBOL = "USDJPY"

    @staticmethod
    def normalize(payload, segment):
        rows = []
        for raw in payload["segments"][segment]["trades"]:
            if raw["canonical_symbol"] != "USDJPY" or raw["status"] != "CLOSED":
                continue
            rows.append({
                "trade_id": int(raw["trade_id"]), "direction": raw["direction"],
                "entry_time": raw["entry_time"], "exit_time": raw["exit_time"],
                "month": raw["entry_time"][:7], "profit": float(raw["profit"]),
                "r_multiple": float(raw["r_multiple"]),
            })
        return sorted(rows, key=lambda row: (row["entry_time"], row["exit_time"], row["trade_id"]))

    @staticmethod
    def metrics(trades):
        count = len(trades)
        profits = [row["profit"] for row in trades]
        wins = [value for value in profits if value > 0]
        losses = [-value for value in profits if value < 0]
        gross_profit, gross_loss = sum(wins), sum(losses)
        return {
            "trades": count, "net_pnl": round(sum(profits), 8),
            "expectancy": round(sum(profits) / count, 8) if count else None,
            "mean_r": round(sum(row["r_multiple"] for row in trades) / count, 8) if count else None,
            "win_rate": round(len(wins) / count, 8) if count else None,
            "profit_factor": round(gross_profit / gross_loss, 8) if gross_loss else None,
        }

    @classmethod
    def monthly(cls, trades):
        groups = defaultdict(list)
        for row in trades:
            groups[row["month"]].append(row)
        return [{"month": month, **cls.metrics(groups[month])} for month in sorted(groups)]

    @classmethod
    def leave_one_month_out(cls, trades):
        months = sorted({row["month"] for row in trades})
        return [{"excluded_month": month, **cls.metrics([row for row in trades if row["month"] != month])} for month in months]

    @classmethod
    def concentration(cls, trades, monthly):
        total = sum(row["profit"] for row in trades)
        positive_months = [row for row in monthly if row["net_pnl"] > 0]
        top_month = max(monthly, key=lambda row: row["net_pnl"])
        top_five = sorted((row["profit"] for row in trades), reverse=True)[:5]
        return {
            "positive_month_count": len(positive_months), "total_month_count": len(monthly),
            "positive_month_share": round(len(positive_months) / len(monthly), 8) if monthly else None,
            "best_month": top_month["month"], "best_month_net_pnl": top_month["net_pnl"],
            "best_month_share_of_total_net": round(top_month["net_pnl"] / total, 8) if total else None,
            "top_five_trade_net_pnl": round(sum(top_five), 8),
            "top_five_share_of_total_net": round(sum(top_five) / total, 8) if total else None,
        }

    @classmethod
    def segment_audit(cls, trades):
        monthly = cls.monthly(trades)
        directions = {direction: cls.metrics([row for row in trades if row["direction"] == direction]) for direction in ("BUY", "SELL")}
        leave_out = cls.leave_one_month_out(trades)
        concentration = cls.concentration(trades, monthly)
        checks = {
            "overall_net_positive": cls.metrics(trades)["net_pnl"] > 0,
            "buy_net_positive": directions["BUY"]["net_pnl"] > 0,
            "sell_net_positive": directions["SELL"]["net_pnl"] > 0,
            "majority_of_months_positive": concentration["positive_month_share"] > 0.5,
            "all_leave_one_month_out_net_positive": all(row["net_pnl"] > 0 for row in leave_out),
            "best_month_not_more_than_total_net": concentration["best_month_share_of_total_net"] <= 1.0,
            "top_five_trades_not_more_than_total_net": concentration["top_five_share_of_total_net"] <= 1.0,
        }
        return {
            "overall": cls.metrics(trades), "monthly": monthly, "directions": directions,
            "leave_one_month_out": leave_out, "concentration": concentration,
            "predefined_falsification_checks": checks,
            "survives_all_predefined_checks": all(checks.values()),
        }

    def build(self, payload):
        source = {segment: self.normalize(payload, segment) for segment in self.SEGMENTS}
        audits = {segment: self.segment_audit(source[segment]) for segment in self.SEGMENTS}
        expected = {
            segment: next(row for row in payload["segments"][segment]["per_symbol_results"] if row["canonical_symbol"] == self.SYMBOL)
            for segment in self.SEGMENTS
        }
        reconciliation = {segment: {
            "closed_trade_count_difference": len(source[segment]) - expected[segment]["closed_trades"],
            "net_pnl_difference": round(sum(row["profit"] for row in source[segment]) - expected[segment]["net_profit"], 8),
        } for segment in self.SEGMENTS}
        survives = all(audits[segment]["survives_all_predefined_checks"] for segment in self.SEGMENTS)
        return {
            "schema_version": self.VERSION, "mode": "FROZEN_TRADES_FALSIFICATION_ONLY",
            "source": {
                "artifact": "reports/MSS_Sprint92C3_Extended_Development_Validation_Replay.json",
                "symbol": self.SYMBOL, "strategy_replay_run": False, "history_downloaded": False,
                "research_exposed_candles_used": 0, "true_oos_candles_used": 0,
            },
            "methodology": {
                "timezone": "SOURCE_TRADE_TIMESTAMPS_NAIVE_BROKER_TIME_AS_FROZEN",
                "month_assignment": "ENTRY_TIME_CALENDAR_MONTH",
                "tests_predefined_before_result_inspection": [
                    "overall net positive", "BUY and SELL independently net positive",
                    "strict majority of calendar months net positive", "every leave-one-month-out net positive",
                    "best month contribution <= total net", "top five winning trades contribution <= total net",
                ],
                "threshold_interpretation": "DESCRIPTIVE_FALSIFICATION_GATES_NOT_HYPOTHESIS_TEST_P_VALUES",
                "optimization_or_filter_creation": False,
            },
            "segment_results": audits, "reconciliation": reconciliation,
            "final_assessment": "SURVIVES_ALL_PREDEFINED_CHECKS" if survives else "FAILS_ONE_OR_MORE_STABILITY_CHECKS",
            "production_change_justified": False,
            "validation": {
                "all_source_trades_reconciled": all(row["closed_trade_count_difference"] == 0 and row["net_pnl_difference"] == 0 for row in reconciliation.values()),
                "strategy_replay_run": False, "true_oos_used": False, "research_exposed_used": False,
            },
            "caveats": [
                "This audit follows a symbol selected after observing C3/C4 results and therefore cannot provide unbiased discovery evidence.",
                "Calendar months differ in trade count and market conditions; comparisons are descriptive.",
                "Concentration gates are sensitivity diagnostics, not formal significance tests.",
                "Development and Validation are not True OOS; production changes remain unjustified.",
            ],
        }
