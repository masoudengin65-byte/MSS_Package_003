from types import SimpleNamespace

from mss.domain.premium_discount import PremiumDiscount
from mss.engine.signal_engine import SignalEngine
from mss.domain.kill_zone_status import KillZoneStatus
from datetime import timedelta
from mss.domain.session_bias import SessionBias


def test_decision_exposes_premium_discount_result():
    analysis = SimpleNamespace(
        choch=None,
        bos=None,
        premium_discount=PremiumDiscount(
            current_zone="DISCOUNT",
            distance_to_equilibrium=0.0015,
            valid=True,
        ),
    )
    context = SimpleNamespace(analysis=analysis)

    decision = SignalEngine().generate(context)

    assert decision.signal == "WAIT"
    assert decision.current_zone == "DISCOUNT"
    assert decision.distance_to_equilibrium == 0.0015


def test_kill_zone_context_does_not_generate_signal():
    analysis = SimpleNamespace(
        choch=None,
        bos=None,
        premium_discount=None,
    )
    context = SimpleNamespace(
        analysis=analysis,
        kill_zone_status=KillZoneStatus(
            current_session="LONDON",
            active_kill_zone="LONDON_OPEN",
            remaining_time=timedelta(minutes=45),
            active=True,
            valid=True,
        ),
    )

    decision = SignalEngine().generate(context)

    assert decision.signal == "WAIT"
    assert decision.reason == "NO_SETUP"
    assert decision.current_session == "LONDON"
    assert decision.active_kill_zone == "LONDON_OPEN"
    assert decision.kill_zone_remaining_time == timedelta(minutes=45)
    assert decision.kill_zone_active


def test_decision_exposes_session_bias_without_changing_signal():
    context = SimpleNamespace(
        analysis=SimpleNamespace(
            choch=None,
            bos=None,
            premium_discount=None,
        ),
        session_bias=SessionBias(
            current_session="NEWYORK",
            bias="Bearish",
            strength=75.0,
            confidence=68.5,
            valid=True,
        ),
    )

    decision = SignalEngine().generate(context)

    assert decision.signal == "WAIT"
    assert decision.session_bias == "Bearish"
    assert decision.bias_strength == 75.0
    assert decision.bias_confidence == 68.5
