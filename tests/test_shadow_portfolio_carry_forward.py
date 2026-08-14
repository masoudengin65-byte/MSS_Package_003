import hashlib
import json
from pathlib import Path

import pytest

from mss.analysis.shadow_portfolio_carry_forward import (
    ShadowPortfolioCarryForward,
)
from mss.analysis.shadow_portfolio_risk_recovery import (
    ShadowPortfolioRiskRecovery,
)
from mss.analysis.shadow_position_recovery import (
    ShadowPositionRecovery,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


POSITION_ID = "SHADOW-GBPUSD-1000"
SYMBOL = "GBPUSD"


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def make_source_open(
    path: Path,
):
    return ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_OPENED",
        position_id=POSITION_ID,
        broker_epoch=1000,
        payload={
            "symbol": SYMBOL,
            "direction": "BUY",
            "volume": 0.01,
            "entry_price": 1.3500,
            "stop_loss": 1.3450,
            "take_profit": 1.3600,
            "initial_risk_price": 0.0050,
            "risk_percent": 1.0,
            "risk_amount": 5.0,
            "loss_per_one_lot": 500.0,
            "raw_volume": 0.01,
            "normalized_volume": 0.01,
            "broker_volume_min": 0.01,
            "broker_volume_max": 100.0,
            "broker_volume_step": 0.01,
        },
    )


def paths(tmp_path):
    predecessor = (
        tmp_path
        / "sprint92h14_5a"
        / SYMBOL
        / "shadow_positions.jsonl"
    )

    current = (
        tmp_path
        / "sprint92h14_5b_1"
        / SYMBOL
        / "shadow_positions.jsonl"
    )

    return predecessor, current


def import_position(
    predecessor,
    current,
):
    return (
        ShadowPortfolioCarryForward
        .import_open_position(
            predecessor_journal_path=(
                predecessor
            ),
            current_journal_path=current,
            expected_position_id=(
                POSITION_ID
            ),
            expected_symbol=SYMBOL,
        )
    )


