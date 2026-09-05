import json
from pathlib import Path

import pytest

from mss.analysis.four_year_mt5_dataset_freeze import FourYearMT5DatasetFreeze as Freeze


def rate(epoch, close=10.0):
    return {"time": epoch, "open": 10.0, "high": 11.0, "low": 9.0, "close": close,
            "tick_volume": 100, "spread": 2, "real_volume": 50}


def rows(monkeypatch):
    monkeypatch.setattr(Freeze, "WARMUP_CANDLES", 2)
    monkeypatch.setattr(Freeze, "WINDOW_START_EPOCH", 3_600)
    monkeypatch.setattr(Freeze, "WINDOW_END_EXCLUSIVE_EPOCH", 6_300)
    return [rate(epoch) for epoch in (1_800, 2_700, 3_600, 4_500, 5_400)]


def test_numpy_structured_rows_are_supported(monkeypatch):
    numpy = pytest.importorskip("numpy")
    source = rows(monkeypatch)
    array = numpy.array(
        [tuple(item[name] for name in Freeze.RATE_FIELDS) for item in source],
        dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
               ("close", "f8"), ("tick_volume", "i8"), ("spread", "i8"),
               ("real_volume", "i8")],
    )
    selected = Freeze.select_window(array)
    assert [row["performance_eligible"] for row in selected] == [False, False, True, True, True]


def test_exclusive_end_future_and_bad_epochs_fail(monkeypatch):
    source = rows(monkeypatch)
    with pytest.raises(ValueError, match="exclusive end"):
        Freeze.select_window(source + [rate(6_300)])
    bad = list(source)
    bad[1] = rate(1_801)
    with pytest.raises(ValueError, match="M15 aligned"):
        Freeze.select_window(bad)


def test_write_is_deterministic_atomic_and_write_once(monkeypatch, tmp_path):
    source = rows(monkeypatch)
    target = tmp_path / "EURUSD_M15.jsonl"
    result = Freeze.write_symbol(target, source)
    assert result["row_count"] == 5
    assert result["warmup_row_count"] == 2
    assert result["performance_row_count"] == 3
    assert result["gap_count"] == 0
    parsed = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert parsed[2]["time"] == 3_600 and parsed[2]["performance_eligible"] is True
    assert not Path(str(target) + ".tmp").exists()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        Freeze.write_symbol(target, source)


def test_invalid_ohlc_duplicate_and_insufficient_warmup_fail(monkeypatch):
    source = rows(monkeypatch)
    invalid = list(source)
    invalid[2] = {**invalid[2], "high": 9.5}
    with pytest.raises(ValueError, match="high"):
        Freeze.select_window(invalid)
    duplicate = list(source)
    duplicate[2] = {**duplicate[2], "time": duplicate[1]["time"]}
    with pytest.raises(ValueError, match="strictly increasing"):
        Freeze.select_window(duplicate)
    with pytest.raises(ValueError, match="warmup"):
        Freeze.select_window(source[1:])


def test_manifest_requires_exact_core_order():
    symbols = [{"canonical_symbol": canonical} for canonical, _broker, _class in Freeze.UNIVERSE]
    manifest = Freeze.build_manifest(symbols)
    assert manifest["schema_version"] == Freeze.VERSION
    assert manifest["audit"]["strategy_or_replay_run"] is False
    with pytest.raises(ValueError, match="symbol order"):
        Freeze.build_manifest(list(reversed(symbols)))


def test_gaps_are_reported_without_imputation_and_manifest_is_write_once(monkeypatch, tmp_path):
    source = rows(monkeypatch)
    source.pop(3)
    dataset = Freeze.write_symbol(tmp_path / "gap.jsonl", source)
    assert dataset["gap_count"] == 1
    assert dataset["missing_m15_slot_count"] == 1
    symbols = [{"canonical_symbol": canonical} for canonical, _broker, _class in Freeze.UNIVERSE]
    target = tmp_path / "manifest.json"
    digest = Freeze.write_manifest(target, symbols)
    assert len(digest) == 64
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        Freeze.write_manifest(target, symbols)


def test_acquisition_ranges_are_contiguous_utc_and_end_exclusive(monkeypatch):
    monkeypatch.setattr(Freeze, "WINDOW_START_EPOCH", 1_630_454_400)
    monkeypatch.setattr(Freeze, "WINDOW_END_EXCLUSIVE_EPOCH", 1_756_684_800)
    ranges = Freeze.acquisition_ranges(lookback_days=45, chunk_days=180)
    assert ranges[0][0].tzinfo is not None
    assert int(ranges[0][0].timestamp()) == Freeze.WINDOW_START_EPOCH - 45 * 86_400
    assert int(ranges[-1][1].timestamp()) == Freeze.WINDOW_END_EXCLUSIVE_EPOCH - 1
    assert all(left[1].timestamp() + 1 == right[0].timestamp() for left, right in zip(ranges, ranges[1:]))
    assert all((end - start).days < 180 for start, end in ranges)
    with pytest.raises(ValueError, match="positive"):
        Freeze.acquisition_ranges(chunk_days=0)
