from mss.analysis.confluence_gated_smart_money_pipeline import ConfluenceGatedSmartMoneyPipeline
from mss.domain.pipeline_result import PipelineResult


def result(direction="BULLISH", signal="BUY", valid=True):
    return PipelineResult(valid=True, bos_detected=True, bos_direction=direction,
        recommendation="TRADE", confluence_valid=valid, confluence_signal=signal)


def test_matching_existing_confluence_preserves_bos():
    gated=ConfluenceGatedSmartMoneyPipeline.apply_gate(result())
    assert gated.bos_detected is True
    assert gated.confluence_gate_rejected is False


def test_missing_or_mismatched_confluence_rejects_bos():
    missing=ConfluenceGatedSmartMoneyPipeline.apply_gate(result(valid=False))
    mismatched=ConfluenceGatedSmartMoneyPipeline.apply_gate(result(signal="SELL"))
    assert missing.bos_detected is False and missing.recommendation=="WATCH"
    assert mismatched.bos_detected is False and mismatched.confluence_gate_rejected is True


def test_non_bos_decision_is_unchanged():
    original=PipelineResult(valid=True,bos_detected=False,recommendation="WAIT")
    assert ConfluenceGatedSmartMoneyPipeline.apply_gate(original) is original
    assert original.recommendation=="WAIT"
