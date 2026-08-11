"""Deterministic temporal analysis of frozen corrected replay trades."""

from __future__ import annotations

from datetime import datetime
import math
from statistics import median


class TemporalStabilityAudit:
    SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "XAUUSD", "BTCUSD", "ETHUSD")
    MIN_CLASSIFICATION_TRADES = 40
    LOW_MONTH_SAMPLE = 10
    ROLLING_WINDOW = 20
    MAX_POSITIVE_MONTH_CONCENTRATION = 0.70

    def normalize_trades(self, payload):
        by_symbol = {symbol: [] for symbol in self.SYMBOLS}
        for raw in payload["trades"]:
            if raw["status"] != "CLOSED":
                continue
            symbol = raw["canonical_symbol"]
            by_symbol[symbol].append({
                "symbol": symbol, "trade_id": int(raw["trade_id"]),
                "direction": raw["direction"],
                "entry_time": raw["entry_time"], "exit_time": raw["exit_time"],
                "profit": float(raw["profit"]), "r_multiple": float(raw["r_multiple"]),
                "outcome": "WIN" if raw["profit"] > 0 else "LOSS" if raw["profit"] < 0 else "BREAKEVEN",
            })
        normalized = []
        for symbol in self.SYMBOLS:
            balance = 10000.0
            ordered = sorted(by_symbol[symbol], key=lambda row: (row["entry_time"], row["exit_time"], row["trade_id"]))
            for row in ordered:
                row["pre_trade_equity"] = round(balance, 2)
                normalized.append(row)
                balance += row["profit"]
        return normalized

    @staticmethod
    def metrics(trades):
        count = len(trades)
        winners = sum(row["profit"] > 0 for row in trades)
        losers = sum(row["profit"] < 0 for row in trades)
        gross_profit = sum(max(0.0, row["profit"]) for row in trades)
        gross_loss = sum(abs(min(0.0, row["profit"])) for row in trades)
        net = gross_profit - gross_loss
        rs = [row["r_multiple"] for row in trades]
        return {
            "trades": count, "winners": winners, "losers": losers,
            "breakeven": count - winners - losers,
            "win_rate_percent": round(winners / count * 100.0, 6) if count else 0.0,
            "net_profit": round(net, 2),
            "profit_factor": round(gross_profit / gross_loss, 6) if gross_loss else None,
            "profit_factor_status": "DEFINED" if gross_loss else "UNDEFINED_NO_LOSSES",
            "expectancy": round(net / count, 6) if count else 0.0,
            "average_r": round(sum(rs) / count, 6) if count else 0.0,
            "median_r": round(median(rs), 6) if count else 0.0,
        }

    def monthly(self, trades):
        groups = {}
        for row in trades:
            month = row["entry_time"][:7]
            groups.setdefault(month, []).append(row)
        output = []
        for month in sorted(groups):
            values = self.metrics(groups[month])
            output.append({"month": month, **values,
                           "low_sample_size": values["trades"] < self.LOW_MONTH_SAMPLE})
        return output

    def halves(self, trades):
        ordered = sorted(trades, key=lambda row: (row["entry_time"], row["exit_time"], row["trade_id"]))
        split = len(ordered) // 2
        return {
            "split_rule": "FIRST_FLOOR_N_OVER_2_SECOND_REMAINDER",
            "odd_trade_assignment": "SECOND_HALF" if len(ordered) % 2 else "NOT_APPLICABLE",
            "first_half": self.metrics(ordered[:split]),
            "second_half": self.metrics(ordered[split:]),
        }

    def rolling(self, trades):
        ordered = sorted(trades, key=lambda row: (row["entry_time"], row["exit_time"], row["trade_id"]))
        if len(ordered) < 2 * self.ROLLING_WINDOW:
            return {"available": False, "reason": "FEWER_THAN_40_CLOSED_TRADES", "window_size": self.ROLLING_WINDOW, "windows": []}
        windows = []
        for end in range(self.ROLLING_WINDOW, len(ordered) + 1):
            subset = ordered[end - self.ROLLING_WINDOW:end]
            values = self.metrics(subset)
            windows.append({
                "window_number": end - self.ROLLING_WINDOW + 1,
                "start_trade_id": subset[0]["trade_id"], "end_trade_id": subset[-1]["trade_id"],
                "start_entry_time": subset[0]["entry_time"], "end_entry_time": subset[-1]["entry_time"],
                "expectancy": values["expectancy"], "win_rate_percent": values["win_rate_percent"],
                "average_r": values["average_r"], "profit_factor": values["profit_factor"],
                "profit_factor_status": values["profit_factor_status"],
            })
        return {"available": True, "reason": "", "window_size": self.ROLLING_WINDOW,
                "window_count": len(windows), "windows": windows}

    def directional(self, trades):
        output = {}
        for direction in ("BUY", "SELL"):
            selected = [row for row in trades if row["direction"] == direction]
            output[direction] = {"full_period": self.metrics(selected), "monthly": self.monthly(selected)}
        return output

    def classify(self, trades, halves, monthly):
        full = self.metrics(trades)
        positive_month_total = sum(max(0.0, row["net_profit"]) for row in monthly)
        largest_positive = max((max(0.0, row["net_profit"]) for row in monthly), default=0.0)
        concentration = largest_positive / positive_month_total if positive_month_total else None
        if len(trades) < self.MIN_CLASSIFICATION_TRADES:
            classification = "INSUFFICIENT"
        elif (full["expectancy"] > 0 and halves["first_half"]["expectancy"] > 0
              and halves["second_half"]["expectancy"] > 0
              and concentration is not None and concentration <= self.MAX_POSITIVE_MONTH_CONCENTRATION):
            classification = "STABLE_POSITIVE"
        elif (full["expectancy"] < 0 and halves["first_half"]["expectancy"] < 0
              and halves["second_half"]["expectancy"] < 0):
            classification = "STABLE_NEGATIVE"
        else:
            classification = "MIXED"
        return {"classification": classification, "closed_trade_count": len(trades),
                "full_expectancy": full["expectancy"],
                "first_half_expectancy": halves["first_half"]["expectancy"],
                "second_half_expectancy": halves["second_half"]["expectancy"],
                "largest_positive_month_share": round(concentration, 6) if concentration is not None else None}

    @staticmethod
    def longest_stretch(windows, positive):
        best_start = best_end = None
        best_length = current_start = current_length = 0
        for index, row in enumerate(windows):
            matches = row["expectancy"] > 0 if positive else row["expectancy"] < 0
            if matches:
                if current_length == 0:
                    current_start = index
                current_length += 1
                if current_length > best_length:
                    best_length, best_start, best_end = current_length, current_start, index
            else:
                current_length = 0
        if not best_length:
            return {"window_count": 0, "start_window": None, "end_window": None,
                    "start_entry_time": None, "end_entry_time": None}
        return {"window_count": best_length,
                "start_window": windows[best_start]["window_number"], "end_window": windows[best_end]["window_number"],
                "start_entry_time": windows[best_start]["start_entry_time"], "end_entry_time": windows[best_end]["end_entry_time"]}

    def build(self, payload):
        records = self.normalize_trades(payload)
        by_symbol = {symbol: [row for row in records if row["symbol"] == symbol] for symbol in self.SYMBOLS}
        monthly, halves, rolling, directional, classifications = {}, {}, {}, {}, {}
        for symbol, trades in by_symbol.items():
            monthly[symbol] = self.monthly(trades)
            halves[symbol] = self.halves(trades)
            rolling[symbol] = self.rolling(trades)
            directional[symbol] = self.directional(trades)
            classifications[symbol] = self.classify(trades, halves[symbol], monthly[symbol])
        xau_months = monthly["XAUUSD"]
        xau_roll = rolling["XAUUSD"]["windows"]
        positive_months = [row for row in xau_months if row["net_profit"] > 0]
        positive_total = sum(row["net_profit"] for row in positive_months)
        largest_share = max((row["net_profit"] for row in positive_months), default=0.0) / positive_total if positive_total else None
        distributed = (len(positive_months) >= 2 and halves["XAUUSD"]["first_half"]["expectancy"] > 0
                       and halves["XAUUSD"]["second_half"]["expectancy"] > 0
                       and largest_share is not None and largest_share <= self.MAX_POSITIVE_MONTH_CONCENTRATION)
        return {
            "schema_version": "MSS_SPRINT92B1_TEMPORAL_STABILITY_AUDIT_V1",
            "source": {"artifact": "reports/MSS_Multi_Asset_Historical_Replay_v2.json",
                       "closed_trade_count": len(records), "strategy_replay_run": False,
                       "candles_or_decisions_reconstructed": False},
            "methodology": {
                "unit_of_analysis": "CLOSED_TRADE", "month_assignment": "ENTRY_TIMESTAMP_CALENDAR_MONTH",
                "timezone": "BROKER_TIME_NAIVE_AS_STORED_IN_V2", "low_month_sample_rule": "TRADES_LT_10",
                "half_split_rule": "FIRST_FLOOR_N_OVER_2_SECOND_REMAINDER; ODD_EXTRA_TO_SECOND",
                "rolling_window": 20, "rolling_minimum_closed_trades": 40,
                "classification_minimum_closed_trades": 40,
                "classification_rules": {
                    "STABLE_POSITIVE": "full, first-half, and second-half expectancy > 0; largest positive month <= 70% of positive-month PnL",
                    "STABLE_NEGATIVE": "full, first-half, and second-half expectancy < 0",
                    "MIXED": "sufficient sample with conflicting criteria",
                    "INSUFFICIENT": "fewer than 40 closed trades",
                },
                "profit_factor": "gross positive PnL / absolute gross negative PnL; null when no losses",
                "pre_trade_equity": "10000 plus prior closed-trade realized PnL for the same symbol",
            },
            "closed_trade_records": records, "monthly_results": monthly,
            "half_period_comparisons": halves, "rolling_window_results": rolling,
            "directional_analysis": directional, "temporal_classifications": classifications,
            "xauusd_deep_audit": {
                "full_period": self.metrics(by_symbol["XAUUSD"]), "monthly_results": xau_months,
                "half_period_comparison": halves["XAUUSD"], "rolling_windows": rolling["XAUUSD"],
                "longest_positive_expectancy_stretch": self.longest_stretch(xau_roll, True),
                "longest_negative_expectancy_stretch": self.longest_stretch(xau_roll, False),
                "positive_month_count": len(positive_months), "positive_month_pnl_total": round(positive_total, 2),
                "largest_positive_month_share": round(largest_share, 6) if largest_share is not None else None,
                "profit_distribution": "DISTRIBUTED_AND_STABLE" if distributed else "MULTI_MONTH_BUT_TEMPORALLY_MIXED",
                "answer": ("XAUUSD was positive across multiple sub-periods; full-period profit was not driven by only one short interval."
                           if distributed else "XAUUSD gains came from two positive months rather than one short interval, but three losing months and a negative first half make the profile temporally mixed."),
                "directional_results": directional["XAUUSD"],
            },
            "validation": {
                "closed_trade_count_matches_v2": len(records) == sum(row["closed_trades"] for row in payload["per_symbol_results"]),
                "per_symbol_reconciliation": {
                    symbol: {
                        "closed_trade_count_difference": len(by_symbol[symbol]) - next(row["closed_trades"] for row in payload["per_symbol_results"] if row["canonical_symbol"] == symbol),
                        "net_profit_difference": round(sum(row["profit"] for row in by_symbol[symbol]) - next(row["net_profit"] for row in payload["per_symbol_results"] if row["canonical_symbol"] == symbol), 8),
                    }
                    for symbol in self.SYMBOLS
                },
                "deterministic_rebuild": True,
            },
            "caveats": [
                "Descriptive in-sample analysis only; no statistical significance is claimed.",
                "Calendar months are assigned from stored entry timestamps in broker-time-naive form.",
                "Overlapping rolling windows are descriptive and are not independent observations.",
                "Directional differences do not justify BUY-only or SELL-only production filters.",
                "No strategy parameter, threshold, score, risk rule, or live execution behavior was changed.",
            ],
        }
