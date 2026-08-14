from pathlib import Path

import pytest

from mss.analysis.portfolio_risk_governor import (
    PortfolioRiskGovernor,
)
from mss.analysis.shadow_portfolio_risk_aggregator import (
    ShadowPortfolioJournalSource,
    ShadowPortfolioRiskAggregator,
)
from mss.analysis.shadow_portfolio_risk_state import (
    ShadowPortfolioRiskState,
)
from mss.analysis.instrument_profile_registry import (
    InstrumentProfileRegistry,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


def append_open(
    path: Path,
    *,
    position_id: str,
    symbol: str,
    direction: str,
    risk_percent: float,
    risk_amount: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    broker_epoch: int,
):
    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_OPENED",
        position_id=position_id,
        broker_epoch=broker_epoch,
        payload={
            "symbol": symbol,
            "direction": direction,
            "risk_percent": risk_percent,
            "risk_amount": risk_amount,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        },
    )


def make_gbp_journal(
    tmp_path: Path,
) -> Path:
    path = (
        tmp_path
        / "GBPUSD"
        / "shadow_positions.jsonl"
    )

    append_open(
        path,
        position_id="GBP-1",
        symbol="GBPUSD",
        direction="BUY",
        risk_percent=1.0,
        risk_amount=100.0,
        entry_price=1.3500,
        stop_loss=1.3450,
        take_profit=1.3600,
        broker_epoch=1000,
    )

    return path


def make_xau_journal(
    tmp_path: Path,
) -> Path:
    path = (
        tmp_path
        / "XAUUSD"
        / "shadow_positions.jsonl"
    )

    append_open(
        path,
        position_id="XAU-1",
        symbol="XAUUSD",
        direction="SELL",
        risk_percent=1.0,
        risk_amount=100.0,
        entry_price=2000.0,
        stop_loss=2010.0,
        take_profit=1980.0,
        broker_epoch=2000,
    )

    return path


def test_two_symbol_journals_aggregate_to_two_percent(
    tmp_path,
):
    gbp = make_gbp_journal(
        tmp_path
    )

    xau = make_xau_journal(
        tmp_path
    )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(gbp),
                ),
                ShadowPortfolioJournalSource(
                    symbol="XAUUSD",
                    journal_path=str(xau),
                ),
            )
        )
    )

    assert result.valid is True

    assert (
        result.reason
        ==
        "PORTFOLIO_RISK_STATE_AGGREGATED"
    )

    assert result.source_count == 2
    assert result.recovered_source_count == 2
    assert result.open_position_count == 2

    assert result.snapshot is not None

    assert (
        result.snapshot.total_risk_percent
        == pytest.approx(2.0)
    )

    assert (
        result.snapshot.total_risk_amount
        == pytest.approx(200.0)
    )

    assert tuple(
        position.symbol
        for position
        in result.snapshot.positions
    ) == (
        "GBPUSD",
        "XAUUSD",
    )


def test_source_input_order_does_not_change_result(
    tmp_path,
):
    gbp = make_gbp_journal(
        tmp_path
    )

    xau = make_xau_journal(
        tmp_path
    )

    forward = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(gbp),
                ),
                ShadowPortfolioJournalSource(
                    symbol="XAUUSD",
                    journal_path=str(xau),
                ),
            )
        )
    )

    reverse = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="XAUUSD",
                    journal_path=str(xau),
                ),
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(gbp),
                ),
            )
        )
    )

    assert forward.valid is True
    assert reverse.valid is True

    assert (
        forward.snapshot.positions
        ==
        reverse.snapshot.positions
    )

    assert (
        forward.snapshot.total_risk_percent
        ==
        reverse.snapshot.total_risk_percent
    )


