from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from mss.analysis.context_capture_engine import ContextCaptureEngine
from mss.domain.candle import Candle
from mss.domain.pipeline_result import PipelineResult


START = datetime(2026, 1, 1, 12, 0)


def candles(count=20):
    return [Candle(START + timedelta(minutes=15*i), 100+i, 102+i, 99+i, 101+i, 100+i, 2, 100+i) for i in range(count)]


def result():
    return PipelineResult(valid=True, structure_state="UPTREND", swing_count=8,
        previous_high=115, last_high=120, previous_low=108, last_low=110,
        current_close=121, bos_detected=True, bos_direction="BULLISH",
        bos_progress=100, score=25, confidence=22.73)


def test_every_context_field_is_present():
    engine = ContextCaptureEngine()
    snap = engine.capture_decision(pipeline_result=result(), visible_candles=candles(), decision_time=candles()[-1].time)
    entered = engine.capture_entry(snap, entry_candle=candles()[-1], entry_time=candles()[-1].time + timedelta(minutes=15), risk_approved=True, position_size=.5, sl_distance=2, tp_distance=4, rr=2)
    assert set(entered.to_dict()) == set(engine.FIELDS)
    assert len(engine.FIELDS) == len(set(engine.FIELDS))


def test_no_future_candle_is_read():
    engine = ContextCaptureEngine()
    visible = candles(10)
    future = candles(11)[-1]
    first = engine.capture_decision(pipeline_result=result(), visible_candles=visible, decision_time=visible[-1].time)
    future.close = 999999
    second = engine.capture_decision(pipeline_result=result(), visible_candles=visible, decision_time=visible[-1].time)
    assert first == second
    assert first["latest_visible_candle_time"] == visible[-1].time.isoformat()


def test_context_is_immutable_after_entry():
    engine = ContextCaptureEngine()
    decision = engine.capture_decision(pipeline_result=result(), visible_candles=candles(), decision_time=candles()[-1].time)
    entered = engine.capture_entry(decision, entry_candle=candles()[-1], entry_time=candles()[-1].time, risk_approved=True, position_size=.5, sl_distance=2, tp_distance=4, rr=2)
    with pytest.raises(TypeError): entered["atr"] = 999
    with pytest.raises(FrozenInstanceError): entered.payload_json = "{}"


def test_capture_is_deterministic():
    engine = ContextCaptureEngine()
    args = dict(pipeline_result=result(), visible_candles=candles(), decision_time=candles()[-1].time)
    assert engine.capture_decision(**args) == engine.capture_decision(**args)
