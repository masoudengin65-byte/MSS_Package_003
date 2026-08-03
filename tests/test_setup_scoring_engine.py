from mss.analysis.setup_scoring_engine import SetupScoringEngine


def test_full_setup_score():

    score = SetupScoringEngine().calculate(

        bos=True,

        choch=True,

        order_block=True,

        fair_value_gap=True,

        liquidity=True,

        kill_zone=True,

        higher_timeframe=True,

    )

    assert score.valid

    assert score.score == 110

    assert score.confidence == 100.0

    assert score.stars == 5


def test_partial_setup_score():

    score = SetupScoringEngine().calculate(

        bos=True,

        order_block=True,

        fair_value_gap=True,

    )

    assert score.valid

    assert score.score == 60

    assert score.stars == 2

    assert score.confidence > 50.0


def test_empty_setup_score():

    score = SetupScoringEngine().calculate()

    assert score.valid

    assert score.score == 0

    assert score.confidence == 0.0

    assert score.stars == 0