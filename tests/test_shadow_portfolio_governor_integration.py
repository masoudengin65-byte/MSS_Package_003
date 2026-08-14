from pathlib import Path

import pytest

from mss.analysis.instrument_profile_registry import (
    InstrumentProfileRegistry,
)
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
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


def append_open(
    path: Path,
    *,
    position_id: str,
    symbol: str,
    direction: str,
    risk_percent: float = 1.0,
    risk_amount: float = 100.0,
):
    if direction == "BUY":
        if symbol == "GBPUSD":
            entry = 1.3500
            stop = 1.3450
            take = 1.3600
        elif symbol == "EURUSD":
            entry = 1.1000
            stop = 1.0950
            take = 1.1100
        elif symbol == "XAUUSD":
            entry = 2000.0
            stop = 1990.0
            take = 2020.0
        else:
            entry = 100.0
            stop = 95.0
            take = 110.0

    else:
        if symbol == "GBPUSD":
            entry = 1.3500
            stop = 1.3550
            take = 1.3400
        elif symbol == "EURUSD":
            entry = 1.1000
            stop = 1.1050
            take = 1.0900
        elif symbol == "XAUUSD":
            entry = 2000.0
            stop = 2010.0
            take = 1980.0
        else:
            entry = 100.0
            stop = 105.0
            take = 90.0

    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_OPENED",
        position_id=position_id,
        broker_epoch=1000,
        payload={
            "symbol": symbol,
            "direction": direction,
            "risk_percent": risk_percent,
            "risk_amount": risk_amount,
            "entry_price": entry,
            "stop_loss": stop,
            "take_profit": take,
        },
    )


def recover_portfolio(
    tmp_path: Path,
    positions,
):
    sources = []

    for (
        symbol,
        direction,
        position_id,
    ) in positions:

        path = (
            tmp_path
            / symbol
            / "shadow_positions.jsonl"
        )

        append_open(
            path,
            position_id=position_id,
            symbol=symbol,
            direction=direction,
        )

        sources.append(
            ShadowPortfolioJournalSource(
                symbol=symbol,
                journal_path=str(path),
            )
        )

    result = (
        ShadowPortfolioRiskAggregator
        .recover(
            sources=tuple(sources)
        )
    )

    assert result.valid is True
    assert result.snapshot is not None

    return result


def evaluate_candidate(
    *,
    symbol: str,
    direction: str,
    open_positions,
    risk_percent: float = 1.0,
):
    exposure = (
        InstrumentProfileRegistry
        .directional_exposure(
            symbol=symbol,
            direction=direction,
        )
    )

    assert exposure is not None

    return (
        PortfolioRiskGovernor
        .evaluate(
            candidate_symbol=symbol,
            candidate_asset_class=(
                exposure.asset_class
            ),
            candidate_risk_percent=(
                risk_percent
            ),
            candidate_exposure_tags=(
                exposure.exposure_tags
            ),
            open_positions=open_positions,
        )
    )


def test_recovered_two_percent_portfolio_blocks_third_position(
    tmp_path,
):
    result = recover_portfolio(
        tmp_path,
        (
            (
                "GBPUSD",
                "BUY",
                "GBP-1",
            ),
            (
                "XAUUSD",
                "SELL",
                "XAU-1",
            ),
        ),
    )

    assert (
        result.snapshot
        .total_risk_percent
        == pytest.approx(2.0)
    )

    open_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            result.snapshot
        )
    )

    decision = evaluate_candidate(
        symbol="WTI",
        direction="BUY",
        open_positions=open_positions,
        risk_percent=0.5,
    )

    assert decision.allowed is False

    assert (
        decision.reason
        ==
        "MAX_SIMULTANEOUS_POSITIONS"
    )

    assert (
        decision.total_open_risk_percent
        == pytest.approx(2.0)
    )

    assert decision.open_position_count == 2
    assert decision.projected_position_count == 3


def test_recovered_forex_position_blocks_second_forex(
    tmp_path,
):
    result = recover_portfolio(
        tmp_path,
        (
            (
                "GBPUSD",
                "BUY",
                "GBP-1",
            ),
        ),
    )

    open_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            result.snapshot
        )
    )

    decision = evaluate_candidate(
        symbol="EURUSD",
        direction="SELL",
        open_positions=open_positions,
    )

    assert decision.allowed is False

    assert (
        decision.reason
        ==
        "ASSET_CLASS_CONCENTRATION"
    )


def test_recovered_short_usd_exposure_blocks_another_short_usd(
    tmp_path,
):
    result = recover_portfolio(
        tmp_path,
        (
            (
                "GBPUSD",
                "BUY",
                "GBP-1",
            ),
        ),
    )

    open_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            result.snapshot
        )
    )

    decision = evaluate_candidate(
        symbol="XAUUSD",
        direction="BUY",
        open_positions=open_positions,
    )

    assert decision.allowed is False

    assert (
        decision.reason
        ==
        "DIRECTIONAL_EXPOSURE_CONCENTRATION"
    )


def test_opposite_usd_exposure_different_asset_class_is_allowed(
    tmp_path,
):
    result = recover_portfolio(
        tmp_path,
        (
            (
                "GBPUSD",
                "BUY",
                "GBP-1",
            ),
        ),
    )

    open_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            result.snapshot
        )
    )

    decision = evaluate_candidate(
        symbol="XAUUSD",
        direction="SELL",
        open_positions=open_positions,
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


def test_recovered_symbol_blocks_duplicate_symbol_candidate(
    tmp_path,
):
    result = recover_portfolio(
        tmp_path,
        (
            (
                "GBPUSD",
                "BUY",
                "GBP-1",
            ),
        ),
    )

    open_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            result.snapshot
        )
    )

    decision = evaluate_candidate(
        symbol="GBPUSD",
        direction="SELL",
        open_positions=open_positions,
    )

    assert decision.allowed is False

    assert (
        decision.reason
        ==
        "DUPLICATE_SYMBOL_POSITION"
    )