def test_first_import_succeeds_and_preserves_source(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    source_event = make_source_open(
        predecessor
    )

    source_hash_before = sha256(
        predecessor
    )

    result = import_position(
        predecessor,
        current,
    )

    source_hash_after = sha256(
        predecessor
    )

    assert result.valid is True
    assert result.action == "IMPORTED"

    assert (
        result.reason
        ==
        "PREDECESSOR_POSITION_CARRIED_FORWARD"
    )

    assert result.position_id == POSITION_ID
    assert result.symbol == SYMBOL

    assert (
        result.source_event_sha256
        ==
        source_event["event_sha256"]
    )

    assert result.target_event_sha256

    assert (
        source_hash_before
        ==
        source_hash_after
    )

    assert (
        result.predecessor_sha256_before
        ==
        source_hash_before
    )

    assert (
        result.predecessor_sha256_after
        ==
        source_hash_after
    )


def test_imported_event_contains_full_provenance(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    source_event = make_source_open(
        predecessor
    )

    source_hash = sha256(
        predecessor
    )

    result = import_position(
        predecessor,
        current,
    )

    assert result.valid is True

    line = current.read_text(
        encoding="utf-8"
    ).strip()

    event = json.loads(
        line
    )

    assert (
        event["event_type"]
        == "POSITION_OPENED"
    )

    assert (
        event["position_id"]
        == POSITION_ID
    )

    continuity = (
        event["payload"][
            "continuity_import"
        ]
    )

    assert (
        continuity[
            "source_position_id"
        ]
        == POSITION_ID
    )

    assert (
        continuity[
            "source_event_sha256"
        ]
        ==
        source_event["event_sha256"]
    )

    assert (
        continuity[
            "source_journal_sha256"
        ]
        == source_hash
    )

    assert (
        continuity[
            "predecessor_read_only"
        ]
        is True
    )

    assert (
        continuity[
            "performance_evidence"
        ]
        is False
    )


def test_import_is_compatible_with_both_recovery_layers(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    result = import_position(
        predecessor,
        current,
    )

    assert result.valid is True

    lifecycle = (
        ShadowPositionRecovery
        .recover(current)
    )

    assert lifecycle.valid is True

    assert (
        lifecycle.open_position_count
        == 1
    )

    assert lifecycle.position is not None

    assert (
        lifecycle.position.position_id
        == POSITION_ID
    )

    assert (
        lifecycle.position.symbol
        == SYMBOL
    )

    risk = (
        ShadowPortfolioRiskRecovery
        .recover(current)
    )

    assert risk.valid is True
    assert risk.open_position_count == 1
    assert risk.snapshot is not None

    position = (
        risk.snapshot.positions[0]
    )

    assert (
        position.position_id
        == POSITION_ID
    )

    assert position.symbol == SYMBOL

    assert (
        position.risk_percent
        == pytest.approx(1.0)
    )

    assert (
        position.risk_amount
        == pytest.approx(5.0)
    )


def test_second_import_is_idempotent(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    first = import_position(
        predecessor,
        current,
    )

    assert first.valid is True
    assert first.action == "IMPORTED"

    current_hash_before = sha256(
        current
    )

    second = import_position(
        predecessor,
        current,
    )

    current_hash_after = sha256(
        current
    )

    assert second.valid is True

    assert (
        second.action
        == "ALREADY_IMPORTED"
    )

    assert (
        second.reason
        ==
        "PREDECESSOR_POSITION_ALREADY_CONSUMED"
    )

    assert (
        current_hash_before
        ==
        current_hash_after
    )

    verification = (
        ShadowTradeJournal.verify(
            current
        )
    )

    assert verification["valid"] is True
    assert verification["event_count"] == 1


def test_closed_import_is_never_resurrected_on_restart(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    first = import_position(
        predecessor,
        current,
    )

    assert first.valid is True

    ShadowTradeJournal.append_event(
        path=current,
        event_type="POSITION_CLOSED",
        position_id=POSITION_ID,
        broker_epoch=2000,
        payload={
            "symbol": SYMBOL,
            "direction": "BUY",
            "volume": 0.01,
            "entry_price": 1.3500,
            "close_price": 1.3600,
            "stop_loss": 1.3450,
            "take_profit": 1.3600,
            "exit_reason": "TAKE_PROFIT",
            "pnl_account_currency": 10.0,
            "r_multiple": 2.0,
        },
    )

    lifecycle = (
        ShadowPositionRecovery
        .recover(current)
    )

    assert lifecycle.valid is True

    assert (
        lifecycle.open_position_count
        == 0
    )

    before_restart_hash = sha256(
        current
    )

    restart = import_position(
        predecessor,
        current,
    )

    after_restart_hash = sha256(
        current
    )

    assert restart.valid is True

    assert (
        restart.action
        == "ALREADY_IMPORTED"
    )

    assert (
        restart.reason
        ==
        "PREDECESSOR_POSITION_ALREADY_CONSUMED"
    )

    assert (
        before_restart_hash
        ==
        after_restart_hash
    )

    lifecycle_after = (
        ShadowPositionRecovery
        .recover(current)
    )

    assert lifecycle_after.valid is True

    assert (
        lifecycle_after.open_position_count
        == 0
    )


def test_tampered_predecessor_is_rejected(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    text = predecessor.read_text(
        encoding="utf-8"
    )

    text = text.replace(
        '"risk_amount":5.0',
        '"risk_amount":6.0',
    )

    predecessor.write_text(
        text,
        encoding="utf-8",
    )

    result = import_position(
        predecessor,
        current,
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "PREDECESSOR_JOURNAL_INTEGRITY_FAILURE"
    )

    assert not current.exists()


def test_true_oos_source_path_is_rejected(
    tmp_path,
):
    predecessor = (
        tmp_path
        / "research_data"
        / "sprint92h_true_oos_v2"
        / SYMBOL
        / "shadow_positions.jsonl"
    )

    current = (
        tmp_path
        / "sprint92h14_5b_1"
        / SYMBOL
        / "shadow_positions.jsonl"
    )

    make_source_open(
        predecessor
    )

    result = import_position(
        predecessor,
        current,
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "PROHIBITED_JOURNAL_PATH"
    )

    assert not current.exists()


def test_true_oos_target_path_is_rejected(
    tmp_path,
):
    predecessor = (
        tmp_path
        / "sprint92h14_5a"
        / SYMBOL
        / "shadow_positions.jsonl"
    )

    current = (
        tmp_path
        / "research_data"
        / "true_oos"
        / SYMBOL
        / "shadow_positions.jsonl"
    )

    make_source_open(
        predecessor
    )

    source_hash_before = sha256(
        predecessor
    )

    result = import_position(
        predecessor,
        current,
    )

    source_hash_after = sha256(
        predecessor
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "PROHIBITED_JOURNAL_PATH"
    )

    assert (
        source_hash_before
        ==
        source_hash_after
    )

    assert not current.exists()


def test_non_pristine_target_is_blocked(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    ShadowTradeJournal.append_event(
        path=current,
        event_type="POSITION_OPENED",
        position_id="OTHER-POSITION",
        broker_epoch=500,
        payload={
            "symbol": SYMBOL,
        },
    )

    current_hash_before = sha256(
        current
    )

    result = import_position(
        predecessor,
        current,
    )

    current_hash_after = sha256(
        current
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "CURRENT_JOURNAL_NOT_PRISTINE"
    )

    assert (
        current_hash_before
        ==
        current_hash_after
    )


def test_source_target_collision_is_blocked(
    tmp_path,
):
    predecessor, _ = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    source_hash_before = sha256(
        predecessor
    )

    result = (
        ShadowPortfolioCarryForward
        .import_open_position(
            predecessor_journal_path=(
                predecessor
            ),
            current_journal_path=(
                predecessor
            ),
            expected_position_id=(
                POSITION_ID
            ),
            expected_symbol=SYMBOL,
        )
    )

    source_hash_after = sha256(
        predecessor
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "SOURCE_TARGET_JOURNAL_COLLISION"
    )

    assert (
        source_hash_before
        ==
        source_hash_after
    )


def test_staged_lifecycle_failure_never_commits_target(
    tmp_path,
    monkeypatch,
):
    from mss.analysis.shadow_position_recovery import (
        ShadowPositionRecovery,
        ShadowPositionRecoveryResult,
    )

    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    predecessor_hash_before = sha256(
        predecessor
    )

    def forced_lifecycle_failure(path):
        return ShadowPositionRecoveryResult(
            valid=False,
            reason=(
                "FORCED_LIFECYCLE_FAILURE"
            ),
            event_count=1,
            open_position_count=0,
            position=None,
            real_order_send_allowed=False,
        )

    monkeypatch.setattr(
        ShadowPositionRecovery,
        "recover",
        forced_lifecycle_failure,
    )

    result = import_position(
        predecessor,
        current,
    )

    predecessor_hash_after = sha256(
        predecessor
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "STAGED_LIFECYCLE_RECOVERY_FAILURE"
    )

    # Real target was never atomically committed.
    assert not current.exists()

    # Frozen predecessor remained byte-identical.
    assert (
        predecessor_hash_before
        ==
        predecessor_hash_after
    )

    # Temporary transaction artifact was cleaned.
    leftovers = tuple(
        current.parent.glob(
            current.name
            + ".carry_forward.*.tmp"
        )
    )

    assert leftovers == ()


def test_staged_risk_failure_never_commits_target(
    tmp_path,
    monkeypatch,
):
    from mss.analysis.shadow_portfolio_risk_recovery import (
        ShadowPortfolioRiskRecovery,
        ShadowPortfolioRiskRecoveryResult,
    )

    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    predecessor_hash_before = sha256(
        predecessor
    )

    def forced_risk_failure(path):
        return ShadowPortfolioRiskRecoveryResult(
            valid=False,
            reason=(
                "FORCED_RISK_FAILURE"
            ),
            event_count=1,
            open_position_count=0,
            snapshot=None,
        )

    monkeypatch.setattr(
        ShadowPortfolioRiskRecovery,
        "recover",
        forced_risk_failure,
    )

    result = import_position(
        predecessor,
        current,
    )

    predecessor_hash_after = sha256(
        predecessor
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "STAGED_RISK_RECOVERY_FAILURE"
    )

    # Real target was never atomically committed.
    assert not current.exists()

    # Frozen predecessor remained byte-identical.
    assert (
        predecessor_hash_before
        ==
        predecessor_hash_after
    )

    # Temporary transaction artifact was cleaned.
    leftovers = tuple(
        current.parent.glob(
            current.name
            + ".carry_forward.*.tmp"
        )
    )

    assert leftovers == ()


def test_atomic_commit_failure_is_fail_safe(
    tmp_path,
    monkeypatch,
):
    import mss.analysis.shadow_portfolio_carry_forward as carry_forward_module

    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    predecessor_hash_before = sha256(
        predecessor
    )

    def forced_replace_failure(
        source,
        destination,
    ):
        raise OSError(
            "FORCED_ATOMIC_REPLACE_FAILURE"
        )

    monkeypatch.setattr(
        carry_forward_module.os,
        "replace",
        forced_replace_failure,
    )

    result = import_position(
        predecessor,
        current,
    )

    predecessor_hash_after = sha256(
        predecessor
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "ATOMIC_COMMIT_FAILED"
    )

    # No real target journal was committed.
    assert not current.exists()

    # Predecessor remains byte-for-byte unchanged.
    assert (
        predecessor_hash_before
        ==
        predecessor_hash_after
    )

    assert (
        result.predecessor_sha256_before
        ==
        predecessor_hash_before
    )

    assert (
        result.predecessor_sha256_after
        ==
        predecessor_hash_after
    )

    # Staging artifact must always be cleaned.
    leftovers = tuple(
        current.parent.glob(
            current.name
            + ".carry_forward.*.tmp"
        )
    )

    assert leftovers == ()


def test_consumption_inspector_before_import_is_false(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    source_hash_before = sha256(
        predecessor
    )

    result = (
        ShadowPortfolioCarryForward
        .inspect_consumption(
            predecessor_journal_path=(
                predecessor
            ),
            current_journal_path=current,
            expected_position_id=(
                POSITION_ID
            ),
            expected_symbol=SYMBOL,
        )
    )

    source_hash_after = sha256(
        predecessor
    )

    assert result.valid is True
    assert result.consumed is False

    assert (
        result.reason
        ==
        "PREDECESSOR_POSITION_NOT_YET_CONSUMED"
    )

    assert not current.exists()

    assert (
        source_hash_before
        ==
        source_hash_after
    )


def test_consumption_inspector_after_import_is_true(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    imported = import_position(
        predecessor,
        current,
    )

    assert imported.valid is True
    assert imported.action == "IMPORTED"

    current_hash_before = sha256(
        current
    )

    result = (
        ShadowPortfolioCarryForward
        .inspect_consumption(
            predecessor_journal_path=(
                predecessor
            ),
            current_journal_path=current,
            expected_position_id=(
                POSITION_ID
            ),
            expected_symbol=SYMBOL,
        )
    )

    current_hash_after = sha256(
        current
    )

    assert result.valid is True
    assert result.consumed is True

    assert (
        result.reason
        ==
        "PREDECESSOR_POSITION_ALREADY_CONSUMED"
    )

    assert (
        current_hash_before
        ==
        current_hash_after
    )


def test_consumption_remains_true_after_current_close(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    imported = import_position(
        predecessor,
        current,
    )

    assert imported.valid is True

    ShadowTradeJournal.append_event(
        path=current,
        event_type="POSITION_CLOSED",
        position_id=POSITION_ID,
        broker_epoch=2000,
        payload={
            "symbol": SYMBOL,
            "direction": "BUY",
            "volume": 0.01,
            "entry_price": 1.3500,
            "close_price": 1.3600,
            "stop_loss": 1.3450,
            "take_profit": 1.3600,
            "exit_reason": "TAKE_PROFIT",
            "pnl_account_currency": 10.0,
            "r_multiple": 2.0,
        },
    )

    lifecycle = (
        ShadowPositionRecovery
        .recover(current)
    )

    assert lifecycle.valid is True
    assert lifecycle.open_position_count == 0

    current_hash_before = sha256(
        current
    )

    result = (
        ShadowPortfolioCarryForward
        .inspect_consumption(
            predecessor_journal_path=(
                predecessor
            ),
            current_journal_path=current,
            expected_position_id=(
                POSITION_ID
            ),
            expected_symbol=SYMBOL,
        )
    )

    current_hash_after = sha256(
        current
    )

    assert result.valid is True
    assert result.consumed is True

    assert (
        result.reason
        ==
        "PREDECESSOR_POSITION_ALREADY_CONSUMED"
    )

    assert (
        current_hash_before
        ==
        current_hash_after
    )


def test_consumption_inspector_rejects_tampered_current(
    tmp_path,
):
    predecessor, current = paths(
        tmp_path
    )

    make_source_open(
        predecessor
    )

    imported = import_position(
        predecessor,
        current,
    )

    assert imported.valid is True

    text = current.read_text(
        encoding="utf-8"
    )

    text = text.replace(
        '"risk_amount":5.0',
        '"risk_amount":6.0',
    )

    current.write_text(
        text,
        encoding="utf-8",
    )

    result = (
        ShadowPortfolioCarryForward
        .inspect_consumption(
            predecessor_journal_path=(
                predecessor
            ),
            current_journal_path=current,
            expected_position_id=(
                POSITION_ID
            ),
            expected_symbol=SYMBOL,
        )
    )

    assert result.valid is False
    assert result.consumed is False

    assert (
        result.reason
        ==
        "CURRENT_JOURNAL_INTEGRITY_FAILURE"
    )
