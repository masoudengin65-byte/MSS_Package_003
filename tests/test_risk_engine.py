from mss.analysis.risk_engine import RiskEngine


def test_calculate_risk_profile():

    profile = RiskEngine().calculate(

        balance=10000,

        risk_percent=1,

        stop_distance=0.002,

    )

    assert profile.valid

    assert profile.account_balance == 10000

    assert profile.risk_percent == 1

    assert profile.risk_amount == 100

    assert profile.stop_distance == 0.002

    assert profile.lot_size == 0.5


def test_invalid_balance():

    profile = RiskEngine().calculate(

        balance=0,

        risk_percent=1,

        stop_distance=0.002,

    )

    assert not profile.valid


def test_invalid_stop_distance():

    profile = RiskEngine().calculate(

        balance=10000,

        risk_percent=1,

        stop_distance=0,

    )

    assert not profile.valid