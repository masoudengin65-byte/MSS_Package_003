"""
Signal Engine

Transforms market analysis into a trading decision.
"""

from dataclasses import dataclass


@dataclass
class TradeSignal:

    signal: str

    reason: str


class SignalEngine:

    def generate(self, context):

        analysis = context.analysis

        if analysis.choch:

            return TradeSignal(

                signal=analysis.choch.direction,

                reason="CHoCH",

            )

        if analysis.bos:

            return TradeSignal(

                signal=analysis.bos.direction,

                reason="BOS",

            )

        return TradeSignal(

            signal="WAIT",

            reason="NO_SETUP",

        )