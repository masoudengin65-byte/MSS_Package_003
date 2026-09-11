"""FIBO-specific paired forward runtime, sealed pending activation verification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from mss.analysis.confluence_gated_smart_money_pipeline import (
    ConfluenceGatedSmartMoneyPipeline,
)
from mss.analysis.live_completed_candle_signal_engine import (
    LiveCompletedCandleSignalEngine,
)
from mss.analysis.shadow_trade_journal import ShadowTradeJournal
from mss.analysis.smart_money_pipeline import SmartMoneyPipeline

SYMBOL_MAP = {"BTCUSD": "BTC", "ETHUSD": "ETH"}
TIMEFRAME_SECONDS = 900
_FIBO_VERIFIED_ACTIVATION_MARKER = object()


@dataclass(frozen=True)
class FiboBoundarySnapshot:
    canonical_symbol: str
    broker_symbol: str
    account_server: str
    current_bar_epoch: int
    rates: Any


@dataclass(frozen=True)
class FiboVerifiedActivation:
    manifest_sha256: str
    first_eligible_epoch: int
    exclusive_end_epoch: int
    _verification_marker: object


class FiboGroupPairedForwardRuntime:
    VERSION = "MSS_SPRINT93_3F_FIBO_GROUP_PAIRED_FORWARD_RUNTIME_V1"

    def __init__(self, baseline_pipeline=None, candidate_pipeline=None):
        self.baseline = LiveCompletedCandleSignalEngine(
            baseline_pipeline or SmartMoneyPipeline()
        )
        self.candidate = LiveCompletedCandleSignalEngine(
            candidate_pipeline or ConfluenceGatedSmartMoneyPipeline()
        )

    @staticmethod
    def _decision(decision) -> dict[str, object]:
        return {
            "valid": decision.valid,
            "action": decision.action,
            "reason": decision.reason,
            "signal_bar_epoch": decision.signal_bar_epoch,
            "current_bar_epoch": decision.current_bar_epoch,
            "completed_candle_count": decision.completed_candle_count,
            "forming_candle_excluded": decision.forming_candle_excluded,
            "completed_candles_only": decision.completed_candles_only,
        }

    def evaluate_pair(
        self, snapshots: tuple[FiboBoundarySnapshot, ...]
    ) -> dict[str, object]:
        if tuple(item.canonical_symbol for item in snapshots) != tuple(SYMBOL_MAP):
            raise RuntimeError("snapshots must contain the exact ordered FIBO universe")
        boundary = snapshots[0].current_bar_epoch
        if boundary <= 0 or boundary % TIMEFRAME_SECONDS:
            raise RuntimeError("FIBO boundary must be a positive M15 epoch")
        if any(item.current_bar_epoch != boundary for item in snapshots):
            raise RuntimeError("FIBO snapshots do not share one boundary")
        branches = {}
        for snapshot in snapshots:
            if snapshot.broker_symbol != SYMBOL_MAP[snapshot.canonical_symbol]:
                raise RuntimeError("FIBO broker symbol mapping mismatch")
            if snapshot.account_server != "FIBOGroup-MT5 Server":
                raise RuntimeError("FIBO snapshot server mismatch")
            baseline = self.baseline.evaluate(
                symbol=snapshot.canonical_symbol,
                rates=snapshot.rates,
                current_bar_epoch=boundary,
            )
            candidate = self.candidate.evaluate(
                symbol=snapshot.canonical_symbol,
                rates=snapshot.rates,
                current_bar_epoch=boundary,
            )
            if not baseline.valid or not candidate.valid:
                raise RuntimeError("paired decision is invalid and cannot be journaled")
            branches[snapshot.canonical_symbol] = {
                "broker_symbol": snapshot.broker_symbol,
                "baseline": self._decision(baseline),
                "candidate": self._decision(candidate),
            }
        return {
            "runtime_version": self.VERSION,
            "boundary_epoch": boundary,
            "branches": branches,
            "safety": {
                "shadow_only": True,
                "order_check_called": False,
                "order_send_called": False,
                "real_order_send_allowed": False,
                "production_execution_enabled": False,
            },
        }

    @staticmethod
    def commit_pair(
        *,
        activation: FiboVerifiedActivation,
        journal_path: Path,
        evaluated: dict[str, object],
    ) -> dict[str, object]:
        if activation._verification_marker is not _FIBO_VERIFIED_ACTIVATION_MARKER:
            raise RuntimeError("verified FIBO activation context is required")
        boundary = evaluated.get("boundary_epoch")
        if not isinstance(boundary, int):
            raise RuntimeError("evaluated FIBO boundary is invalid")
        if (
            not activation.first_eligible_epoch
            <= boundary
            < activation.exclusive_end_epoch
        ):
            raise RuntimeError("FIBO boundary is outside the activated window")
        identity = {
            "manifest_sha256": activation.manifest_sha256,
            "boundary_epoch": boundary,
        }
        event_id = hashlib.sha256(
            (
                json.dumps(identity, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode()
        ).hexdigest()
        path = Path(journal_path)
        with ShadowTradeJournal.exclusive_transaction(path):
            verification = ShadowTradeJournal.verify(path)
            if not verification["valid"]:
                raise RuntimeError("FIBO journal integrity failure")
            for existing in ShadowTradeJournal._read_events(path):
                payload = existing.get("payload", {})
                if (
                    payload.get("activation_manifest_sha256")
                    == activation.manifest_sha256
                    and payload.get("boundary_epoch") == boundary
                ):
                    raise RuntimeError("duplicate FIBO boundary is prohibited")
            payload = {
                "activation_manifest_sha256": activation.manifest_sha256,
                "boundary_epoch": boundary,
                "branches": evaluated["branches"],
                "phase": "PAIRED_DECISION",
            }
            return ShadowTradeJournal._append_event_unlocked(
                path=path,
                event_type="SPRINT93_3F_FIBO_PAIRED_DECISION",
                position_id=event_id,
                broker_epoch=boundary,
                payload=payload,
            )
