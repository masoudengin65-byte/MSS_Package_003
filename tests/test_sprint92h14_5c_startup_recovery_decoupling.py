from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RUNNER = (
    ROOT
    / "integration_tests"
    / "run_sprint92h14_5c_shadow_live_safety_governor_session.py"
)


def source_text():
    return RUNNER.read_text(
        encoding="utf-8"
    )


def startup_segment():
    text = source_text()

    start = text.index(
        "# H14.5c STARTUP LIFECYCLE CONTINUITY."
    )

    end = text.index(
        'if (\n'
        '            global_stats[\n'
        '                "symbols_enabled"\n',
        start,
    )

    return text[start:end]


def test_startup_recovery_occurs_before_feed_disabled_skip():
    segment = startup_segment()

    recovery_index = segment.index(
        "ShadowPositionRecovery"
    )

    disabled_index = segment.index(
        'if state[\n'
        '                "disabled_reason"\n'
        '            ]:'
    )

    assert (
        recovery_index
        <
        disabled_index
    )


def test_open_position_is_collected_before_feed_disabled_skip():
    segment = startup_segment()

    append_index = segment.index(
        "recovered.append("
    )

    disabled_index = segment.index(
        'if state[\n'
        '                "disabled_reason"\n'
        '            ]:'
    )

    assert (
        append_index
        <
        disabled_index
    )


def test_feed_disabled_symbol_is_not_forced_enabled():
    segment = startup_segment()

    disabled_index = segment.index(
        'if state[\n'
        '                "disabled_reason"\n'
        '            ]:'
    )

    enabled_index = segment.index(
        'state[\n'
        '                    "enabled"\n'
        '                ] = True'
    )

    assert (
        disabled_index
        <
        enabled_index
    )

    between = segment[
        disabled_index:enabled_index
    ]

    assert "continue" in between


def test_startup_contract_documents_recovery_feed_separation():
    segment = startup_segment()

    assert (
        "Journal recovery is independent from"
        in segment
    )

    assert (
        "Feed/entry eligibility remains separate."
        in segment
    )

    assert (
        "unsafe for NEW entries"
        in segment
    )
