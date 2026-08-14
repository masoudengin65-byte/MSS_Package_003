import pytest

from mss.analysis.shadow_portfolio_risk_state import (
    ShadowPortfolioPositionState,
    ShadowPortfolioRiskState,
)


def build_valid_buy():
    return (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P1",
            journal_path=(
                "shadow_data/live/test/"
                "EURUSD/shadow_positions.jsonl"
            ),
            symbol="EURUSD",
            direction="BUY",
            risk_percent=0.75,
            risk_amount=75.0,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            open_broker_epoch=1000,
        )
    )


def build_valid_sell():
    return (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P2",
            journal_path=(
                "shadow_data/live/test/"
                "XAUUSD/shadow_positions.jsonl"
            ),
            symbol="XAUUSD",
            direction="SELL",
            risk_percent=0.50,
            risk_amount=50.0,
            entry_price=2000.0,
            stop_loss=2010.0,
            take_profit=1980.0,
            open_broker_epoch=2000,
        )
    )


def test_build_valid_buy_position():
    position = build_valid_buy()

    assert position is not None
    assert position.symbol == "EURUSD"
    assert position.direction == "BUY"
    assert position.asset_class == "FOREX"
    assert position.exposure_tags == (
        "LONG:EUR",
        "SHORT:USD",
    )


def test_build_valid_sell_position():
    position = build_valid_sell()

    assert position is not None
    assert position.asset_class == "METALS"
    assert position.exposure_tags == (
        "SHORT:XAU",
        "LONG:USD",
    )


def test_invalid_risk_is_blocked():
    position = (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P1",
            journal_path=(
                "shadow_data/live/test/"
                "EURUSD/shadow_positions.jsonl"
            ),
            symbol="EURUSD",
            direction="BUY",
            risk_percent=0.0,
            risk_amount=0.0,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            open_broker_epoch=1000,
        )
    )

    assert position is None


def test_invalid_buy_geometry_is_blocked():
    position = (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P1",
            journal_path=(
                "shadow_data/live/test/"
                "EURUSD/shadow_positions.jsonl"
            ),
            symbol="EURUSD",
            direction="BUY",
            risk_percent=1.0,
            risk_amount=100.0,
            entry_price=1.1000,
            stop_loss=1.1050,
            take_profit=1.1100,
            open_broker_epoch=1000,
        )
    )

    assert position is None


def test_unsupported_symbol_is_blocked():
    position = (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P1",
            journal_path=(
                "shadow_data/live/test/"
                "UNKNOWN/shadow_positions.jsonl"
            ),
            symbol="UNKNOWN",
            direction="BUY",
            risk_percent=1.0,
            risk_amount=100.0,
            entry_price=100.0,
            stop_loss=90.0,
            take_profit=120.0,
            open_broker_epoch=1000,
        )
    )

    assert position is None


def test_snapshot_sums_risk():
    first = build_valid_buy()
    second = build_valid_sell()

    snapshot = (
        ShadowPortfolioRiskState
        .snapshot(
            positions=(
                first,
                second,
            )
        )
    )

    assert snapshot.valid is True
    assert (
        snapshot.reason
        == "PORTFOLIO_SNAPSHOT_VALID"
    )

    assert (
        snapshot.total_risk_percent
        == pytest.approx(1.25)
    )

    assert (
        snapshot.total_risk_amount
        == pytest.approx(125.0)
    )


def test_snapshot_blocks_duplicate_position_id():
    first = build_valid_buy()

    duplicate = (
        ShadowPortfolioPositionState(
            position_id=first.position_id,
            journal_path=(
                "shadow_data/live/test/"
                "XAUUSD/shadow_positions.jsonl"
            ),
            symbol="XAUUSD",
            direction="SELL",
            risk_percent=0.5,
            risk_amount=50.0,
            asset_class="METALS",
            exposure_tags=(
                "SHORT:XAU",
                "LONG:USD",
            ),
            entry_price=2000.0,
            stop_loss=2010.0,
            take_profit=1980.0,
            open_broker_epoch=2000,
        )
    )

    snapshot = (
        ShadowPortfolioRiskState
        .snapshot(
            positions=(
                first,
                duplicate,
            )
        )
    )

    assert snapshot.valid is False
    assert (
        snapshot.reason
        == "DUPLICATE_POSITION_ID"
    )


