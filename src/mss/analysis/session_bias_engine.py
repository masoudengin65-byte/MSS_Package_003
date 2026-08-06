"""Calculate session bias from multi-timeframe pipeline confluence."""

from mss.domain.kill_zone_status import KillZoneStatus
from mss.domain.pipeline_result import PipelineResult
from mss.domain.premium_discount import PremiumDiscount
from mss.domain.session_bias import SessionBias


class SessionBiasEngine:

    MTF_WEIGHT = 0.75
    PREMIUM_DISCOUNT_WEIGHT = 0.25
    BIAS_THRESHOLD = 0.15

    def calculate(
        self,
        pipeline_results: list[PipelineResult] | None,
        premium_discount: PremiumDiscount | None,
        kill_zone_status: KillZoneStatus | None,
    ) -> SessionBias:
        result = SessionBias(
            current_session=getattr(
                kill_zone_status,
                "current_session",
                "NONE",
            )
        )

        directions = [
            self._direction(item)
            for item in (pipeline_results or [])
            if isinstance(item, PipelineResult) and item.valid
        ]

        result.bullish_timeframes = directions.count(1)
        result.bearish_timeframes = directions.count(-1)
        result.neutral_timeframes = directions.count(0)

        mtf_score = (
            sum(directions) / len(directions)
            if directions
            else 0.0
        )
        location_score = self._location_score(premium_discount)
        combined_score = (
            mtf_score * self.MTF_WEIGHT
            + location_score * self.PREMIUM_DISCOUNT_WEIGHT
        )

        if combined_score > self.BIAS_THRESHOLD:
            result.bias = "Bullish"
        elif combined_score < -self.BIAS_THRESHOLD:
            result.bias = "Bearish"

        result.strength = round(min(100.0, abs(combined_score) * 100.0), 2)

        evidence = 0.0
        if directions:
            evidence += 60.0
        if premium_discount is not None and premium_discount.valid:
            evidence += 25.0
        if kill_zone_status is not None and kill_zone_status.valid:
            evidence += 5.0
            if kill_zone_status.active:
                evidence += 10.0

        result.valid = bool(directions) or bool(
            premium_discount is not None and premium_discount.valid
        )
        if result.valid:
            result.confidence = round(
                min(100.0, result.strength * 0.7 + evidence * 0.3),
                2,
            )
        return result

    @staticmethod
    def _direction(result: PipelineResult) -> int:
        if result.bos_detected:
            if result.bos_direction == "BULLISH":
                return 1
            if result.bos_direction == "BEARISH":
                return -1

        if result.structure_state == "UPTREND":
            return 1
        if result.structure_state == "DOWNTREND":
            return -1
        return 0

    @staticmethod
    def _location_score(premium_discount: PremiumDiscount | None) -> int:
        if premium_discount is None or not premium_discount.valid:
            return 0
        if premium_discount.current_zone == "DISCOUNT":
            return 1
        if premium_discount.current_zone == "PREMIUM":
            return -1
        return 0
