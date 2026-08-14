from mss.analysis.multi_symbol_candidate_arbitrator import (
    DeterministicCandidateArbitrator,
    ShadowEntryCandidate,
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


def test_selects_first_eligible_by_frozen_priority():
    candidates = (
        ShadowEntryCandidate(
            symbol="ETHEREUM",
            eligible=True,
        ),
        ShadowEntryCandidate(
            symbol="GBPUSD",
            eligible=True,
        ),
        ShadowEntryCandidate(
            symbol="XAUUSD",
            eligible=True,
        ),
    )

    result = (
        DeterministicCandidateArbitrator.select(
            candidates=candidates,
            symbol_priority=PRIORITY,
        )
    )

    assert result.allowed is True
    assert result.selected_symbol == "GBPUSD"
    assert result.eligible_symbols == (
        "GBPUSD",
        "XAUUSD",
        "ETHEREUM",
    )


def test_input_order_does_not_change_selection():
    first = (
        ShadowEntryCandidate(
            "ETHEREUM",
            True,
        ),
        ShadowEntryCandidate(
            "EURUSD",
            True,
        ),
    )

    second = tuple(
        reversed(first)
    )

    result_a = (
        DeterministicCandidateArbitrator.select(
            candidates=first,
            symbol_priority=PRIORITY,
        )
    )

    result_b = (
        DeterministicCandidateArbitrator.select(
            candidates=second,
            symbol_priority=PRIORITY,
        )
    )

    assert (
        result_a.selected_symbol
        == result_b.selected_symbol
        == "EURUSD"
    )


def test_blocks_unknown_eligible_symbol():
    result = (
        DeterministicCandidateArbitrator.select(
            candidates=(
                ShadowEntryCandidate(
                    "UNKNOWN",
                    True,
                ),
            ),
            symbol_priority=PRIORITY,
        )
    )

    assert result.allowed is False
    assert (
        result.reason
        == "ELIGIBLE_SYMBOL_NOT_IN_PRIORITY"
    )


def test_blocks_duplicate_candidate_symbol():
    result = (
        DeterministicCandidateArbitrator.select(
            candidates=(
                ShadowEntryCandidate(
                    "EURUSD",
                    True,
                ),
                ShadowEntryCandidate(
                    "EURUSD",
                    True,
                ),
            ),
            symbol_priority=PRIORITY,
        )
    )

    assert result.allowed is False
    assert (
        result.reason
        == "DUPLICATE_CANDIDATE_SYMBOL"
    )


def test_no_eligible_candidate_is_safe_no_trade():
    result = (
        DeterministicCandidateArbitrator.select(
            candidates=(
                ShadowEntryCandidate(
                    "EURUSD",
                    False,
                    "NO_BOS",
                ),
                ShadowEntryCandidate(
                    "ETHEREUM",
                    False,
                    "NO_BOS",
                ),
            ),
            symbol_priority=PRIORITY,
        )
    )

    assert result.allowed is False
    assert result.selected_symbol is None
    assert result.reason == "NO_ELIGIBLE_CANDIDATE"


def test_duplicate_priority_fails_safe():
    result = (
        DeterministicCandidateArbitrator.select(
            candidates=(
                ShadowEntryCandidate(
                    "EURUSD",
                    True,
                ),
            ),
            symbol_priority=(
                "EURUSD",
                "EURUSD",
            ),
        )
    )

    assert result.allowed is False
    assert result.reason == "DUPLICATE_SYMBOL_PRIORITY"
