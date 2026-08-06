"""Capture entry-available context without influencing trade decisions."""

from datetime import datetime

from mss.analysis.kill_zone_engine import KillZoneEngine
from mss.analysis.session_engine import SessionEngine
from mss.domain.context_snapshot import ContextSnapshot


class ContextCaptureEngine:
    NOT_AVAILABLE = "NOT_AVAILABLE"
    ATR_PERIOD = 14

    # Stable schema: every snapshot contains every field, even when its source
    # was not part of the historical replay input.
    FIELDS = (
        "snapshot_version", "captured_at", "available_candle_count", "latest_visible_candle_time",
        "structure", "trend_strength", "swing_count", "bos", "bos_direction", "bos_strength",
        "choch", "choch_direction", "choch_strength",
        "liquidity_detected", "liquidity_side", "liquidity_sweep", "liquidity_distance",
        "equal_high", "equal_low",
        "order_block_detected", "order_block_type", "order_block_age",
        "order_block_mitigation_state", "order_block_quality_score",
        "fvg_detected", "fvg_direction", "fvg_width", "fvg_fill_percentage", "fvg_quality_score",
        "equilibrium_price", "premium", "discount", "current_zone",
        "h1_trend", "h1_bos", "h1_choch", "h1_bias", "h1_confidence",
        "h4_trend", "h4_bos", "h4_choch", "h4_bias", "h4_confidence",
        "daily_trend", "daily_bos", "daily_choch", "daily_bias", "daily_confidence",
        "session", "kill_zone", "session_bias", "time_of_day", "day_of_week",
        "atr", "average_candle_size", "current_candle_size", "relative_volatility", "spread", "tick_volume",
        "structure_score", "bos_score", "choch_score", "liquidity_score", "ob_score", "fvg_score",
        "session_score", "htf_score", "risk_score", "unattributed_score", "final_score", "confidence",
        "risk_approved", "position_size", "sl_distance", "tp_distance", "rr",
        "portfolio_exposure", "correlation_score",
        "news_allowed", "minutes_to_next_news", "minutes_since_last_news", "news_severity",
        "decision_time", "entry_time", "entry_delay_minutes", "decision_candle", "entry_candle",
    )

    def capture_decision(self, *, pipeline_result, visible_candles, decision_time):
        candles = tuple(visible_candles or ())
        latest = candles[-1] if candles else None
        session = SessionEngine().detect(decision_time)
        zone = KillZoneEngine().detect(decision_time)
        sizes = [abs(float(c.high) - float(c.low)) for c in candles[-self.ATR_PERIOD:]]
        current_size = sizes[-1] if sizes else 0.0
        average_size = sum(sizes) / len(sizes) if sizes else 0.0
        atr = self._atr(candles[-self.ATR_PERIOD:])
        equilibrium, premium, discount, current_zone = self._premium_discount(pipeline_result)
        liquidity_distance = self._liquidity_distance(pipeline_result)
        score = int(getattr(pipeline_result, "score", 0) or 0)
        bos_score = 25 if getattr(pipeline_result, "bos_detected", False) else 0
        choch_score = 20 if getattr(pipeline_result, "choch_detected", False) else 0
        values = {field: self.NOT_AVAILABLE for field in self.FIELDS}
        values.update({
            "snapshot_version": "SPRINT_79_V1",
            "captured_at": self._iso(decision_time),
            "available_candle_count": len(candles),
            "latest_visible_candle_time": self._iso(getattr(latest, "time", None)),
            "structure": getattr(pipeline_result, "structure_state", "UNKNOWN"),
            "trend_strength": getattr(pipeline_result, "bos_progress", self.NOT_AVAILABLE),
            "swing_count": getattr(pipeline_result, "swing_count", 0),
            "bos": bool(getattr(pipeline_result, "bos_detected", False)),
            "bos_direction": getattr(pipeline_result, "bos_direction", ""),
            "bos_strength": getattr(pipeline_result, "bos_progress", self.NOT_AVAILABLE),
            "choch": bool(getattr(pipeline_result, "choch_detected", False)),
            "choch_direction": getattr(pipeline_result, "choch_direction", ""),
            "liquidity_detected": bool(getattr(pipeline_result, "liquidity_detected", False)),
            "liquidity_side": getattr(pipeline_result, "liquidity_side", ""),
            "liquidity_sweep": bool(getattr(pipeline_result, "liquidity_sweep", False)),
            "liquidity_distance": liquidity_distance,
            "order_block_detected": bool(getattr(pipeline_result, "order_block_detected", False)),
            "fvg_detected": bool(getattr(pipeline_result, "fair_value_gap_detected", False)),
            "equilibrium_price": equilibrium, "premium": premium, "discount": discount,
            "current_zone": current_zone,
            "session": session.name if session.active else "OFF_SESSION",
            "kill_zone": zone.name if zone.active else "NONE",
            "time_of_day": decision_time.strftime("%H:%M:%S") if decision_time else self.NOT_AVAILABLE,
            "day_of_week": decision_time.strftime("%A") if decision_time else self.NOT_AVAILABLE,
            "atr": atr, "average_candle_size": average_size, "current_candle_size": current_size,
            "relative_volatility": current_size / average_size if average_size else 0.0,
            "spread": getattr(latest, "spread", self.NOT_AVAILABLE),
            "tick_volume": getattr(latest, "tick_volume", self.NOT_AVAILABLE),
            # SmartMoneyPipeline currently scores only BOS and CHOCH.  Zeroes
            # below are exact score contributions, not missing estimates.
            "structure_score": 0, "bos_score": bos_score, "choch_score": choch_score,
            "liquidity_score": 0, "ob_score": 0, "fvg_score": 0,
            "session_score": 0, "htf_score": 0, "risk_score": 0,
            "unattributed_score": score - bos_score - choch_score,
            "final_score": score, "confidence": float(getattr(pipeline_result, "confidence", 0.0) or 0.0),
            "portfolio_exposure": 0.0, "correlation_score": 0.0,
            "decision_time": self._iso(decision_time),
            "decision_candle": self._candle_value(latest),
        })
        if sum(values[name] for name in ("structure_score", "bos_score", "choch_score", "liquidity_score", "ob_score", "fvg_score", "session_score", "htf_score", "risk_score", "unattributed_score")) != score:
            raise ValueError("Captured score components do not reconcile to final score")
        return ContextSnapshot.create(values)

    def capture_entry(self, decision_snapshot, *, entry_candle, entry_time,
                      risk_approved, position_size, sl_distance, tp_distance, rr):
        values = decision_snapshot.to_dict()
        decision_time = datetime.fromisoformat(values["decision_time"])
        values.update({
            "risk_approved": bool(risk_approved), "position_size": float(position_size),
            "sl_distance": float(sl_distance), "tp_distance": float(tp_distance), "rr": float(rr),
            "entry_time": self._iso(entry_time),
            "entry_delay_minutes": (entry_time - decision_time).total_seconds() / 60.0,
            "entry_candle": self._candle_value(entry_candle),
        })
        return ContextSnapshot.create(values)

    @staticmethod
    def _atr(candles):
        if not candles: return 0.0
        ranges = []
        for index, candle in enumerate(candles):
            previous_close = candles[index - 1].close if index else candle.open
            ranges.append(max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close)))
        return sum(ranges) / len(ranges)

    @classmethod
    def _premium_discount(cls, result):
        highs = [x for x in (getattr(result, "previous_high", None), getattr(result, "last_high", None)) if x is not None]
        lows = [x for x in (getattr(result, "previous_low", None), getattr(result, "last_low", None)) if x is not None]
        current = getattr(result, "current_close", None)
        if not highs or not lows or current is None: return (cls.NOT_AVAILABLE,) * 4
        high, low = max(highs), min(lows)
        if high <= low: return (cls.NOT_AVAILABLE,) * 4
        eq = (high + low) / 2.0
        zone = "PREMIUM" if current > eq else "DISCOUNT" if current < eq else "EQUILIBRIUM"
        return eq, [eq, high], [low, eq], zone

    @classmethod
    def _liquidity_distance(cls, result):
        current = getattr(result, "current_close", None)
        side = getattr(result, "liquidity_side", "")
        level = getattr(result, "last_high", None) if side == "BUY" else getattr(result, "last_low", None) if side == "SELL" else None
        return abs(current - level) if current is not None and level is not None else cls.NOT_AVAILABLE

    @staticmethod
    def _candle_value(candle):
        if candle is None: return None
        return {"time": ContextCaptureEngine._iso(candle.time), "open": candle.open, "high": candle.high, "low": candle.low, "close": candle.close, "spread": candle.spread, "tick_volume": candle.tick_volume}

    @staticmethod
    def _iso(value):
        return value.isoformat() if value is not None else None
