"""Idempotent journal application for confirmed offline closures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mss.analysis.demo_broker_offline_closure_reconciler import (
    DemoBrokerOfflineClosureResult,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
    ShadowTradeJournalBusyError,
)
from mss.analysis.virtual_position_engine import (
    VirtualPosition,
    VirtualPositionEngine,
)


@dataclass(frozen=True)
class DemoBrokerOfflineClosureApplicationResult:
    valid: bool = False
    applied: bool = False
    already_reconciled: bool = False
    reason: str = ""
    journal_event_sha256: str = ""
    real_order_send_allowed: bool = False


class DemoBrokerOfflineClosureJournalApplier:
    """Append one normal POSITION_CLOSED event after pure confirmation."""

    @staticmethod
    def _events(path: Path) -> tuple[dict, ...]:
        if not path.exists():
            return ()
        with path.open("r", encoding="utf-8") as handle:
            return tuple(json.loads(line) for line in handle if line.strip())

    @classmethod
    def apply(
        cls,
        *,
        journal_path,
        shadow_position: VirtualPosition,
        reconciliation: DemoBrokerOfflineClosureResult,
    ) -> DemoBrokerOfflineClosureApplicationResult:
        path = Path(journal_path)

        try:
            with ShadowTradeJournal.exclusive_transaction(path):
                return cls._apply_locked(
                    path=path,
                    shadow_position=shadow_position,
                    reconciliation=reconciliation,
                )
        except ShadowTradeJournalBusyError:
            return DemoBrokerOfflineClosureApplicationResult(
                reason="SHADOW_JOURNAL_TRANSACTION_BUSY"
            )

    @classmethod
    def _apply_locked(
        cls,
        *,
        path: Path,
        shadow_position: VirtualPosition,
        reconciliation: DemoBrokerOfflineClosureResult,
    ) -> DemoBrokerOfflineClosureApplicationResult:
        verification = ShadowTradeJournal.verify(path)
        if not verification["valid"]:
            return DemoBrokerOfflineClosureApplicationResult(
                reason="SHADOW_JOURNAL_INTEGRITY_FAILURE"
            )
        if not reconciliation.valid or not reconciliation.closure_confirmed:
            return DemoBrokerOfflineClosureApplicationResult(
                reason="OFFLINE_CLOSURE_NOT_CONFIRMED"
            )
        if (
            reconciliation.shadow_position_id != shadow_position.position_id
            or reconciliation.broker_position_identifier
            != shadow_position.broker_position_identifier
        ):
            return DemoBrokerOfflineClosureApplicationResult(
                reason="RECONCILIATION_SHADOW_IDENTITY_MISMATCH"
            )

        events = cls._events(path)
        open_events = tuple(
            event for event in events
            if event.get("event_type") == "POSITION_OPENED"
            and event.get("position_id") == shadow_position.position_id
        )
        if len(open_events) != 1 or not cls._open_matches(
            open_events[0], shadow_position
        ):
            return DemoBrokerOfflineClosureApplicationResult(
                reason="SHADOW_OPEN_EVENT_IDENTITY_MISMATCH"
            )

        closed_events = tuple(
            event for event in events
            if event.get("event_type") == "POSITION_CLOSED"
            and event.get("position_id") == shadow_position.position_id
        )
        if closed_events:
            event = closed_events[-1]
            payload = event.get("payload", {})
            if cls._matches(payload, event, reconciliation):
                return DemoBrokerOfflineClosureApplicationResult(
                    valid=True,
                    already_reconciled=True,
                    reason="OFFLINE_CLOSURE_ALREADY_RECONCILED",
                    journal_event_sha256=str(event.get("event_sha256", "")),
                )
            return DemoBrokerOfflineClosureApplicationResult(
                reason="CONFLICTING_EXISTING_POSITION_CLOSE"
            )

        closed = VirtualPositionEngine.close_position(
            position=shadow_position,
            close_price=reconciliation.exit_price,
            broker_epoch=reconciliation.exit_broker_epoch,
            reason=reconciliation.exit_reason,
            pnl_account_currency=reconciliation.net_result,
        )
        if closed.status != "CLOSED":
            return DemoBrokerOfflineClosureApplicationResult(
                reason="VIRTUAL_CLOSE_APPLICATION_FAILED"
            )
        event = ShadowTradeJournal._append_event_unlocked(
            path=path,
            event_type="POSITION_CLOSED",
            position_id=closed.position_id,
            broker_epoch=reconciliation.exit_broker_epoch,
            payload={
                "symbol": closed.symbol,
                "direction": closed.direction,
                "volume": closed.volume,
                "entry_price": closed.entry_price,
                "close_price": closed.close_price,
                "stop_loss": closed.stop_loss,
                "take_profit": closed.take_profit,
                "exit_reason": closed.exit_reason,
                "pnl_account_currency": closed.pnl_account_currency,
                "r_multiple": closed.r_multiple,
                "valuation_method": "BROKER_DEAL_HISTORY",
                "broker_position_identifier": reconciliation.broker_position_identifier,
                "exit_deal_ticket": reconciliation.exit_deal_ticket,
                "gross_profit": reconciliation.gross_profit,
                "commission": reconciliation.commission,
                "swap": reconciliation.swap,
                "fee": reconciliation.fee,
                "net_result": reconciliation.net_result,
            },
        )
        return DemoBrokerOfflineClosureApplicationResult(
            valid=True,
            applied=True,
            reason="OFFLINE_CLOSURE_APPLIED",
            journal_event_sha256=str(event["event_sha256"]),
        )

    @staticmethod
    def _matches(payload, event, reconciliation) -> bool:
        return (
            int(event.get("broker_epoch", 0))
            == reconciliation.exit_broker_epoch
            and float(payload.get("close_price", 0.0))
            == reconciliation.exit_price
            and str(payload.get("exit_reason", ""))
            == reconciliation.exit_reason
            and int(payload.get("broker_position_identifier", 0))
            == reconciliation.broker_position_identifier
            and int(payload.get("exit_deal_ticket", 0))
            == reconciliation.exit_deal_ticket
            and float(payload.get("gross_profit", 0.0))
            == reconciliation.gross_profit
            and float(payload.get("commission", 0.0))
            == reconciliation.commission
            and float(payload.get("swap", 0.0)) == reconciliation.swap
            and float(payload.get("fee", 0.0)) == reconciliation.fee
            and float(payload.get("net_result", 0.0))
            == reconciliation.net_result
        )

    @staticmethod
    def _open_matches(event, shadow_position) -> bool:
        payload = event.get("payload", {})
        return (
            int(event.get("broker_epoch", 0))
            == shadow_position.open_broker_epoch
            and str(payload.get("symbol", "")) == shadow_position.symbol
            and str(payload.get("direction", "")).upper()
            == shadow_position.direction.upper()
            and float(payload.get("volume", 0.0)) == shadow_position.volume
            and float(payload.get("entry_price", 0.0))
            == shadow_position.entry_price
            and int(payload.get("broker_position_ticket", 0))
            == shadow_position.broker_position_ticket
            and int(payload.get("broker_position_identifier", 0))
            == shadow_position.broker_position_identifier
        )
