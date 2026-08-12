"""Research-only candidate that gates BOS entries with existing confluence."""

from mss.analysis.smart_money_pipeline import SmartMoneyPipeline


class ConfluenceGatedSmartMoneyPipeline(SmartMoneyPipeline):
    """Single-change G.1 candidate; baseline SmartMoneyPipeline stays unchanged."""

    @staticmethod
    def apply_gate(result):
        if not result.bos_detected:
            return result
        expected = "BUY" if result.bos_direction in ("BULLISH", "BUY") else "SELL" if result.bos_direction in ("BEARISH", "SELL") else ""
        accepted = bool(result.confluence_valid and expected and result.confluence_signal == expected)
        if not accepted:
            result.bos_detected = False
            result.recommendation = "WATCH"
            result.confluence_gate_rejected = True
            result.logs.append("Confluence Gate : REJECTED")
        else:
            result.logs.append("Confluence Gate : ACCEPTED")
        return result

    def run(self, symbol, timeframe, candles):
        return self.apply_gate(super().run(symbol, timeframe, candles))
