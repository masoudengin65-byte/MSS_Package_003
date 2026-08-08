from copy import deepcopy
from datetime import datetime, timedelta

from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.analysis.score_engine import ScoreEngine
from mss.analysis.shadow_score_report_engine import ShadowScoreReportEngine
from mss.domain.candle import Candle
from mss.domain.historical_backtest import BacktestSymbolMetadata, HistoricalBacktestConfig
from mss.domain.pipeline_result import PipelineResult


def evidence(**overrides):
    values = {
        "structure": "UPTREND", "bos": True, "bos_direction": "BULLISH",
        "choch": False, "choch_direction": "NOT_AVAILABLE",
        "liquidity_detected": True, "liquidity_sweep": True, "liquidity_side": "SELL",
        "order_block_detected": True, "fvg_detected": False,
        "current_zone": "DISCOUNT", "session": "LONDON", "kill_zone": "LONDON_OPEN",
        "relative_volatility": 1.3, "h1_trend": "NOT_AVAILABLE", "h4_trend": "NOT_AVAILABLE",
        "daily_trend": "NOT_AVAILABLE", "risk_approved": True,
        "available_candle_count": 200, "portfolio_exposure": 0.0, "correlation_score": 0.0,
    }
    values.update(overrides)
    return values


def test_shadow_score_is_exact_component_sum_with_no_residual():
    result = ScoreEngine().calculate(evidence(), "BUY")
    numeric = [v for v in result.components.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert result.score == sum(numeric)
    assert set(result.components) == set(ScoreEngine.COMPONENTS)
    assert "unattributed" not in result.components


def test_shadow_confidence_is_reproducible_and_varies_with_agreement():
    engine = ScoreEngine(); source = evidence(); before = deepcopy(source)
    strong = engine.calculate(source, "BUY")
    assert strong == engine.calculate(source, "BUY")
    assert source == before
    conflicting = engine.calculate(evidence(structure="DOWNTREND", bos_direction="BEARISH", current_zone="PREMIUM"), "BUY")
    assert strong.confidence != conflicting.confidence


def test_unavailable_evidence_is_not_invented():
    result = ScoreEngine().calculate({key: "NOT_AVAILABLE" for key in evidence()}, "BUY")
    assert all(value == "NOT_AVAILABLE" for value in result.components.values())
    assert result.score == 0
    assert result.confidence == 0.0


class VariablePipeline:
    def __init__(self): self.calls = 0
    def run(self, symbol, timeframe, candles):
        self.calls += 1
        active = self.calls in {1, 4}
        return PipelineResult(symbol=symbol, timeframe=timeframe, valid=True,
            structure_state="UPTREND", swing_count=4, previous_high=103, last_high=104,
            previous_low=98, last_low=99, current_close=candles[-1].close,
            bos_detected=active, bos_direction="BULLISH" if active else "",
            liquidity_detected=self.calls == 4, liquidity_side="SELL" if self.calls == 4 else "",
            score=25 if active else 0, confidence=22.73 if active else 0,
            recommendation="TRADE" if active else "WAIT")


def _candles():
    start = datetime(2026, 1, 1)
    return [Candle(start+timedelta(minutes=15*i), 100, 103, 99.5, 101, 100+i, 0, 100) for i in range(8)]


def _run():
    return HistoricalBacktestEngine(VariablePipeline()).run("TEST", "M15", _candles(),
        HistoricalBacktestConfig(warmup_candles=2, analysis_lookback=10, spread_points=0, slippage_points=0),
        BacktestSymbolMetadata(point=.01, digits=2, tick_size=.01, tick_value=1,
            contract_size=100, volume_min=.01, volume_max=100, volume_step=.01))


def test_shadow_replay_is_deterministic_and_does_not_change_legacy_behavior():
    first, second = _run(), _run()
    assert first.trades == second.trades
    assert first.metrics == second.metrics
    for trade in first.trades:
        assert trade.score == trade.legacy_score
        assert trade.confidence == trade.legacy_confidence
        assert ShadowScoreReportEngine.reconciles(trade)
        assert trade.direction == "BUY"


def test_shadow_scores_and_confidence_have_variation():
    rows = [
        ScoreEngine().calculate(evidence(relative_volatility=.4, session="ASIA", kill_zone="NONE"), "BUY"),
        ScoreEngine().calculate(evidence(relative_volatility=1.4), "BUY"),
        ScoreEngine().calculate(evidence(structure="DOWNTREND", current_zone="PREMIUM"), "BUY"),
    ]
    assert len({row.score for row in rows}) > 1
    assert len({row.confidence for row in rows}) > 1


def test_detector_and_strategy_inputs_are_not_mutated():
    source = evidence(); before = deepcopy(source)
    ScoreEngine().calculate(source, "BUY")
    assert source == before
    pipeline = PipelineResult(bos_detected=True, bos_direction="BULLISH", recommendation="TRADE", score=25, confidence=22.73)
    snapshot = deepcopy(pipeline)
    ScoreEngine().calculate(evidence(), "BUY")
    assert pipeline == snapshot
