"""
Signal Engine

Transforms market analysis into a trading decision.
"""

from dataclasses import dataclass


@dataclass
class TradeSignal:

    signal: str

    reason: str

    current_zone: str = "UNKNOWN"

    distance_to_equilibrium: float | None = None

    current_session: str = "NONE"

    active_kill_zone: str = "NONE"

    kill_zone_remaining_time: object = None

    kill_zone_active: bool = False

    session_bias: str = "Neutral"

    bias_strength: float = 0.0

    bias_confidence: float = 0.0


class SignalEngine:

    def generate(self, context):

        analysis = context.analysis

        premium_discount = getattr(analysis, "premium_discount", None)

        current_zone = (
            premium_discount.current_zone
            if premium_discount is not None
            else "UNKNOWN"
        )

        distance_to_equilibrium = (
            premium_discount.distance_to_equilibrium
            if premium_discount is not None
            else None
        )

        kill_zone_status = getattr(context, "kill_zone_status", None)

        kill_zone_fields = {
            "current_session": getattr(
                kill_zone_status, "current_session", "NONE"
            ),
            "active_kill_zone": getattr(
                kill_zone_status, "active_kill_zone", "NONE"
            ),
            "kill_zone_remaining_time": getattr(
                kill_zone_status, "remaining_time", None
            ),
            "kill_zone_active": getattr(kill_zone_status, "active", False),
        }

        session_bias = getattr(context, "session_bias", None)

        session_bias_fields = {
            "session_bias": getattr(session_bias, "bias", "Neutral"),
            "bias_strength": getattr(session_bias, "strength", 0.0),
            "bias_confidence": getattr(session_bias, "confidence", 0.0),
        }

        if analysis.choch:

            return TradeSignal(

                signal=analysis.choch.direction,

                reason="CHoCH",

                current_zone=current_zone,

                distance_to_equilibrium=distance_to_equilibrium,

                **kill_zone_fields,

                **session_bias_fields,

            )

        if analysis.bos:

            return TradeSignal(

                signal=analysis.bos.direction,

                reason="BOS",

                current_zone=current_zone,

                distance_to_equilibrium=distance_to_equilibrium,

                **kill_zone_fields,

                **session_bias_fields,

            )

        return TradeSignal(

            signal="WAIT",

            reason="NO_SETUP",

            current_zone=current_zone,

            distance_to_equilibrium=distance_to_equilibrium,

            **kill_zone_fields,

            **session_bias_fields,

        )
