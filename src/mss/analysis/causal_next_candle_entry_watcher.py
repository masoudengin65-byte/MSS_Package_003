"""Causal next-candle entry watcher for MSS Shadow Live."""

from __future__ import annotations

from dataclasses import dataclass

from mss.analysis.frozen_shadow_strategy_adapter import (
    FrozenShadowEntry,
    FrozenShadowSignal,
    FrozenShadowStrategyAdapter,
)


@dataclass(frozen=True)
class NextCandleEntryWatchResult:
    valid: bool = False

    action: str = "BLOCKED"
    reason: str = ""

    previous_current_bar_epoch: int = 0
    current_bar_epoch: int = 0

    exact_bar_transition_observed: bool = False
    bar_transition_missed: bool = False

    next_candle_sequence_confirmed: bool = False

    signal_valid: bool = False
    entry: FrozenShadowEntry | None = None

    shadow_entry_allowed: bool = False

    real_order_send_allowed: bool = False
    order_send_called: bool = False
    order_check_called: bool = False


class CausalNextCandleEntryWatcher:
    """
    Sprint 92H.14.3.3

    Causal NEXT_CANDLE_OPEN gate.

    The next candle is defined by actual MT5 trading-bar
    sequence, not by assuming signal_epoch + 900 seconds.

    This preserves the frozen historical contract across:
    - normal M15 transitions
    - weekends
    - broker/session closures

    No retrospective fills.
    No real broker execution.
    """

    VERSION = (
        "MSS_SPRINT92H14_3_3_"
        "CAUSAL_NEXT_CANDLE_WATCHER_V2"
    )

    @classmethod
    def evaluate(
        cls,
        *,
        signal: FrozenShadowSignal | None,
        previous_current_bar_epoch: int,
        current_bar_epoch: int,
        next_candle_sequence_confirmed: bool,
        next_candle_open: float,
        spread_points: float,
        point: float,
    ) -> NextCandleEntryWatchResult:

        previous_epoch = int(
            previous_current_bar_epoch
        )

        current_epoch = int(
            current_bar_epoch
        )

        if (
            previous_epoch <= 0
            or current_epoch <= 0
        ):
            return NextCandleEntryWatchResult(
                reason="INVALID_BAR_EPOCH",
                previous_current_bar_epoch=(
                    previous_epoch
                ),
                current_bar_epoch=(
                    current_epoch
                ),
            )

        if current_epoch < previous_epoch:
            return NextCandleEntryWatchResult(
                reason="BAR_TIME_REGRESSION",
                previous_current_bar_epoch=(
                    previous_epoch
                ),
                current_bar_epoch=(
                    current_epoch
                ),
            )

        if current_epoch == previous_epoch:
            return NextCandleEntryWatchResult(
                valid=True,
                action="WAIT_FOR_NEXT_BAR",
                reason="BAR_NOT_TRANSITIONED",
                previous_current_bar_epoch=(
                    previous_epoch
                ),
                current_bar_epoch=(
                    current_epoch
                ),
            )

        if not next_candle_sequence_confirmed:
            return NextCandleEntryWatchResult(
                valid=False,
                action="ENTRY_WINDOW_MISSED",
                reason=(
                    "NEXT_CANDLE_SEQUENCE_NOT_CONFIRMED"
                ),
                previous_current_bar_epoch=(
                    previous_epoch
                ),
                current_bar_epoch=(
                    current_epoch
                ),
                bar_transition_missed=True,
                next_candle_sequence_confirmed=False,
            )

        if signal is None:
            return NextCandleEntryWatchResult(
                valid=True,
                action="NO_SIGNAL",
                reason="NO_FROZEN_SIGNAL",
                previous_current_bar_epoch=(
                    previous_epoch
                ),
                current_bar_epoch=(
                    current_epoch
                ),
                exact_bar_transition_observed=True,
                next_candle_sequence_confirmed=True,
            )

        if not signal.valid:
            return NextCandleEntryWatchResult(
                valid=True,
                action="NO_SIGNAL",
                reason=(
                    signal.reason
                    or "SIGNAL_INVALID"
                ),
                previous_current_bar_epoch=(
                    previous_epoch
                ),
                current_bar_epoch=(
                    current_epoch
                ),
                exact_bar_transition_observed=True,
                next_candle_sequence_confirmed=True,
                signal_valid=False,
            )

        if (
            signal.signal_bar_epoch
            != previous_epoch
        ):
            return NextCandleEntryWatchResult(
                valid=False,
                action="ENTRY_BLOCKED",
                reason=(
                    "SIGNAL_BAR_DOES_NOT_MATCH_"
                    "OBSERVED_PREVIOUS_BAR"
                ),
                previous_current_bar_epoch=(
                    previous_epoch
                ),
                current_bar_epoch=(
                    current_epoch
                ),
                exact_bar_transition_observed=True,
                next_candle_sequence_confirmed=True,
                signal_valid=True,
            )

        entry = (
            FrozenShadowStrategyAdapter
            .activate_entry(
                signal=signal,
                entry_bar_epoch=current_epoch,
                next_candle_sequence_confirmed=True,
                next_candle_open=(
                    next_candle_open
                ),
                spread_points=(
                    spread_points
                ),
                point=point,
            )
        )

        if not entry.valid:
            return NextCandleEntryWatchResult(
                valid=False,
                action="ENTRY_BLOCKED",
                reason=entry.reason,
                previous_current_bar_epoch=(
                    previous_epoch
                ),
                current_bar_epoch=(
                    current_epoch
                ),
                exact_bar_transition_observed=True,
                next_candle_sequence_confirmed=True,
                signal_valid=True,
                entry=entry,
            )

        return NextCandleEntryWatchResult(
            valid=True,
            action="SHADOW_ENTRY_READY",
            reason=(
                "CAUSAL_NEXT_CANDLE_ENTRY_VALID"
            ),
            previous_current_bar_epoch=(
                previous_epoch
            ),
            current_bar_epoch=(
                current_epoch
            ),
            exact_bar_transition_observed=True,
            next_candle_sequence_confirmed=True,
            signal_valid=True,
            entry=entry,
            shadow_entry_allowed=True,
            real_order_send_allowed=False,
            order_send_called=False,
            order_check_called=False,
        )
