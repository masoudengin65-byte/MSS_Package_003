from datetime import datetime, timedelta

from mss.analysis.context_capture_engine import ContextCaptureEngine
from mss.analysis.historical_context_audit import HistoricalContextAudit
from mss.domain.candle import Candle
from mss.domain.historical_backtest import HistoricalBacktestResult, HistoricalTrade
from mss.domain.pipeline_result import PipelineResult


def test_context_audit_reports_complete_clean_snapshot():
    now = datetime(2026, 1, 1)
    candle = Candle(now, 100, 101, 99, 100.5, 10, 2, 10)
    pipeline = PipelineResult(valid=True, bos_detected=True, bos_direction="BULLISH", score=25, confidence=22.73)
    engine = ContextCaptureEngine()
    decision = engine.capture_decision(pipeline_result=pipeline, visible_candles=[candle], decision_time=now)
    snapshot = engine.capture_entry(decision, entry_candle=candle, entry_time=now + timedelta(minutes=15), risk_approved=True, position_size=1, sl_distance=1, tp_distance=2, rr=2)
    trade = HistoricalTrade(trade_id=1, symbol="TEST", status="CLOSED", context_snapshot=snapshot)
    result = HistoricalBacktestResult(symbol="TEST", trades=[trade])
    result.diagnostics.candles_loaded = result.diagnostics.candles_processed = 1
    audit = HistoricalContextAudit().calculate([result])
    assert audit["trades_with_context"] == 1
    assert audit["trades_without_context"] == 0
    assert audit["context_field_count"] == 87
    assert audit["duplicate_trade_ids"] == 0
    assert audit["inconsistent_score_component_totals"] == 0
    assert audit["context_mutation_violations"] == 0
    assert audit["timestamp_order_violations"] == 0
    assert audit["future_data_violations"] == 0