def test_snapshot_blocks_duplicate_symbol():
    first = build_valid_buy()

    duplicate_symbol = (
        ShadowPortfolioPositionState(
            position_id="P2",
            journal_path=(
                "shadow_data/live/test/"
                "EURUSD/shadow_positions.jsonl"
            ),
            symbol="EURUSD",
            direction="SELL",
            risk_percent=0.5,
            risk_amount=50.0,
            asset_class="FOREX",
            exposure_tags=(
                "SHORT:EUR",
                "LONG:USD",
            ),
            entry_price=1.1000,
            stop_loss=1.1050,
            take_profit=1.0900,
            open_broker_epoch=2000,
        )
    )

    snapshot = (
        ShadowPortfolioRiskState
        .snapshot(
            positions=(
                first,
                duplicate_symbol,
            )
        )
    )

    assert snapshot.valid is False
    assert (
        snapshot.reason
        == "DUPLICATE_SYMBOL_POSITION"
    )


def test_governor_positions_preserve_risk_and_exposure():
    first = build_valid_buy()
    second = build_valid_sell()

    snapshot = (
        ShadowPortfolioRiskState
        .snapshot(
            positions=(
                first,
                second,
            )
        )
    )

    governor_positions = (
        ShadowPortfolioRiskState
        .governor_positions(
            snapshot
        )
    )

    assert len(governor_positions) == 2

    assert (
        governor_positions[0]
        .risk_percent
        == pytest.approx(0.75)
    )

    assert (
        governor_positions[0]
        .exposure_tags
        ==
        (
            "LONG:EUR",
            "SHORT:USD",
        )
    )

    assert (
        governor_positions[1]
        .asset_class
        == "METALS"
    )


def test_invalid_snapshot_returns_no_governor_positions():
    invalid = (
        ShadowPortfolioRiskState
        .snapshot(
            positions=(
                ShadowPortfolioPositionState(
                    position_id="P1",
                    journal_path=(
                        "shadow_data/live/test/"
                        "EURUSD/shadow_positions.jsonl"
                    ),
                    symbol="EURUSD",
                    direction="BUY",
                    risk_percent=1.0,
                    risk_amount=100.0,
                    asset_class="FOREX",
                    exposure_tags=(
                        "LONG:EUR",
                        "SHORT:USD",
                    ),
                    entry_price=1.1,
                    stop_loss=1.09,
                    take_profit=1.12,
                    open_broker_epoch=1000,
                ),
                ShadowPortfolioPositionState(
                    position_id="P1",
                    journal_path=(
                        "shadow_data/live/test/"
                        "XAUUSD/shadow_positions.jsonl"
                    ),
                    symbol="XAUUSD",
                    direction="SELL",
                    risk_percent=1.0,
                    risk_amount=100.0,
                    asset_class="METALS",
                    exposure_tags=(
                        "SHORT:XAU",
                        "LONG:USD",
                    ),
                    entry_price=2000.0,
                    stop_loss=2010.0,
                    take_profit=1980.0,
                    open_broker_epoch=2000,
                ),
            )
        )
    )

    assert invalid.valid is False

    assert (
        ShadowPortfolioRiskState
        .governor_positions(
            invalid
        )
        == ()
    )



def test_missing_journal_provenance_is_blocked():
    position = (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P3",
            journal_path="",
            symbol="EURUSD",
            direction="BUY",
            risk_percent=1.0,
            risk_amount=100.0,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            open_broker_epoch=3000,
        )
    )

    assert position is None


def test_true_oos_journal_provenance_is_blocked():
    position = (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P4",
            journal_path=(
                "research_data/"
                "sprint92h_true_oos_v2/"
                "shadow_positions.jsonl"
            ),
            symbol="EURUSD",
            direction="BUY",
            risk_percent=1.0,
            risk_amount=100.0,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            open_broker_epoch=4000,
        )
    )

    assert position is None



def test_missing_journal_provenance_is_blocked():
    position = (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P3",
            journal_path="",
            symbol="EURUSD",
            direction="BUY",
            risk_percent=1.0,
            risk_amount=100.0,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            open_broker_epoch=3000,
        )
    )

    assert position is None


def test_true_oos_journal_provenance_is_blocked():
    position = (
        ShadowPortfolioRiskState
        .build_position(
            position_id="P4",
            journal_path=(
                "research_data/"
                "sprint92h_true_oos_v2/"
                "shadow_positions.jsonl"
            ),
            symbol="EURUSD",
            direction="BUY",
            risk_percent=1.0,
            risk_amount=100.0,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            open_broker_epoch=4000,
        )
    )

    assert position is None
