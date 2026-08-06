from mss.analysis.session_bias_engine import SessionBiasEngine
from mss.domain.kill_zone_status import KillZoneStatus
from mss.domain.pipeline_result import PipelineResult
from mss.domain.premium_discount import PremiumDiscount


def pipeline(structure, bos_direction=""):
    return PipelineResult(
        valid=True,
        structure_state=structure,
        bos_detected=bool(bos_direction),
        bos_direction=bos_direction,
    )


def test_bullish_session_bias():
    pipelines = [
        pipeline("UPTREND"),
        pipeline("UPTREND", "BULLISH"),
        pipeline("RANGE", "BULLISH"),
    ]
    premium_discount = PremiumDiscount(
        current_zone="DISCOUNT",
        valid=True,
    )
    kill_zone = KillZoneStatus(
        current_session="LONDON",
        active_kill_zone="LONDON_OPEN",
        active=True,
        valid=True,
    )

    result = SessionBiasEngine().calculate(
        pipelines,
        premium_discount,
        kill_zone,
    )

    assert result.valid
    assert result.current_session == "LONDON"
    assert result.bias == "Bullish"
    assert result.strength == 100.0
    assert result.confidence == 100.0
    assert result.bullish_timeframes == 3


def test_bearish_session_bias():
    result = SessionBiasEngine().calculate(
        [pipeline("DOWNTREND"), pipeline("DOWNTREND", "BEARISH")],
        PremiumDiscount(current_zone="PREMIUM", valid=True),
        KillZoneStatus(current_session="NEWYORK", valid=True),
    )

    assert result.bias == "Bearish"
    assert result.strength == 100.0
    assert result.bearish_timeframes == 2


def test_conflicting_timeframes_are_neutral():
    result = SessionBiasEngine().calculate(
        [pipeline("UPTREND"), pipeline("DOWNTREND")],
        PremiumDiscount(current_zone="EQUILIBRIUM", valid=True),
        KillZoneStatus(current_session="LONDON", valid=True),
    )

    assert result.bias == "Neutral"
    assert result.strength == 0.0
    assert result.bullish_timeframes == 1
    assert result.bearish_timeframes == 1


def test_premium_discount_can_supply_bias_without_timeframe_direction():
    result = SessionBiasEngine().calculate(
        [],
        PremiumDiscount(current_zone="DISCOUNT", valid=True),
        KillZoneStatus(current_session="ASIA", valid=True),
    )

    assert result.bias == "Bullish"
    assert result.strength == 25.0


def test_missing_inputs_return_invalid_neutral():
    result = SessionBiasEngine().calculate(None, None, None)

    assert not result.valid
    assert result.bias == "Neutral"
    assert result.strength == 0.0
    assert result.confidence == 0.0


def test_session_context_alone_has_zero_bias_confidence():
    result = SessionBiasEngine().calculate(
        [],
        None,
        KillZoneStatus(current_session="ASIA", valid=True),
    )

    assert not result.valid
    assert result.bias == "Neutral"
    assert result.confidence == 0.0
