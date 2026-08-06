from dataclasses import dataclass

from mss.analysis.premium_discount_engine import PremiumDiscountEngine


@dataclass
class Swing:
    price: float
    is_high: bool = False
    is_low: bool = False


def test_premium_zone():
    swings = [
        Swing(price=110.0, is_high=True),
        Swing(price=90.0, is_low=True),
    ]

    result = PremiumDiscountEngine().calculate(swings, current_price=105.0)

    assert result.valid
    assert result.premium_zone == (100.0, 110.0)
    assert result.discount_zone == (90.0, 100.0)
    assert result.equilibrium == 100.0
    assert result.current_zone == "PREMIUM"
    assert result.distance_to_equilibrium == 5.0


def test_discount_zone_uses_full_swing_range():
    swings = [
        Swing(price=108.0, is_high=True),
        Swing(price=110.0, is_high=True),
        Swing(price=92.0, is_low=True),
        Swing(price=90.0, is_low=True),
    ]

    result = PremiumDiscountEngine().calculate(swings, current_price=95.0)

    assert result.swing_high == 110.0
    assert result.swing_low == 90.0
    assert result.current_zone == "DISCOUNT"
    assert result.distance_to_equilibrium == 5.0


def test_equilibrium_zone():
    swings = [
        Swing(price=110.0, is_high=True),
        Swing(price=90.0, is_low=True),
    ]

    result = PremiumDiscountEngine().calculate(swings, current_price=100.0)

    assert result.current_zone == "EQUILIBRIUM"
    assert result.distance_to_equilibrium == 0.0


def test_incomplete_swing_range_is_invalid():
    result = PremiumDiscountEngine().calculate(
        [Swing(price=110.0, is_high=True)],
        current_price=100.0,
    )

    assert not result.valid
    assert result.current_zone == "UNKNOWN"
