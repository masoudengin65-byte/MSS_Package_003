from mss.analysis.shadow_portfolio_continuity_policy import (
    ShadowPortfolioContinuityPolicy,
)
from mss.analysis.shadow_portfolio_risk_state import (
    ShadowPortfolioPositionState,
    ShadowPortfolioRiskState,
    ShadowPortfolioSnapshot,
)


def make_position(
    *,
    position_id="P1",
    symbol="GBPUSD",
    direction="BUY",
    journal_namespace="current",
    risk_percent=1.0,
    risk_amount=5.0,
    open_broker_epoch=1000,
):
    if symbol == "GBPUSD":
        if direction == "BUY":
            entry = 1.3500
            stop = 1.3450
            take = 1.3600
        else:
            entry = 1.3500
            stop = 1.3550
            take = 1.3400

    elif symbol == "XAUUSD":
        if direction == "BUY":
            entry = 2000.0
            stop = 1990.0
            take = 2020.0
        else:
            entry = 2000.0
            stop = 2010.0
            take = 1980.0

    else:
        raise RuntimeError(
            "UNSUPPORTED_TEST_SYMBOL"
        )

    position = (
        ShadowPortfolioRiskState
        .build_position(
            position_id=position_id,
            journal_path=(
                f"shadow_data/live/"
                f"{journal_namespace}/"
                f"{symbol}/"
                "shadow_positions.jsonl"
            ),
            symbol=symbol,
            direction=direction,
            risk_percent=risk_percent,
            risk_amount=risk_amount,
            entry_price=entry,
            stop_loss=stop,
            take_profit=take,
            open_broker_epoch=(
                open_broker_epoch
            ),
        )
    )

    assert position is not None

    return position


def snapshot(*positions):
    result = (
        ShadowPortfolioRiskState
        .snapshot(
            positions=positions
        )
    )

    assert result.valid is True

    return result


def test_empty_current_and_predecessor_are_clear():
    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(),
            predecessor_snapshot=snapshot(),
        )
    )

    assert result.valid is True
    assert result.action == "CONTINUE"
    assert result.reason == "CONTINUITY_CLEAR"

    assert result.current_position_count == 0
    assert result.predecessor_position_count == 0


def test_predecessor_only_requires_import():
    predecessor = make_position(
        journal_namespace="predecessor",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(),
            predecessor_snapshot=snapshot(
                predecessor
            ),
        )
    )

    assert result.valid is True

    assert (
        result.action
        == "IMPORT_REQUIRED"
    )

    assert (
        result.reason
        ==
        "PREDECESSOR_POSITION_IMPORT_REQUIRED"
    )

    assert result.position_id == "P1"
    assert result.symbol == "GBPUSD"

    assert result.current_position_count == 0
    assert result.predecessor_position_count == 1


def test_current_only_continues():
    current = make_position(
        journal_namespace="current",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(
                current
            ),
            predecessor_snapshot=snapshot(),
        )
    )

    assert result.valid is True
    assert result.action == "CONTINUE"

    assert (
        result.reason
        ==
        "CURRENT_POSITION_ACTIVE"
    )

    assert result.position_id == "P1"
    assert result.symbol == "GBPUSD"


def test_identical_position_in_both_namespaces_continues():
    current = make_position(
        journal_namespace="current",
    )

    predecessor = make_position(
        journal_namespace="predecessor",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(
                current
            ),
            predecessor_snapshot=snapshot(
                predecessor
            ),
        )
    )

    assert result.valid is True
    assert result.action == "CONTINUE"

    assert (
        result.reason
        ==
        "CURRENT_SUPERSEDES_PREDECESSOR"
    )

    assert result.position_id == "P1"
    assert result.symbol == "GBPUSD"


def test_different_positions_conflict():
    current = make_position(
        position_id="CURRENT-1",
        journal_namespace="current",
    )

    predecessor = make_position(
        position_id="LEGACY-1",
        journal_namespace="predecessor",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(
                current
            ),
            predecessor_snapshot=snapshot(
                predecessor
            ),
        )
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "CURRENT_PREDECESSOR_POSITION_CONFLICT"
    )


