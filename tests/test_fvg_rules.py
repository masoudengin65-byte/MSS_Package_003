from mss.domain.fair_value_gap import FairValueGap


def test_new_fvg_is_invalid_by_default():

    fvg = FairValueGap()

    assert not fvg.valid

    assert not fvg.filled