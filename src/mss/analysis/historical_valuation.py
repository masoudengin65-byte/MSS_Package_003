"""Deterministic broker-aware monetary valuation for historical simulation."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class HistoricalPositionSizing:
    valid: bool
    reason: str
    risk_amount: float
    stop_tick_count: float
    risk_per_lot: float
    raw_volume: float
    rounded_volume: float
    rounded_risk_amount: float


class HistoricalValuation:
    """Convert price movement to account currency using broker tick economics."""

    REQUIRED_FIELDS = (
        "point", "digits", "tick_size", "tick_value", "contract_size",
        "volume_min", "volume_max", "volume_step",
    )

    @classmethod
    def metadata_error(cls, metadata):
        if metadata is None:
            return "MISSING_METADATA"
        for field in cls.REQUIRED_FIELDS:
            value = getattr(metadata, field, None)
            if value is None or isinstance(value, bool):
                return f"MISSING_{field.upper()}"
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return f"INVALID_{field.upper()}"
            if not math.isfinite(numeric):
                return f"INVALID_{field.upper()}"
            if field == "digits":
                if numeric < 0 or not numeric.is_integer():
                    return "INVALID_DIGITS"
            elif numeric <= 0:
                return f"INVALID_{field.upper()}"
        if float(metadata.volume_min) > float(metadata.volume_max):
            return "INVALID_VOLUME_RANGE"
        return ""

    @classmethod
    def tick_count(cls, price_delta, metadata):
        error = cls.metadata_error(metadata)
        if error:
            raise ValueError(error)
        delta = abs(float(price_delta))
        if not math.isfinite(delta):
            raise ValueError("INVALID_PRICE_DELTA")
        return delta / float(metadata.tick_size)

    @classmethod
    def monetary_value(cls, price_delta, volume, metadata):
        error = cls.metadata_error(metadata)
        if error:
            raise ValueError(error)
        volume = float(volume)
        if not math.isfinite(volume) or volume < 0:
            raise ValueError("INVALID_VOLUME")
        return cls.tick_count(price_delta, metadata) * float(metadata.tick_value) * volume

    @classmethod
    def signed_pnl(
        cls, entry_price, exit_price, direction, volume, metadata, commission=0.0,
    ):
        error = cls.metadata_error(metadata)
        if error:
            raise ValueError(error)
        if direction not in {"BUY", "SELL"}:
            raise ValueError("INVALID_DIRECTION")
        price_delta = float(exit_price) - float(entry_price)
        direction_sign = 1.0 if direction == "BUY" else -1.0
        gross = (
            price_delta / float(metadata.tick_size)
            * float(metadata.tick_value)
            * float(volume)
            * direction_sign
        )
        return gross - float(commission)

    @classmethod
    def size_for_risk(cls, risk_amount, stop_distance, metadata):
        error = cls.metadata_error(metadata)
        risk_amount = float(risk_amount)
        stop_distance = abs(float(stop_distance))
        if error:
            return cls._rejected(error, risk_amount)
        if not math.isfinite(risk_amount) or risk_amount <= 0:
            return cls._rejected("INVALID_RISK_AMOUNT", risk_amount)
        if not math.isfinite(stop_distance) or stop_distance <= 0:
            return cls._rejected("INVALID_STOP_DISTANCE", risk_amount)

        stop_ticks = cls.tick_count(stop_distance, metadata)
        risk_per_lot = stop_ticks * float(metadata.tick_value)
        raw_volume = risk_amount / risk_per_lot
        minimum = float(metadata.volume_min)
        maximum = float(metadata.volume_max)
        step = float(metadata.volume_step)
        tolerance = max(1e-12, minimum * 1e-12)
        if raw_volume < minimum - tolerance:
            return HistoricalPositionSizing(
                False, "MIN_VOLUME_EXCEEDS_RISK", risk_amount, stop_ticks,
                risk_per_lot, raw_volume, 0.0, 0.0,
            )

        capped = min(raw_volume, maximum)
        steps = math.floor((capped + step * 1e-12) / step)
        rounded_volume = steps * step
        if rounded_volume < minimum:
            rounded_volume = minimum
        decimals = max(0, len(str(step).split(".")[-1]))
        rounded_volume = round(rounded_volume, decimals)
        rounded_risk = risk_per_lot * rounded_volume
        if rounded_risk > risk_amount + max(1e-9, risk_amount * 1e-12):
            return HistoricalPositionSizing(
                False, "ROUNDED_VOLUME_EXCEEDS_RISK", risk_amount, stop_ticks,
                risk_per_lot, raw_volume, 0.0, 0.0,
            )
        return HistoricalPositionSizing(
            True, "", risk_amount, stop_ticks, risk_per_lot, raw_volume,
            rounded_volume, rounded_risk,
        )

    @staticmethod
    def _rejected(reason, risk_amount):
        return HistoricalPositionSizing(
            False, reason, risk_amount, 0.0, 0.0, 0.0, 0.0, 0.0,
        )
