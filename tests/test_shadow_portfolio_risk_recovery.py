from pathlib import Path

import pytest

from mss.analysis.shadow_portfolio_risk_recovery import (
    ShadowPortfolioRiskRecovery,
)
from mss.analysis.shadow_portfolio_risk_state import (
    ShadowPortfolioRiskState,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


def open_payload():
    return {
        "symbol": "EURUSD",
        "direction": "BUY",
        "risk_percent": 0.75,
        "risk_amount": 75.0,
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profit": 1.1100,
    }


def append_open(
    path: Path,
    position_id="P1",
):
    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_OPENED",
        position_id=position_id,
        broker_epoch=1000,
        payload=open_payload(),
    )


def test_empty_journal_recovers_empty_snapshot(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is True

    assert (
        result.reason
        ==
        "NO_OPEN_PORTFOLIO_RISK_POSITION"
    )

    assert result.open_position_count == 0

    assert result.snapshot is not None
    assert result.snapshot.valid is True
    assert result.snapshot.positions == ()


def test_open_position_risk_state_is_recovered(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    append_open(path)

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is True

    assert (
        result.reason
        ==
        "OPEN_PORTFOLIO_RISK_STATE_RECOVERED"
    )

    assert result.open_position_count == 1
    assert result.snapshot is not None

    position = (
        result.snapshot.positions[0]
    )

    assert position.position_id == "P1"
    assert position.symbol == "EURUSD"
    assert position.direction == "BUY"

    assert (
        position.risk_percent
        == pytest.approx(0.75)
    )

    assert (
        position.risk_amount
        == pytest.approx(75.0)
    )

    assert (
        position.journal_path
        == str(path.resolve())
    )

    assert position.asset_class == "FOREX"

    assert position.exposure_tags == (
        "LONG:EUR",
        "SHORT:USD",
    )


def test_recovered_state_converts_to_governor_position(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    append_open(path)

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    governor_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            result.snapshot
        )
    )

    assert len(governor_positions) == 1

    position = governor_positions[0]

    assert position.symbol == "EURUSD"

    assert (
        position.risk_percent
        == pytest.approx(0.75)
    )

    assert position.asset_class == "FOREX"

    assert position.exposure_tags == (
        "LONG:EUR",
        "SHORT:USD",
    )


def test_open_then_close_recovers_no_position(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    append_open(path)

    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_CLOSED",
        position_id="P1",
        broker_epoch=2000,
        payload={
            "symbol": "EURUSD",
        },
    )

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is True
    assert result.open_position_count == 0

    assert (
        result.reason
        ==
        "NO_OPEN_PORTFOLIO_RISK_POSITION"
    )


def test_missing_risk_data_fails_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    payload = open_payload()

    payload.pop(
        "risk_percent"
    )

    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_OPENED",
        position_id="P1",
        broker_epoch=1000,
        payload=payload,
    )

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "INVALID_POSITION_OPEN_RISK_EVENT"
    )


def test_duplicate_active_open_fails_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    append_open(
        path,
        position_id="P1",
    )

    append_open(
        path,
        position_id="P1",
    )

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "DUPLICATE_OPEN_POSITION_ID"
    )


def test_close_without_open_fails_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_CLOSED",
        position_id="P1",
        broker_epoch=1000,
        payload={},
    )

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "CLOSE_WITHOUT_OPEN_POSITION"
    )


def test_unknown_event_fails_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_NOTE",
        position_id="P1",
        broker_epoch=1000,
        payload={},
    )

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "UNSUPPORTED_SHADOW_JOURNAL_EVENT"
    )


def test_tampered_hash_chain_fails_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    append_open(path)

    text = path.read_text(
        encoding="utf-8"
    )

    text = text.replace(
        '"risk_amount":75.0',
        '"risk_amount":76.0',
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "SHADOW_JOURNAL_INTEGRITY_FAILURE"
    )


def test_malformed_json_fails_safe_without_exception(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_positions.jsonl"
    )

    path.write_text(
        "{broken-json\n",
        encoding="utf-8",
    )

    result = (
        ShadowPortfolioRiskRecovery
        .recover(path)
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "SHADOW_JOURNAL_INTEGRITY_FAILURE"
    )
