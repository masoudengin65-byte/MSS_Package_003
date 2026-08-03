"""
MSS Setup Scoring Engine
Version : 1.0
Sprint : 45.0
Compatible : v0.45
"""

from mss.domain.setup_score import SetupScore


class SetupScoringEngine:

    def calculate(
        self,
        *,
        bos=False,
        choch=False,
        order_block=False,
        fair_value_gap=False,
        liquidity=False,
        kill_zone=False,
        higher_timeframe=False,
    ) -> SetupScore:

        score = SetupScore()

        #
        # Smart Money Score
        #

        if bos:

            score.bos = 25

        if choch:

            score.choch = 20

        if order_block:

            score.order_block = 20

        if fair_value_gap:

            score.fair_value_gap = 15

        if liquidity:

            score.liquidity = 10

        if kill_zone:

            score.kill_zone = 5

        if higher_timeframe:

            score.higher_timeframe = 15

        score.score = (

            score.bos
            + score.choch
            + score.order_block
            + score.fair_value_gap
            + score.liquidity
            + score.kill_zone
            + score.higher_timeframe

        )

        #
        # Confidence
        #

        score.confidence = round(

            (score.score / 110.0) * 100.0,

            2,

        )

        #
        # Star Rating
        #

        if score.score >= 95:

            score.stars = 5

        elif score.score >= 80:

            score.stars = 4

        elif score.score >= 65:

            score.stars = 3

        elif score.score >= 45:

            score.stars = 2

        elif score.score > 0:

            score.stars = 1

        else:

            score.stars = 0

        score.valid = True

        return score