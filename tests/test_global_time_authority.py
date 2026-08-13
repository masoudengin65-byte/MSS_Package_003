from mss.analysis.global_time_authority import (
    GlobalTimeAuthority,
)


def build(
    offset_seconds,
    previous=None,
):
    authority = GlobalTimeAuthority()

    true_utc = 2_000_000_000

    tick_epoch = (
        true_utc
        + offset_seconds
    )

    bar_epoch = (
        tick_epoch // 900
    ) * 900

    return authority.build(
        utc_epoch_before_tick=(
            true_utc - 1
        ),
        utc_epoch_after_tick=(
            true_utc + 1
        ),
        tick_epoch=tick_epoch,
        current_bar_epoch=bar_epoch,
        previous_broker_offset_seconds=previous,
    )


def test_h132_detects_positive_broker_offset():
    result = build(3 * 3600)

    assert (
        result["observation"]
        ["detected_broker_offset_seconds"]
        == 10800
    )

    assert (
        result["observation"]
        ["detected_broker_offset_label"]
        == "UTC+03:00"
    )

    assert (
        result["time_authority"]
        ["confirmed"]
        is True
    )


def test_h132_detects_negative_broker_offset():
    result = build(-5 * 3600)

    assert (
        result["observation"]
        ["detected_broker_offset_seconds"]
        == -18000
    )

    assert (
        result["observation"]
        ["detected_broker_offset_label"]
        == "UTC-05:00"
    )

    assert (
        result["time_authority"]
        ["confirmed"]
        is True
    )


def test_h132_supports_half_hour_offset():
    result = build(
        5 * 3600 + 30 * 60
    )

    assert (
        result["observation"]
        ["detected_broker_offset_seconds"]
        == 19800
    )

    assert (
        result["observation"]
        ["detected_broker_offset_label"]
        == "UTC+05:30"
    )


def test_h132_detects_normal_dst_change():
    result = build(
        3 * 3600,
        previous=2 * 3600,
    )

    monitor = result[
        "offset_change_monitor"
    ]

    assert monitor["offset_changed"] is True

    assert (
        monitor["offset_change_seconds"]
        == 3600
    )

    assert (
        monitor["classification"]
        == "NORMAL_SEASONAL_OR_DST_CHANGE"
    )

    assert (
        result["time_authority"]
        ["confirmed"]
        is True
    )


def test_h132_blocks_nonstandard_offset_change():
    result = build(
        5 * 3600,
        previous=2 * 3600,
    )

    assert (
        result["offset_change_monitor"]
        ["classification"]
        == "NONSTANDARD_OFFSET_CHANGE"
    )

    assert (
        result["time_authority"]
        ["status"]
        == "BROKER_OFFSET_CHANGE_REQUIRES_REVIEW"
    )

    assert (
        result["fail_safe"]
        ["trading_allowed_by_time_authority"]
        is False
    )


def test_h132_has_no_hardcoded_environment():
    result = build(0)

    authority = result[
        "time_authority"
    ]

    assert (
        authority["hardcoded_broker_offset"]
        is False
    )

    assert (
        authority["hardcoded_system_timezone"]
        is False
    )

    assert (
        authority["hardcoded_broker_identity"]
        is False
    )

    assert (
        result["portability"]
        ["broker_agnostic"]
        is True
    )

    assert (
        result["portability"]
        ["country_agnostic"]
        is True
    )