def test_recovered_open_position_drives_projected_two_percent(
    tmp_path,
):
    gbp = make_gbp_journal(
        tmp_path
    )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(gbp),
                ),
            )
        )
    )

    assert result.valid is True
    assert result.snapshot is not None

    open_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            result.snapshot
        )
    )

    exposure = (
        InstrumentProfileRegistry
        .directional_exposure(
            symbol="XAUUSD",
            direction="SELL",
        )
    )

    assert exposure is not None

    decision = (
        PortfolioRiskGovernor
        .evaluate(
            candidate_symbol="XAUUSD",
            candidate_asset_class=(
                exposure.asset_class
            ),
            candidate_risk_percent=1.0,
            candidate_exposure_tags=(
                exposure.exposure_tags
            ),
            open_positions=open_positions,
        )
    )

    assert decision.allowed is True

    assert (
        decision.reason
        ==
        "PORTFOLIO_RISK_ALLOWED"
    )

    assert (
        decision.total_open_risk_percent
        == pytest.approx(1.0)
    )

    assert (
        decision.projected_total_risk_percent
        == pytest.approx(2.0)
    )

    assert decision.open_position_count == 1
    assert decision.projected_position_count == 2


def test_duplicate_source_symbol_fails_safe(
    tmp_path,
):
    first = (
        tmp_path
        / "one"
        / "shadow_positions.jsonl"
    )

    second = (
        tmp_path
        / "two"
        / "shadow_positions.jsonl"
    )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(first),
                ),
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(second),
                ),
            )
        )
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "DUPLICATE_SOURCE_SYMBOL"
    )


def test_duplicate_journal_path_fails_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "shared"
        / "shadow_positions.jsonl"
    )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(path),
                ),
                ShadowPortfolioJournalSource(
                    symbol="XAUUSD",
                    journal_path=str(path),
                ),
            )
        )
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "DUPLICATE_JOURNAL_PATH"
    )


def test_journal_symbol_mismatch_fails_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "EURUSD"
        / "shadow_positions.jsonl"
    )

    append_open(
        path,
        position_id="P1",
        symbol="GBPUSD",
        direction="BUY",
        risk_percent=1.0,
        risk_amount=100.0,
        entry_price=1.3500,
        stop_loss=1.3450,
        take_profit=1.3600,
        broker_epoch=1000,
    )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="EURUSD",
                    journal_path=str(path),
                ),
            )
        )
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "JOURNAL_SYMBOL_MISMATCH"
    )

    assert result.failed_symbol == "EURUSD"
    assert result.failed_reason == "GBPUSD"


def test_tampered_journal_blocks_entire_portfolio(
    tmp_path,
):
    gbp = make_gbp_journal(
        tmp_path
    )

    xau = make_xau_journal(
        tmp_path
    )

    text = xau.read_text(
        encoding="utf-8"
    )

    text = text.replace(
        '"risk_amount":100.0',
        '"risk_amount":101.0',
    )

    xau.write_text(
        text,
        encoding="utf-8",
    )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(gbp),
                ),
                ShadowPortfolioJournalSource(
                    symbol="XAUUSD",
                    journal_path=str(xau),
                ),
            )
        )
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "JOURNAL_RECOVERY_FAILED"
    )

    assert result.failed_symbol == "XAUUSD"

    assert (
        result.failed_reason
        ==
        "SHADOW_JOURNAL_INTEGRITY_FAILURE"
    )


def test_true_oos_path_is_rejected_before_read(
    tmp_path,
):
    prohibited = (
        tmp_path
        / "research_data"
        / "sprint92h_true_oos_v2"
        / "GBPUSD"
        / "shadow_positions.jsonl"
    )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="GBPUSD",
                    journal_path=str(prohibited),
                ),
            )
        )
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "INVALID_OR_PROHIBITED_JOURNAL_PATH"
    )


def test_unsupported_source_symbol_fails_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "UNKNOWN"
        / "shadow_positions.jsonl"
    )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=(
                ShadowPortfolioJournalSource(
                    symbol="UNKNOWN",
                    journal_path=str(path),
                ),
            )
        )
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "UNSUPPORTED_SOURCE_SYMBOL"
    )


def test_no_sources_fails_safe():
    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=()
        )
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "NO_JOURNAL_SOURCES"
    )
