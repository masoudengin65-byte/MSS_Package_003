"""Deterministic broker-aware monetary valuation for historical simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from bisect import bisect_right
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


@dataclass(frozen=True)
class HistoricalConversionPoint:
    """A rate whose timestamp is the candle completion time."""
    timestamp: datetime
    rate: float


@dataclass(frozen=True)
class HistoricalConversionResult:
    available: bool
    reason: str
    from_currency: str
    to_currency: str
    requested_time: datetime
    rate_time: datetime | None = None
    factor: float = 0.0
    path: str = ""


class HistoricalFxResolver:
    """Resolve deterministic one-leg direct/inverse completed-candle FX rates."""

    def __init__(self, series=None):
        self._series = {}
        for symbol, value in (series or {}).items():
            base, quote, points = value
            ordered = tuple(sorted(points, key=lambda item: item.timestamp))
            self._series[symbol] = (str(base).upper(), str(quote).upper(), ordered)

    def resolve(self, from_currency, to_currency, timestamp):
        source, target = str(from_currency).upper(), str(to_currency).upper()
        if source == target:
            return HistoricalConversionResult(
                True, "", source, target, timestamp, timestamp, 1.0,
                f"{source}->{target}:IDENTITY",
            )
        candidates = []
        for symbol, (base, quote, points) in sorted(self._series.items()):
            inverse = source == quote and target == base
            direct = source == base and target == quote
            if not (direct or inverse):
                continue
            times = [point.timestamp for point in points]
            index = bisect_right(times, timestamp) - 1
            if index < 0:
                continue
            point = points[index]
            if not math.isfinite(float(point.rate)) or float(point.rate) <= 0:
                continue
            factor = (1.0 / float(point.rate)) if inverse else float(point.rate)
            path = f"{source}->{target}:{symbol}:{'INVERSE' if inverse else 'DIRECT'}"
            candidates.append((point.timestamp, symbol, factor, path))
        if not candidates:
            return HistoricalConversionResult(
                False, "HISTORICAL_CONVERSION_UNAVAILABLE", source, target,
                timestamp,
            )
        rate_time, _, factor, path = max(candidates, key=lambda item: (item[0], item[1]))
        return HistoricalConversionResult(
            True, "", source, target, timestamp, rate_time, factor, path,
        )


class HistoricalValuation:
    """Value supported historical trades without current broker tick economics."""

    REQUIRED_FIELDS = (
        "point", "digits", "tick_size", "tick_value", "contract_size",
        "volume_min", "volume_max", "volume_step",
    )
    REQUIRED_TEXT_FIELDS = (
        "account_currency", "currency_base", "currency_profit", "currency_margin",
    )
    # MT5 FOREX (0), CFD (1), and CFDLEVERAGE (4) all use contract-size
    # price-difference profit in the broker metadata verified for this project.
    SUPPORTED_TRADE_CALC_MODES = (0, 1, 4)

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
        for field in cls.REQUIRED_TEXT_FIELDS:
            value = getattr(metadata, field, None)
            if not isinstance(value, str) or not value.strip():
                return f"MISSING_{field.upper()}"
        mode = getattr(metadata, "trade_calc_mode", None)
        if mode is None:
            return "MISSING_TRADE_CALC_MODE"
        if isinstance(mode, bool) or not isinstance(mode, int):
            return "INVALID_TRADE_CALC_MODE"
        if mode not in cls.SUPPORTED_TRADE_CALC_MODES:
            return f"UNSUPPORTED_TRADE_CALC_MODE:{mode}"
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
    def native_monetary_value(cls, price_delta, volume, metadata):
        error = cls.metadata_error(metadata)
        if error:
            raise ValueError(error)
        volume = float(volume)
        if not math.isfinite(volume) or volume < 0:
            raise ValueError("INVALID_VOLUME")
        return abs(float(price_delta)) * float(metadata.contract_size) * volume

    @classmethod
    def monetary_value(cls, price_delta, volume, metadata, conversion_factor=1.0):
        return cls.native_monetary_value(price_delta, volume, metadata) * float(conversion_factor)

    @classmethod
    def signed_pnl(
        cls, entry_price, exit_price, direction, volume, metadata,
        conversion_factor=1.0, commission=0.0,
    ):
        error = cls.metadata_error(metadata)
        if error:
            raise ValueError(error)
        if direction not in {"BUY", "SELL"}:
            raise ValueError("INVALID_DIRECTION")
        price_delta = float(exit_price) - float(entry_price)
        direction_sign = 1.0 if direction == "BUY" else -1.0
        gross = (
            price_delta * float(metadata.contract_size) * float(volume)
            * direction_sign
        )
        return gross * float(conversion_factor) - float(commission)

    @classmethod
    def size_for_risk(cls, risk_amount, stop_distance, metadata, conversion_factor=1.0):
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
        factor = float(conversion_factor)
        if not math.isfinite(factor) or factor <= 0:
            return cls._rejected("INVALID_CONVERSION_FACTOR", risk_amount)
        risk_per_lot = stop_distance * float(metadata.contract_size) * factor
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
