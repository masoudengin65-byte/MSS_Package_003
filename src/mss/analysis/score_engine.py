"""Modular, deterministic decision scoring operated only in shadow mode."""

from __future__ import annotations

from mss.domain.shadow_score import ShadowScore


class ScoreEngine:
    """Score captured evidence without changing a production decision.

    Each component is independently visible. Missing evidence is preserved as
    NOT_AVAILABLE and contributes nothing to the arithmetic sum.
    """

    NOT_AVAILABLE = "NOT_AVAILABLE"
    COMPONENTS = (
        "structure", "bos", "choch", "liquidity", "order_block",
        "fair_value_gap", "premium_discount", "session", "kill_zone",
        "volatility", "htf", "risk", "context", "portfolio", "correlation",
    )
    MAX_ABSOLUTE = {
        "structure": 15, "bos": 20, "choch": 10, "liquidity": 8,
        "order_block": 10, "fair_value_gap": 8, "premium_discount": 8,
        "session": 5, "kill_zone": 5, "volatility": 5, "htf": 10,
        "risk": 5, "context": 4, "portfolio": 5, "correlation": 5,
    }

    def calculate(self, evidence: dict, direction: str) -> ShadowScore:
        direction = str(direction or "").upper()
        components = {
            "structure": self._directional_structure(evidence.get("structure"), direction),
            "bos": self._directional_detector(evidence.get("bos"), evidence.get("bos_direction"), direction, 20),
            "choch": self._directional_detector(evidence.get("choch"), evidence.get("choch_direction"), direction, 10),
            "liquidity": self._liquidity(evidence, direction),
            "order_block": self._boolean(evidence.get("order_block_detected"), 10),
            "fair_value_gap": self._boolean(evidence.get("fvg_detected"), 8),
            "premium_discount": self._zone(evidence.get("current_zone"), direction),
            "session": self._session(evidence.get("session")),
            "kill_zone": self._kill_zone(evidence.get("kill_zone")),
            "volatility": self._volatility(evidence.get("relative_volatility")),
            "htf": self._htf(evidence, direction),
            "risk": self._risk(evidence.get("risk_approved")),
            "context": self._context(evidence),
            "portfolio": self._bounded_inverse(evidence.get("portfolio_exposure")),
            "correlation": self._bounded_inverse(evidence.get("correlation_score")),
        }
        numeric = [value for value in components.values() if isinstance(value, (int, float)) and not isinstance(value, bool)]
        score = int(sum(numeric))
        confidence = self._confidence(components)
        return ShadowScore(
            score=score,
            confidence=confidence,
            components=components,
            available_components=len(numeric),
            positive_components=sum(value > 0 for value in numeric),
            negative_components=sum(value < 0 for value in numeric),
        )

    def _confidence(self, components):
        numeric = {k: v for k, v in components.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        if not numeric:
            return 0.0
        positive = sum(v for v in numeric.values() if v > 0)
        negative = abs(sum(v for v in numeric.values() if v < 0))
        magnitude = positive + negative
        if not magnitude:
            return 0.0
        agreement = abs(positive - negative) / magnitude
        coverage = len(numeric) / len(self.COMPONENTS)
        observed_capacity = sum(self.MAX_ABSOLUTE[k] for k in numeric)
        strength = min(1.0, magnitude / observed_capacity) if observed_capacity else 0.0
        # Agreement is primary; evidence strength and availability prevent weak
        # or sparse agreement from producing unjustified high confidence.
        return round(100.0 * (0.60 * agreement + 0.25 * strength + 0.15 * coverage), 2)

    def _directional_structure(self, value, direction):
        if self._missing(value) or value == "UNKNOWN": return self.NOT_AVAILABLE
        aligned = (direction == "BUY" and value == "UPTREND") or (direction == "SELL" and value == "DOWNTREND")
        conflicting = (direction == "BUY" and value == "DOWNTREND") or (direction == "SELL" and value == "UPTREND")
        return 15 if aligned else -15 if conflicting else 0

    def _directional_detector(self, detected, detector_direction, direction, weight):
        if self._missing(detected): return self.NOT_AVAILABLE
        if not detected: return 0
        if self._missing(detector_direction): return self.NOT_AVAILABLE
        aligned = (direction == "BUY" and detector_direction == "BULLISH") or (direction == "SELL" and detector_direction == "BEARISH")
        return weight if aligned else -weight

    def _liquidity(self, evidence, direction):
        detected = evidence.get("liquidity_detected")
        swept = evidence.get("liquidity_sweep")
        if self._missing(detected) and self._missing(swept): return self.NOT_AVAILABLE
        if not detected and not swept: return 0
        side = evidence.get("liquidity_side")
        if self._missing(side): return 4
        aligned = (direction == "BUY" and side == "SELL") or (direction == "SELL" and side == "BUY")
        return 8 if aligned else -8

    def _zone(self, zone, direction):
        if self._missing(zone): return self.NOT_AVAILABLE
        if zone == "EQUILIBRIUM": return 0
        aligned = (direction == "BUY" and zone == "DISCOUNT") or (direction == "SELL" and zone == "PREMIUM")
        return 8 if aligned else -8

    def _htf(self, evidence, direction):
        values = [evidence.get(name) for name in ("h1_trend", "h4_trend", "daily_trend")]
        usable = [v for v in values if not self._missing(v) and v != "UNKNOWN"]
        if not usable: return self.NOT_AVAILABLE
        target = "UPTREND" if direction == "BUY" else "DOWNTREND"
        aligned = sum(v == target for v in usable)
        conflicting = sum(v in {"UPTREND", "DOWNTREND"} and v != target for v in usable)
        return round(10 * (aligned - conflicting) / len(usable))

    def _volatility(self, value):
        number = self._number(value)
        if number is None: return self.NOT_AVAILABLE
        return 5 if number >= 1.2 else 3 if number >= 0.8 else 1

    def _bounded_inverse(self, value):
        number = self._number(value)
        if number is None: return self.NOT_AVAILABLE
        magnitude = abs(number)
        return 0 if magnitude == 0 else -min(5, max(1, round(magnitude)))

    def _context(self, evidence):
        count = self._number(evidence.get("available_candle_count"))
        if count is None: return self.NOT_AVAILABLE
        return 4 if count >= 200 else 2 if count >= 50 else 1

    def _session(self, value):
        if self._missing(value): return self.NOT_AVAILABLE
        return 5 if value in {"LONDON", "NEWYORK"} else 2 if value == "ASIA" else 0

    def _kill_zone(self, value):
        if self._missing(value): return self.NOT_AVAILABLE
        return 0 if value == "NONE" else 5

    def _risk(self, value):
        if self._missing(value): return self.NOT_AVAILABLE
        return 5 if value is True else -5

    def _boolean(self, value, weight):
        if self._missing(value): return self.NOT_AVAILABLE
        return weight if value is True else 0

    @classmethod
    def _missing(cls, value):
        return value in (None, "", cls.NOT_AVAILABLE)

    @classmethod
    def _number(cls, value):
        if cls._missing(value) or isinstance(value, bool): return None
        try: return float(value)
        except (TypeError, ValueError): return None
