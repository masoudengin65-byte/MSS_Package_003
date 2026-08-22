from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event, Lock

import pytest

from mss.analysis.demo_broker_offline_closure_reconciler import (
    DemoBrokerDealSnapshot,
    DemoBrokerOfflineClosureReconciler,
)
from mss.analysis.demo_broker_offline_closure_journal_applier import (
    DemoBrokerOfflineClosureJournalApplier,
)
from mss.analysis.shadow_position_recovery import ShadowPositionRecovery
from mss.analysis.shadow_trade_journal import ShadowTradeJournal
from mss.analysis.virtual_position_engine import VirtualPositionEngine


IDENTIFIER = 98765


@pytest.fixture
def shadow():
    return VirtualPositionEngine.open_position(
        position_id="SHADOW-EURGBP-1",
        symbol="EURGBP",
        direction="SELL",
        volume=0.01,
        entry_price=0.85698,
        stop_loss=0.85760,
        take_profit=0.85553,
        broker_epoch=1000,
        broker_position_ticket=98764,
        broker_position_identifier=IDENTIFIER,
    )


@pytest.fixture
def deals():
    return (
        DemoBrokerDealSnapshot(
            ticket=101,
            position_identifier=IDENTIFIER,
            order_ticket=91,
            magic=920146,
            comment="MSS_DEMO_FORWARD",
            symbol="EURGBP",
            direction="SELL",
            entry_kind="IN",
            reason="CLIENT",
            volume=0.01,
            price=0.85698,
            broker_epoch=1000,
            profit=1.25,
            commission=-0.20,
            swap=0.03,
            fee=-0.01,
        ),
        DemoBrokerDealSnapshot(
            ticket=102,
            position_identifier=IDENTIFIER,
            order_ticket=92,
            magic=920146,
            comment="MSS_DEMO_FORWARD",
            symbol="EURGBP",
            direction="BUY",
            entry_kind="OUT",
            reason="SL",
            volume=0.01,
            price=0.85760,
            broker_epoch=1100,
            profit=8.75,
            commission=-0.30,
            swap=-0.13,
            fee=-0.02,
        ),
    )


def reconcile(shadow, deals, positions=0, orders=0):
    return DemoBrokerOfflineClosureReconciler.reconcile(
        shadow_position=shadow,
        current_mss_position_count=positions,
        pending_mss_order_count=orders,
        deals=deals,
    )


def test_clean_history_confirms_authoritative_closure(shadow, deals):
    result = reconcile(shadow, deals)
    assert result.valid and result.closure_confirmed
    assert result.reason == "BROKER_OFFLINE_CLOSURE_CONFIRMED"
    assert result.exit_deal_ticket == 102
    assert result.exit_price == 0.85760
    assert result.exit_broker_epoch == 1100
    assert result.real_order_send_allowed is False


@pytest.mark.parametrize(("broker_reason", "expected"), [
    ("SL", "STOP_LOSS"),
    ("TP", "TAKE_PROFIT"),
    ("CLIENT", "BROKER_MANUAL_OR_OTHER_EXIT"),
])
def test_broker_exit_reason_mapping(shadow, deals, broker_reason, expected):
    changed = (deals[0], replace(deals[1], reason=broker_reason))
    assert reconcile(shadow, changed).exit_reason == expected


def test_lifecycle_pnl_includes_entry_side_costs(shadow, deals):
    result = reconcile(shadow, deals)
    assert result.gross_profit == pytest.approx(10.00)
    assert result.commission == pytest.approx(-0.50)
    assert result.swap == pytest.approx(-0.10)
    assert result.fee == pytest.approx(-0.03)
    assert result.net_result == pytest.approx(9.37)


@pytest.mark.parametrize(("changed_deals", "reason"), [
    ((), "BROKER_DEAL_HISTORY_MISSING"),
    ((1,), "BROKER_ENTRY_DEAL_MISSING"),
    ((0,), "BROKER_EXIT_DEAL_MISSING"),
])
def test_missing_history_lifecycle_blocks(
    shadow, deals, changed_deals, reason
):
    selected = tuple(deals[index] for index in changed_deals)
    assert reconcile(shadow, selected).reason == reason


def test_multiple_exits_and_partial_close_block(shadow, deals):
    extra_exit = replace(deals[1], ticket=103, broker_epoch=1101)
    assert reconcile(shadow, deals + (extra_exit,)).reason == (
        "AMBIGUOUS_MULTIPLE_EXIT_DEALS"
    )
    partial = (deals[0], replace(deals[1], volume=0.005))
    assert reconcile(shadow, partial).reason == (
        "PARTIAL_OR_INCONSISTENT_CLOSE_VOLUME"
    )


