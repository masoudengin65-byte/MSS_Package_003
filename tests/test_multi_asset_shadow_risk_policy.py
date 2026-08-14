from mss.analysis.multi_asset_shadow_risk_policy import (
    MultiAssetShadowRiskPolicy,
    ShadowRiskCandidateInput,
)
from mss.analysis.portfolio_risk_governor import (
    PortfolioPosition,
)


PRIORITY = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "XAUUSD",
    "XAGUSD",
    "WTI",
    "BITCOIN",
    "ETHEREUM",
)


def candidate(
    symbol,
    direction="BUY",
    *,
    bid=100.0,
    ask=100.1,
    entry=100.0,
    stop=99.0,
    risk=1.0,
):
    return ShadowRiskCandidateInput(
        symbol=symbol,
        direction=direction,
        bid=bid,
        ask=ask,
        entry_price=entry,
        stop_loss=stop,
        symbol_tradable=True,
        quote_fresh=True,
        risk_percent=risk,
    )


def test_policy_selects_by_priority_not_input_order():
    result = MultiAssetShadowRiskPolicy.evaluate(
        candidates=(
            candidate(
                "ETHEREUM",
            ),
            candidate(
                "XAUUSD",
            ),
            candidate(
                "EURUSD",
            ),
        ),
        open_positions=(),
        symbol_priority=PRIORITY,
    )

    assert result.allowed is True
    assert result.selected_symbol == "EURUSD"


def test_policy_blocks_high_spread_candidate():
    result = MultiAssetShadowRiskPolicy.evaluate(
        candidates=(
            candidate(
                "EURUSD",
                bid=100.0,
                ask=100.5,
                entry=100.0,
                stop=99.0,
            ),
        ),
        open_positions=(),
        symbol_priority=PRIORITY,
    )

    assert result.allowed is False
    assert result.selected_symbol is None

    assert (
        result.evaluations[0].reason
        == "SPREAD_TO_STOP_RATIO_TOO_HIGH"
    )


def test_policy_fails_safe_unknown_instrument():
    result = MultiAssetShadowRiskPolicy.evaluate(
        candidates=(
            candidate(
                "UNKNOWN",
            ),
        ),
        open_positions=(),
        symbol_priority=PRIORITY,
    )

    assert result.allowed is False

    assert (
        result.evaluations[0].reason
        == "UNSUPPORTED_INSTRUMENT_OR_DIRECTION"
    )


def test_policy_blocks_directional_concentration():
    positions = (
        PortfolioPosition(
            symbol="EURUSD",
            asset_class="FOREX",
            risk_percent=0.5,
            exposure_tags=(
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
    )

    result = MultiAssetShadowRiskPolicy.evaluate(
        candidates=(
            candidate(
                "XAUUSD",
                direction="BUY",
                risk=0.5,
            ),
        ),
        open_positions=positions,
        symbol_priority=PRIORITY,
    )

    assert result.allowed is False

    assert (
        result.evaluations[0].reason
        == "DIRECTIONAL_EXPOSURE_CONCENTRATION"
    )


def test_policy_allows_opposite_usd_exposure():
    positions = (
        PortfolioPosition(
            symbol="EURUSD",
            asset_class="FOREX",
            risk_percent=0.5,
            exposure_tags=(
                "LONG:EUR",
                "SHORT:USD",
            ),
        ),
    )

    result = MultiAssetShadowRiskPolicy.evaluate(
        candidates=(
            candidate(
                "XAUUSD",
                direction="SELL",
                risk=0.5,
            ),
        ),
        open_positions=positions,
        symbol_priority=PRIORITY,
    )

    assert result.allowed is True
    assert result.selected_symbol == "XAUUSD"


def test_policy_is_input_order_independent():
    candidates_a = (
        candidate(
            "ETHEREUM",
        ),
        candidate(
            "GBPUSD",
        ),
    )

    candidates_b = tuple(
        reversed(
            candidates_a
        )
    )

    result_a = MultiAssetShadowRiskPolicy.evaluate(
        candidates=candidates_a,
        open_positions=(),
        symbol_priority=PRIORITY,
    )

    result_b = MultiAssetShadowRiskPolicy.evaluate(
        candidates=candidates_b,
        open_positions=(),
        symbol_priority=PRIORITY,
    )

    assert (
        result_a.selected_symbol
        == result_b.selected_symbol
        == "GBPUSD"
    )
