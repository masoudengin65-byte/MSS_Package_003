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


def test_global_safety_block_counter_exists_in_per_symbol_stats():
    text = source_text()

    start = text.index(
        "def new_stats():"
    )

    end = text.index(
        "\ndef evaluate_signal_snapshot",
        start,
    )

    segment = text[
        start:end
    ]

    assert (
        '"global_safety_blocks": 0'
        in segment
    )


def test_global_safety_block_counter_exists_in_global_stats():
    text = source_text()

    start = text.index(
        "global_stats = {"
    )

    end = text.index(
        "\n\n    initialized = False",
        start,
    )

    segment = text[
        start:end
    ]

    assert (
        '"global_safety_blocks": 0'
        in segment
    )


def test_global_safety_counter_is_consumed_by_runtime_paths():
    text = source_text()

    assert (
        text.count(
            '"global_safety_blocks"'
        )
        >= 5
    )