def test_identity_symbol_epoch_and_direction_mismatches_block(shadow, deals):
    wrong_id = tuple(replace(item, position_identifier=55) for item in deals)
    assert reconcile(shadow, wrong_id).reason == (
        "BROKER_POSITION_IDENTIFIER_MISMATCH"
    )
    wrong_symbol = (deals[0], replace(deals[1], symbol="GBPUSD"))
    assert reconcile(shadow, wrong_symbol).reason == (
        "BROKER_SHADOW_SYMBOL_MISMATCH"
    )
    bad_epoch = (deals[0], replace(deals[1], broker_epoch=1000))
    assert reconcile(shadow, bad_epoch).reason == (
        "BROKER_EXIT_EPOCH_NOT_AFTER_OPEN"
    )
    bad_direction = (deals[0], replace(deals[1], direction="SELL"))
    assert reconcile(shadow, bad_direction).reason == (
        "BROKER_EXIT_DIRECTION_MISMATCH"
    )
    bad_entry_epoch = (replace(deals[0], broker_epoch=999), deals[1])
    assert reconcile(shadow, bad_entry_epoch).reason == (
        "BROKER_ENTRY_EPOCH_MISMATCH"
    )
    bad_entry_price = (replace(deals[0], price=0.85697), deals[1])
    assert reconcile(shadow, bad_entry_price).reason == (
        "BROKER_SHADOW_ENTRY_PRICE_MISMATCH"
    )


def test_exposure_pending_invalid_shadow_and_missing_identity_block(shadow, deals):
    assert reconcile(shadow, deals, positions=1).reason == (
        "BROKER_EXPOSURE_STILL_PRESENT"
    )
    assert reconcile(shadow, deals, orders=1).reason == (
        "MSS_PENDING_ORDER_PRESENT"
    )
    assert reconcile(replace(shadow, status="CLOSED"), deals).reason == (
        "INVALID_OPEN_SHADOW_POSITION"
    )
    assert reconcile(
        replace(shadow, broker_position_identifier=0), deals
    ).reason == "SHADOW_BROKER_POSITION_IDENTITY_MISSING"


def write_open(path, shadow, *, include_identity=True):
    payload = {
        "symbol": shadow.symbol,
        "direction": shadow.direction,
        "volume": shadow.volume,
        "entry_price": shadow.entry_price,
        "stop_loss": shadow.stop_loss,
        "take_profit": shadow.take_profit,
        "initial_risk_price": shadow.initial_risk_price,
        "risk_percent": 1.0,
        "risk_amount": 100.0,
    }
    if include_identity:
        payload.update({
            "broker_position_ticket": shadow.broker_position_ticket,
            "broker_position_identifier": shadow.broker_position_identifier,
        })
    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_OPENED",
        position_id=shadow.position_id,
        broker_epoch=shadow.open_broker_epoch,
        payload=payload,
    )


def test_application_is_hash_valid_idempotent_and_recovers_closed(
    tmp_path, shadow, deals
):
    path = tmp_path / "shadow.jsonl"
    write_open(path, shadow)
    reconciliation = reconcile(shadow, deals)

    first = DemoBrokerOfflineClosureJournalApplier.apply(
        journal_path=path,
        shadow_position=shadow,
        reconciliation=reconciliation,
    )
    content_after_first = path.read_bytes()
    second = DemoBrokerOfflineClosureJournalApplier.apply(
        journal_path=path,
        shadow_position=shadow,
        reconciliation=reconciliation,
    )

    assert first.valid and first.applied
    assert second.valid and second.already_reconciled
    assert path.read_bytes() == content_after_first
    assert ShadowTradeJournal.verify(path)["valid"]
    recovered = ShadowPositionRecovery.recover(path)
    assert recovered.valid
    assert recovered.open_position_count == 0


