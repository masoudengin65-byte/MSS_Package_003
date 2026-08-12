import json
from datetime import datetime, timezone
from pathlib import Path

from mss.analysis.sealed_oos_accrual_monitor import SealedOosAccrualMonitor


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def test_boundary_and_current_bar_are_excluded_correctly(monkeypatch):
    monkeypatch.setattr(SealedOosAccrualMonitor, "TARGET", 3)
    result = SealedOosAccrualMonitor.inspect_symbol(
        "EURUSD", "EURUSD", "FOREX", iso(1_000), [100, 1_000, 1_900, 2_800, 3_700], 3_700,
    )
    assert result["completed_timestamp_count"] == 3
    assert result["gate_met"] is True
    assert result["first_eligible_open_timestamp"] == iso(1_000)
    assert result["last_completed_open_timestamp"] == iso(2_800)


def test_duplicate_timestamps_are_reported_and_deduplicated():
    result = SealedOosAccrualMonitor.inspect_symbol(
        "USDJPY", "USDJPY", "FOREX", iso(1_000), [1_000, 1_900, 1_900], 3_000,
    )
    assert result["completed_timestamp_count"] == 2
    assert result["quality"]["duplicate_timestamp_count"] == 1


def test_global_gate_requires_all_eight_and_quality(monkeypatch):
    monkeypatch.setattr(SealedOosAccrualMonitor, "TARGET", 1)
    rows = [SealedOosAccrualMonitor.inspect_symbol(str(i), str(i), "X", iso(1_000), [1_000], 2_000) for i in range(8)]
    result = SealedOosAccrualMonitor.build(rows, "a" * 64)
    assert result["global_gate"]["authoritative_replay_allowed"] is True
    assert result["privacy_and_seal_contract"]["ohlc_fields_persisted"] is False


def test_incomplete_gate_explicitly_prohibits_replay(monkeypatch):
    monkeypatch.setattr(SealedOosAccrualMonitor, "TARGET", 2)
    rows = [SealedOosAccrualMonitor.inspect_symbol(str(i), str(i), "X", iso(1_000), [1_000], 2_000) for i in range(8)]
    result = SealedOosAccrualMonitor.build(rows, "a" * 64)
    assert result["global_gate"]["status"] == "ACCRUING_REPLAY_PROHIBITED"
    assert result["global_gate"]["authoritative_replay_allowed"] is False


def test_completed_artifact_contains_no_price_or_outcome_fields():
    path = Path(__file__).resolve().parents[1] / "reports" / "MSS_Sprint92D1_Sealed_OOS_Accrual_Monitor.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == SealedOosAccrualMonitor.VERSION
    assert data["global_gate"]["status"] == "ACCRUING_REPLAY_PROHIBITED"
    assert data["global_gate"]["authoritative_replay_allowed"] is False
    assert len(data["symbols"]) == 8
    contract = data["privacy_and_seal_contract"]
    assert contract["ohlc_fields_persisted"] is False
    assert contract["strategy_replay_run"] is False
    assert contract["pnl_or_performance_computed"] is False
    serialized = json.dumps(data).lower()
    for forbidden in ('"open":', '"high":', '"low":', '"close":', '"profit":', '"pnl":', '"trade":'):
        assert forbidden not in serialized
