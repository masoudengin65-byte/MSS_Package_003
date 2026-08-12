import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mss.analysis.extended_dataset_freeze import ExtendedDatasetFreeze


def rate(timestamp, close=11.0):
    return {"time": timestamp, "open": 10.0, "high": 12.0, "low": 9.0, "close": close,
            "tick_volume": 100, "spread": 2, "real_volume": 50}


def source_window(first, last_close):
    iso = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")
    return {"canonical_symbol": "BTCUSD", "broker_symbol": "BITCOIN", "asset_class": "CRYPTO",
            "first_candle_open_time": iso(first), "last_candle_close_time": iso(last_close)}


@pytest.fixture
def frozen_rates(monkeypatch):
    monkeypatch.setattr(ExtendedDatasetFreeze, "DATASET_CANDLES", 10)
    monkeypatch.setattr(ExtendedDatasetFreeze, "DEVELOPMENT_CANDLES", 4)
    monkeypatch.setattr(ExtendedDatasetFreeze, "VALIDATION_CANDLES", 2)
    return [rate(1_000 + index * 900) for index in range(10)]


def test_partition_is_chronological_complete_and_oos_is_not_analyzed(frozen_rates):
    result = ExtendedDatasetFreeze.freeze_symbol(
        frozen_rates, source_window(frozen_rates[6]["time"], frozen_rates[8]["time"]), 20_000,
    )
    counts = {row["slice"]: row["candle_count"] for row in result["slices"]}
    assert counts == {"DEVELOPMENT": 4, "VALIDATION": 2,
                      "RESEARCH_EXPOSED_QUARANTINE": 2, "TRUE_OOS_ACCRUAL": 2}
    assert result["slices"][-1]["analysis_access"] == "FROZEN_NO_ANALYSIS"
    assert result["partition_reconciliation"] == {
        "slice_candle_sum": 10, "equals_frozen_dataset": True,
        "no_overlap": True, "chronological": True,
    }


def test_candle_at_v2_close_boundary_belongs_to_true_oos(frozen_rates):
    boundary = frozen_rates[8]["time"]
    result = ExtendedDatasetFreeze.freeze_symbol(
        frozen_rates, source_window(frozen_rates[6]["time"], boundary), 20_000,
    )
    oos = next(row for row in result["slices"] if row["slice"] == "TRUE_OOS_ACCRUAL")
    assert oos["first_candle_open_timestamp"] == ExtendedDatasetFreeze._slice_manifest(
        "x", frozen_rates[8:], "x"
    )["first_candle_open_timestamp"]


def test_hashes_are_deterministic_and_content_sensitive(frozen_rates):
    window = source_window(frozen_rates[6]["time"], frozen_rates[8]["time"])
    first = ExtendedDatasetFreeze.freeze_symbol(frozen_rates, window, 20_000)
    second = ExtendedDatasetFreeze.freeze_symbol(copy.deepcopy(frozen_rates), window, 20_000)
    assert first["full_dataset_sha256"] == second["full_dataset_sha256"]
    changed = copy.deepcopy(frozen_rates)
    changed[0]["close"] += 0.1
    assert ExtendedDatasetFreeze.freeze_symbol(changed, window, 20_000)["full_dataset_sha256"] != first["full_dataset_sha256"]


def test_wrong_count_and_duplicate_timestamp_are_rejected(frozen_rates):
    window = source_window(frozen_rates[6]["time"], frozen_rates[8]["time"])
    with pytest.raises(ValueError, match="exactly"):
        ExtendedDatasetFreeze.freeze_symbol(frozen_rates[:-1], window, 20_000)
    duplicated = copy.deepcopy(frozen_rates)
    duplicated[1]["time"] = duplicated[0]["time"]
    with pytest.raises(ValueError, match="strictly increasing"):
        ExtendedDatasetFreeze.freeze_symbol(duplicated, window, 20_000)


def test_pre_exposure_remainder_is_rejected(frozen_rates):
    window = source_window(frozen_rates[7]["time"], frozen_rates[9]["time"] + 900)
    with pytest.raises(ValueError, match="pre-exposure"):
        ExtendedDatasetFreeze.freeze_symbol(frozen_rates, window, 20_000)


def test_frozen_manifest_acceptance_and_oos_quarantine():
    path = Path(__file__).resolve().parents[1] / "reports" / "MSS_Sprint92C2_Extended_Dataset_Manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "MSS_SPRINT92C2_EXTENDED_DATASET_MANIFEST_V1"
    assert data["acceptance"] == {
        "all_c1_stable": True,
        "all_fixed_50000": True,
        "all_frozen_hashes_match_c1": True,
        "all_partitions_reconcile": True,
        "performance_metrics_computed": False,
        "strategy_or_replay_run": False,
        "symbol_count": 8,
        "trading_operations_performed": 0,
        "true_oos_never_analyzed": True,
    }
    assert all(row["matches_c1_50000_sha256"] for row in data["symbols"])
    assert all(sum(item["candle_count"] for item in row["slices"]) == 50_000 for row in data["symbols"])
    assert all(
        next(item for item in row["slices"] if item["slice"] == "TRUE_OOS_ACCRUAL")["analysis_access"]
        == "FROZEN_NO_ANALYSIS"
        for row in data["symbols"]
    )
