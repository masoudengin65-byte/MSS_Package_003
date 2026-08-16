from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional


@dataclass(frozen=True)
class ShadowLiveHeartbeatInput:
    started_monotonic: float
    now_monotonic: float
    last_heartbeat_monotonic: Optional[float]
    heartbeat_sequence: int
    max_heartbeat_gap_seconds: float


@dataclass(frozen=True)
class ShadowLiveHeartbeatDecision:
    valid: bool
    healthy: bool
    hard_block: bool
    reason: str

    heartbeat_sequence: int

    uptime_seconds: float
    heartbeat_gap_seconds: float

    next_last_heartbeat_monotonic: float
    next_heartbeat_sequence: int


class ShadowLiveRuntimeHeartbeat:
    REASON_HEARTBEAT_INITIALIZED = (
        "RUNTIME_HEARTBEAT_INITIALIZED"
    )

    REASON_HEARTBEAT_HEALTHY = (
        "RUNTIME_HEARTBEAT_HEALTHY"
    )

    REASON_HEARTBEAT_STALE = (
        "RUNTIME_HEARTBEAT_STALE"
    )

    REASON_INVALID_INPUT = (
        "INVALID_RUNTIME_HEARTBEAT_INPUT"
    )

    @classmethod
    def evaluate(
        cls,
        heartbeat: ShadowLiveHeartbeatInput,
    ) -> ShadowLiveHeartbeatDecision:

        if not isinstance(
            heartbeat,
            ShadowLiveHeartbeatInput,
        ):
            return cls._invalid()

        started = heartbeat.started_monotonic
        now = heartbeat.now_monotonic
        last = heartbeat.last_heartbeat_monotonic
        sequence = heartbeat.heartbeat_sequence
        max_gap = heartbeat.max_heartbeat_gap_seconds

        numeric_values = (
            started,
            now,
            max_gap,
        )

        if not all(
            isinstance(value, (int, float))
            and math.isfinite(float(value))
            for value in numeric_values
        ):
            return cls._invalid()

        started = float(started)
        now = float(now)
        max_gap = float(max_gap)

        if (
            started < 0.0
            or
            now < 0.0
            or
            now < started
            or
            max_gap <= 0.0
        ):
            return cls._invalid()

        if (
            not isinstance(sequence, int)
            or
            isinstance(sequence, bool)
            or
            sequence < 0
        ):
            return cls._invalid()

        uptime = (
            now
            - started
        )

        if last is None:
            if sequence != 0:
                return cls._invalid()

            return ShadowLiveHeartbeatDecision(
                valid=True,
                healthy=True,
                hard_block=False,
                reason=(
                    cls.REASON_HEARTBEAT_INITIALIZED
                ),
                heartbeat_sequence=sequence,
                uptime_seconds=uptime,
                heartbeat_gap_seconds=0.0,
                next_last_heartbeat_monotonic=now,
                next_heartbeat_sequence=1,
            )

        if (
            not isinstance(last, (int, float))
            or
            not math.isfinite(float(last))
        ):
            return cls._invalid()

        last = float(last)

        if (
            last < started
            or
            last > now
            or
            sequence <= 0
        ):
            return cls._invalid()

        gap = (
            now
            - last
        )

        if gap > max_gap:
            return ShadowLiveHeartbeatDecision(
                valid=True,
                healthy=False,
                hard_block=True,
                reason=(
                    cls.REASON_HEARTBEAT_STALE
                ),
                heartbeat_sequence=sequence,
                uptime_seconds=uptime,
                heartbeat_gap_seconds=gap,
                next_last_heartbeat_monotonic=now,
                next_heartbeat_sequence=(
                    sequence + 1
                ),
            )

        return ShadowLiveHeartbeatDecision(
            valid=True,
            healthy=True,
            hard_block=False,
            reason=(
                cls.REASON_HEARTBEAT_HEALTHY
            ),
            heartbeat_sequence=sequence,
            uptime_seconds=uptime,
            heartbeat_gap_seconds=gap,
            next_last_heartbeat_monotonic=now,
            next_heartbeat_sequence=(
                sequence + 1
            ),
        )

    @classmethod
    def _invalid(
        cls,
    ) -> ShadowLiveHeartbeatDecision:
        return ShadowLiveHeartbeatDecision(
            valid=False,
            healthy=False,
            hard_block=True,
            reason=cls.REASON_INVALID_INPUT,
            heartbeat_sequence=0,
            uptime_seconds=0.0,
            heartbeat_gap_seconds=0.0,
            next_last_heartbeat_monotonic=0.0,
            next_heartbeat_sequence=0,
        )
