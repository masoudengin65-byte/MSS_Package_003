from pathlib import Path
import hashlib


ROOT = Path(__file__).resolve().parents[1]

RUNNER = (
    ROOT
    / "integration_tests"
    / "run_sprint92h14_6_long_running_shadow_live_session.py"
)

SOURCE = (
    ROOT
    / "shadow_data"
    / "live"
    / "sprint92h14_5c"
    / "GBPUSD"
    / "shadow_positions.jsonl"
)

TARGET = (
    ROOT
    / "shadow_data"
    / "live"
    / "sprint92h14_6"
    / "GBPUSD"
    / "shadow_positions.jsonl"
)


EXPECTED_SOURCE_SHA256 = (
    "1954c6fa4e179ec0ea0548eb605172a3b5db07c55234868b10f6b94ed09ee720"
)

EXPECTED_TARGET_SHA256 = (
    "12ce1ca0e80fbdf52e4feca1e17106043e3500a76520d8dae68debc5fb8ff06e"
)

EXPECTED_POSITION_ID = (
    "SHADOW-GBPUSD-1786716000"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def runner_source() -> str:
    return RUNNER.read_text(
        encoding="utf-8"
    )


def test_h14_6_runner_uses_own_current_namespace():
    source = runner_source()

    assert (
        '/ "sprint92h14_6"'
        in source
    )


def test_h14_6_predecessor_is_h14_5c():
    source = runner_source()

    assert (
        '/ "sprint92h14_5c"'
        in source
    )

    assert (
        "PREDECESSOR_H14_5C"
        in source
    )


def test_h14_6_does_not_use_h14_5b_1_as_predecessor():
    source = runner_source()

    assert (
        "sprint92h14_5b_1"
        not in source
    )

    assert (
        "PREDECESSOR_H14_5B_1"
        not in source
    )


def test_h14_6_report_identity_is_correct():
    source = runner_source()

    assert (
        '"92H.14.6"'
        in source
    )

    assert (
        '"MSS_Sprint92H14_6_"'
        in source
    )


def test_h14_6_has_exactly_one_shadow_open_trade_call():
    source = runner_source()

    assert (
        source.count(
            ".open_trade("
        )
        == 1
    )


def test_h14_6_has_no_direct_real_order_send():
    source = runner_source()

    assert (
        "mt5.order_send("
        not in source
    )


def test_h14_6_has_no_direct_order_check():
    source = runner_source()

    assert (
        "mt5.order_check("
        not in source
    )


def test_h14_5c_predecessor_journal_hash_is_frozen():
    assert SOURCE.is_file()

    assert (
        sha256(SOURCE)
        ==
        EXPECTED_SOURCE_SHA256
    )


def test_h14_6_target_journal_hash_is_frozen_at_migration_evidence():
    assert TARGET.is_file()

    assert (
        sha256(TARGET)
        ==
        EXPECTED_TARGET_SHA256
    )


def test_h14_6_target_contains_expected_position_identity():
    text = TARGET.read_text(
        encoding="utf-8"
    )

    assert (
        EXPECTED_POSITION_ID
        in text
    )


def test_h14_6_target_contains_h14_5c_continuity_evidence():
    text = TARGET.read_text(
        encoding="utf-8"
    )

    assert (
        "6604ff4b9408e24d100955f593bd6b75"
        "aad632d6b124bea74f9ef2882a15fe2d"
        in text
    )


def test_true_oos_path_is_not_referenced_by_h14_6_runner():
    source = runner_source()

    assert (
        "sprint92h_true_oos_v2"
        not in source
    )
