"""Calculate premium and discount zones from existing swing points."""

from mss.domain.premium_discount import PremiumDiscount


class PremiumDiscountEngine:

    def calculate(self, swings, current_price) -> PremiumDiscount:
        result = PremiumDiscount()

        if not swings or current_price is None:
            return result

        swing_highs = [
            swing.price
            for swing in swings
            if self._is_high(swing) and getattr(swing, "price", None) is not None
        ]
        swing_lows = [
            swing.price
            for swing in swings
            if self._is_low(swing) and getattr(swing, "price", None) is not None
        ]

        if not swing_highs or not swing_lows:
            return result

        swing_high = max(swing_highs)
        swing_low = min(swing_lows)

        if swing_high <= swing_low:
            return result

        equilibrium = (swing_high + swing_low) / 2.0

        result.swing_high = swing_high
        result.swing_low = swing_low
        result.premium_zone = (equilibrium, swing_high)
        result.discount_zone = (swing_low, equilibrium)
        result.equilibrium = equilibrium
        result.distance_to_equilibrium = abs(current_price - equilibrium)

        if current_price > equilibrium:
            result.current_zone = "PREMIUM"
        elif current_price < equilibrium:
            result.current_zone = "DISCOUNT"
        else:
            result.current_zone = "EQUILIBRIUM"

        result.valid = True
        return result

    @staticmethod
    def _is_high(swing) -> bool:
        return bool(
            getattr(swing, "is_high", False)
            or getattr(swing, "kind", "") == "HIGH"
        )

    @staticmethod
    def _is_low(swing) -> bool:
        return bool(
            getattr(swing, "is_low", False)
            or getattr(swing, "kind", "") == "LOW"
        )
