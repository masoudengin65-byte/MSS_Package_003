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


def test_h14_5c_current_and_predecessor_namespaces_are_distinct():
    text = source_text()

    assert (
        '/ "sprint92h14_5c"'
        in text
    )

    assert (
        '/ "sprint92h14_5b_1"'
        in text
    )


def test_consumption_target_is_h14_5c():
    text = source_text()

    marker = (
        "current_consumption_journal_path = ("
    )

    start = text.index(
        marker
    )

    end = text.index(
        "predecessor_consumption_result = (",
        start,
    )

    segment = text[
        start:end
    ]

    assert (
        '/ "sprint92h14_5c"'
        in segment
    )

    assert (
        '/ "sprint92h14_5b_1"'
        not in segment
    )


def test_predecessor_helper_points_to_h14_5b_1():
    text = source_text()

    start = text.index(
        "def predecessor_journal_path_for("
    )

    end = text.index(
        "\ndef ",
        start + 1,
    )

    segment = text[
        start:end
    ]

    assert (
        '/ "sprint92h14_5b_1"'
        in segment
    )

    assert (
        '/ "sprint92h14_5c"'
        not in segment
    )


def test_no_h14_5a_predecessor_labels_remain():
    text = source_text()

    assert (
        "PREDECESSOR_H14_5A"
        not in text
    )

    assert (
        "sprint92h14_5a"
        not in text
    )