def test_same_id_but_different_direction_conflicts():
    current = make_position(
        position_id="P1",
        direction="SELL",
        journal_namespace="current",
    )

    predecessor = make_position(
        position_id="P1",
        direction="BUY",
        journal_namespace="predecessor",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(
                current
            ),
            predecessor_snapshot=snapshot(
                predecessor
            ),
        )
    )

    assert result.valid is False

    assert (
        result.reason
        ==
        "CURRENT_PREDECESSOR_POSITION_CONFLICT"
    )


def test_multiple_current_positions_fail_safe():
    first = make_position(
        position_id="GBP-1",
        symbol="GBPUSD",
        journal_namespace="current",
    )

    second = make_position(
        position_id="XAU-1",
        symbol="XAUUSD",
        direction="SELL",
        journal_namespace="current",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(
                first,
                second,
            ),
            predecessor_snapshot=snapshot(),
        )
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "MULTIPLE_CURRENT_POSITIONS_NOT_ALLOWED"
    )

    assert result.current_position_count == 2


def test_multiple_predecessor_positions_fail_safe():
    first = make_position(
        position_id="GBP-1",
        symbol="GBPUSD",
        journal_namespace="predecessor",
    )

    second = make_position(
        position_id="XAU-1",
        symbol="XAUUSD",
        direction="SELL",
        journal_namespace="predecessor",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(),
            predecessor_snapshot=snapshot(
                first,
                second,
            ),
        )
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "MULTIPLE_PREDECESSOR_POSITIONS_NOT_ALLOWED"
    )

    assert result.predecessor_position_count == 2


def test_invalid_current_snapshot_fails_safe():
    invalid = ShadowPortfolioSnapshot(
        valid=False,
        reason="TEST_INVALID",
        positions=(),
        total_risk_percent=0.0,
        total_risk_amount=0.0,
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=invalid,
            predecessor_snapshot=snapshot(),
        )
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "CURRENT_SNAPSHOT_INVALID"
    )


def test_invalid_predecessor_snapshot_fails_safe():
    invalid = ShadowPortfolioSnapshot(
        valid=False,
        reason="TEST_INVALID",
        positions=(),
        total_risk_percent=0.0,
        total_risk_amount=0.0,
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(),
            predecessor_snapshot=invalid,
        )
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "PREDECESSOR_SNAPSHOT_INVALID"
    )


def test_consumed_predecessor_only_continues_without_reimport():
    predecessor = make_position(
        journal_namespace="predecessor",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(),
            predecessor_snapshot=snapshot(
                predecessor
            ),
            predecessor_consumed=True,
        )
    )

    assert result.valid is True
    assert result.action == "CONTINUE"

    assert (
        result.reason
        ==
        "PREDECESSOR_POSITION_ALREADY_CONSUMED"
    )

    assert result.position_id == "P1"
    assert result.symbol == "GBPUSD"

    assert result.current_position_count == 0
    assert result.predecessor_position_count == 1


def test_explicit_unconsumed_predecessor_still_requires_import():
    predecessor = make_position(
        journal_namespace="predecessor",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(),
            predecessor_snapshot=snapshot(
                predecessor
            ),
            predecessor_consumed=False,
        )
    )

    assert result.valid is True

    assert (
        result.action
        == "IMPORT_REQUIRED"
    )

    assert (
        result.reason
        ==
        "PREDECESSOR_POSITION_IMPORT_REQUIRED"
    )


def test_consumed_flag_never_overrides_position_conflict():
    current = make_position(
        position_id="CURRENT-1",
        journal_namespace="current",
    )

    predecessor = make_position(
        position_id="LEGACY-1",
        journal_namespace="predecessor",
    )

    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(
                current
            ),
            predecessor_snapshot=snapshot(
                predecessor
            ),
            predecessor_consumed=True,
        )
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "CURRENT_PREDECESSOR_POSITION_CONFLICT"
    )


def test_invalid_consumption_flag_fails_safe():
    result = (
        ShadowPortfolioContinuityPolicy
        .evaluate(
            current_snapshot=snapshot(),
            predecessor_snapshot=snapshot(),
            predecessor_consumed="yes",
        )
    )

    assert result.valid is False
    assert result.action == "BLOCK"

    assert (
        result.reason
        ==
        "INVALID_PREDECESSOR_CONSUMPTION_FLAG"
    )
