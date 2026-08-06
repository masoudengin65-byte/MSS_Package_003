"""Data-quality audit for Sprint 79 frozen historical context snapshots."""

from collections import Counter

from mss.analysis.context_capture_engine import ContextCaptureEngine
from mss.domain.context_snapshot import ContextSnapshot


class HistoricalContextAudit:
    SCORE_FIELDS = (
        "structure_score", "bos_score", "choch_score", "liquidity_score",
        "ob_score", "fvg_score", "session_score", "htf_score", "risk_score",
        "unattributed_score",
    )

    def calculate(self, results):
        trades = [trade for result in results for trade in result.trades]
        snapshots = [trade.context_snapshot for trade in trades if trade.context_snapshot]
        required = set(ContextCaptureEngine.FIELDS)
        unavailable = Counter()
        missing = Counter()
        score_errors = mutation_errors = order_errors = future_errors = 0

        for trade in trades:
            snapshot = trade.context_snapshot
            if snapshot is None:
                continue
            if not isinstance(snapshot, ContextSnapshot):
                mutation_errors += 1
                continue
            values = snapshot.to_dict()
            for field in required:
                if field not in values or values[field] is None:
                    missing[field] += 1
                if values.get(field) == ContextCaptureEngine.NOT_AVAILABLE:
                    unavailable[field] += 1
            if sum(float(values.get(field, 0) or 0) for field in self.SCORE_FIELDS) != float(values.get("final_score", 0) or 0):
                score_errors += 1
            decision = values.get("decision_time")
            entry = values.get("entry_time")
            visible = values.get("latest_visible_candle_time")
            if decision and entry and decision >= entry:
                order_errors += 1
            if visible and decision and visible > decision:
                future_errors += 1

        ids = [(trade.symbol, trade.trade_id) for trade in trades]
        payloads = [snapshot.payload_json for snapshot in snapshots]
        return {
            "source_candle_count": {result.symbol: result.diagnostics.candles_loaded for result in results},
            "processed_candle_count": {result.symbol: result.diagnostics.candles_processed for result in results},
            "closed_trades": sum(trade.status == "CLOSED" for trade in trades),
            "unresolved_trades": sum(trade.status != "CLOSED" for trade in trades),
            "opened_trades": len(trades),
            "trades_with_context": len(snapshots),
            "trades_without_context": len(trades) - len(snapshots),
            "context_field_count": len(ContextCaptureEngine.FIELDS),
            "duplicate_trade_ids": len(ids) - len(set(ids)),
            "duplicate_snapshots": len(payloads) - len(set(payloads)),
            "missing_required_values": dict(sorted(missing.items())),
            "not_available_by_field": dict(sorted(unavailable.items())),
            "inconsistent_score_component_totals": score_errors,
            "context_mutation_violations": mutation_errors,
            "timestamp_order_violations": order_errors,
            "future_data_violations": future_errors,
        }