def test_concurrent_application_fails_safe_without_duplicate_close(
    tmp_path, shadow, deals, monkeypatch
):
    path = tmp_path / "concurrent-shadow.jsonl"
    write_open(path, shadow)
    reconciliation = reconcile(shadow, deals)
    first_reader_entered = Event()
    release_first_reader = Event()
    reader_guard = Lock()
    reader_count = 0
    original_events = DemoBrokerOfflineClosureJournalApplier._events

    def blocking_first_reader(journal_path):
        nonlocal reader_count
        with reader_guard:
            reader_count += 1
            is_first_reader = reader_count == 1
        if is_first_reader:
            first_reader_entered.set()
            assert release_first_reader.wait(timeout=2.0)
        return original_events(journal_path)

    monkeypatch.setattr(
        DemoBrokerOfflineClosureJournalApplier,
        "_events",
        staticmethod(blocking_first_reader),
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(
            DemoBrokerOfflineClosureJournalApplier.apply,
            journal_path=path,
            shadow_position=shadow,
            reconciliation=reconciliation,
        )
        assert first_reader_entered.wait(timeout=2.0)
        blocked = DemoBrokerOfflineClosureJournalApplier.apply(
            journal_path=path,
            shadow_position=shadow,
            reconciliation=reconciliation,
        )
        release_first_reader.set()
        applied = first.result(timeout=2.0)

    assert not blocked.valid
    assert blocked.reason == "SHADOW_JOURNAL_TRANSACTION_BUSY"
    assert applied.valid and applied.applied
    verification = ShadowTradeJournal.verify(path)
    assert verification["valid"]
    assert verification["event_count"] == 2


def test_unconfirmed_closure_cannot_mutate_journal(tmp_path, shadow, deals):
    path = tmp_path / "shadow.jsonl"
    write_open(path, shadow)
    before = path.read_bytes()
    blocked = reconcile(shadow, ())
    applied = DemoBrokerOfflineClosureJournalApplier.apply(
        journal_path=path,
        shadow_position=shadow,
        reconciliation=blocked,
    )
    assert not applied.valid
    assert path.read_bytes() == before


@pytest.mark.parametrize("blocked_case", [
    "MISSING",
    "PARTIAL",
    "AMBIGUOUS",
    "PENDING",
    "EXPOSURE",
])
def test_every_blocked_history_state_leaves_journal_byte_identical(
    tmp_path, shadow, deals, blocked_case
):
    path = tmp_path / "shadow.jsonl"
    write_open(path, shadow)
    before = path.read_bytes()
    if blocked_case == "MISSING":
        result = reconcile(shadow, ())
    elif blocked_case == "PARTIAL":
        result = reconcile(
            shadow, (deals[0], replace(deals[1], volume=0.005))
        )
    elif blocked_case == "AMBIGUOUS":
        result = reconcile(
            shadow,
            deals + (replace(deals[1], ticket=103, broker_epoch=1101),),
        )
    elif blocked_case == "PENDING":
        result = reconcile(shadow, deals, orders=1)
    else:
        result = reconcile(shadow, deals, positions=1)
    application = DemoBrokerOfflineClosureJournalApplier.apply(
        journal_path=path,
        shadow_position=shadow,
        reconciliation=result,
    )
    assert not result.valid
    assert not application.valid
    assert path.read_bytes() == before


def test_conflicting_existing_close_is_rejected_without_mutation(
    tmp_path, shadow, deals
):
    path = tmp_path / "shadow.jsonl"
    write_open(path, shadow)
    confirmed = reconcile(shadow, deals)
    first = DemoBrokerOfflineClosureJournalApplier.apply(
        journal_path=path,
        shadow_position=shadow,
        reconciliation=confirmed,
    )
    assert first.applied
    before = path.read_bytes()
    conflict = replace(confirmed, net_result=confirmed.net_result + 1.0)
    second = DemoBrokerOfflineClosureJournalApplier.apply(
        journal_path=path,
        shadow_position=shadow,
        reconciliation=conflict,
    )
    assert not second.valid
    assert second.reason == "CONFLICTING_EXISTING_POSITION_CLOSE"
    assert path.read_bytes() == before


def test_legacy_eurgbp_mismatch_and_missing_identity_fail_without_write(tmp_path):
    path = tmp_path / "legacy-eurgbp.jsonl"
    legacy = VirtualPositionEngine.open_position(
        position_id="SHADOW-EURGBP-LEGACY",
        symbol="EURGBP",
        direction="SELL",
        volume=0.01,
        entry_price=0.8569100000000001,
        stop_loss=0.85760,
        take_profit=0.85553,
        broker_epoch=1787240700,
    )
    write_open(path, legacy, include_identity=False)
    before = path.read_bytes()
    historical_deals = (
        replace(
            DemoBrokerDealSnapshot(),
            ticket=201,
            position_identifier=367746308,
            magic=920146,
            symbol="EURGBP",
            direction="SELL",
            entry_kind="IN",
            reason="CLIENT",
            volume=0.01,
            price=0.85698,
            broker_epoch=1787240705,
        ),
        replace(
            DemoBrokerDealSnapshot(),
            ticket=202,
            position_identifier=367746308,
            magic=920146,
            symbol="EURGBP",
            direction="BUY",
            entry_kind="OUT",
            reason="SL",
            volume=0.01,
            price=0.85760,
            broker_epoch=1787240800,
        ),
    )
    result = reconcile(legacy, historical_deals)
    application = DemoBrokerOfflineClosureJournalApplier.apply(
        journal_path=path,
        shadow_position=legacy,
        reconciliation=result,
    )
    assert result.reason == "SHADOW_BROKER_POSITION_IDENTITY_MISSING"
    assert not application.valid
    assert path.read_bytes() == before


def test_nonfinite_broker_accounting_fails_without_journal_mutation(
    tmp_path, shadow, deals
):
    path = tmp_path / "shadow.jsonl"
    write_open(path, shadow)
    before = path.read_bytes()
    invalid_deals = (deals[0], replace(deals[1], commission=float("nan")))
    result = reconcile(shadow, invalid_deals)
    application = DemoBrokerOfflineClosureJournalApplier.apply(
        journal_path=path,
        shadow_position=shadow,
        reconciliation=result,
    )
    assert result.reason == "INVALID_BROKER_DEAL_METADATA"
    assert not application.valid
    assert path.read_bytes() == before
