from __future__ import annotations

import gc
import json
from pathlib import Path
import tracemalloc

import pytest

from mss.analysis import sprint93_paired_forward_activation as A
from mss.analysis.indexed_shadow_trade_journal import IndexedShadowTradeJournal
from mss.analysis.shadow_trade_journal import ShadowTradeJournal
from test_sprint93_2b_boundary_runner import START, TARGET, activation, lifecycle_end_snapshot, utc


@pytest.fixture(autouse=True)
def stable_clock(monkeypatch):
    monkeypatch.setattr(A, "_utc_now_epoch", lambda: TARGET + .05)


def append(backend, path, sequence):
    return backend.append_event(
        path=path, event_type="SYNTHETIC_EVENT", position_id=f"position-{sequence}",
        broker_epoch=TARGET + sequence,
        payload={"sequence": sequence, "unicode": "آزمون", "nested": {"safe": True}},
    )


def test_indexed_append_is_byte_identical_to_frozen_journal(tmp_path):
    frozen_path, indexed_path = tmp_path / "frozen.jsonl", tmp_path / "indexed.jsonl"
    indexed = IndexedShadowTradeJournal(indexed_path)
    for sequence in range(4):
        append(ShadowTradeJournal, frozen_path, sequence)
        append(indexed, indexed_path, sequence)
    assert frozen_path.read_bytes() == indexed_path.read_bytes()
    assert indexed.full_verify() == ShadowTradeJournal.verify(indexed_path)


def test_pre_write_failure_appends_neither_jsonl_nor_index_row(tmp_path):
    path = tmp_path / "paired.jsonl"
    indexed = IndexedShadowTradeJournal(path)
    with indexed.exclusive_transaction(path):
        with pytest.raises(RuntimeError, match="synthetic deadline"):
            indexed._append_event_unlocked(
                path=path, event_type="EVENT", position_id="id", broker_epoch=1,
                payload={}, pre_write_check=lambda: (_ for _ in ()).throw(
                    RuntimeError("synthetic deadline")
                ),
            )
    assert path.read_bytes() == b""
    assert indexed.verify(path)["event_count"] == 0


def test_existing_authoritative_jsonl_rebuilds_disposable_index(tmp_path):
    path = tmp_path / "paired.jsonl"
    for sequence in range(5):
        append(ShadowTradeJournal, path, sequence)
    indexed = IndexedShadowTradeJournal(path)
    assert indexed.verify(path)["event_count"] == 5
    assert indexed.find_event("missing") is None
    assert indexed._read_events(path) == ShadowTradeJournal._read_events(path)


def test_external_authoritative_append_is_reconciled_before_lookup(tmp_path):
    path = tmp_path / "paired.jsonl"
    indexed = IndexedShadowTradeJournal(path)
    first = append(indexed, path, 1)
    second = append(ShadowTradeJournal, path, 2)
    assert indexed.verify(path)["event_count"] == 2
    assert indexed._read_events(path) == [first, second]


def test_two_index_views_reconcile_under_the_same_file_lock(tmp_path):
    path = tmp_path / "paired.jsonl"
    first, second = IndexedShadowTradeJournal(path), IndexedShadowTradeJournal(path)
    events = []
    for sequence, backend in enumerate((first, second, first, second)):
        events.append(append(backend, path, sequence))
    assert first._read_events(path) == events
    assert second._read_events(path) == events
    assert ShadowTradeJournal.verify(path)["valid"]


def test_deleted_index_is_rebuilt_only_from_authoritative_jsonl(tmp_path):
    path = tmp_path / "paired.jsonl"
    indexed = IndexedShadowTradeJournal(path)
    expected = [append(indexed, path, sequence) for sequence in range(3)]
    indexed.close()
    index_path = IndexedShadowTradeJournal.index_path_for(path)
    for artifact in (index_path, Path(str(index_path) + "-wal"), Path(str(index_path) + "-shm")):
        if artifact.exists():
            artifact.unlink()
    rebuilt = IndexedShadowTradeJournal(path)
    assert rebuilt._read_events(path) == expected
    assert ShadowTradeJournal.verify(path)["valid"]


@pytest.mark.parametrize("fault", ["body", "previous", "truncated"])
def test_authoritative_corruption_invalidates_index(fault, tmp_path):
    path = tmp_path / "paired.jsonl"
    indexed = IndexedShadowTradeJournal(path)
    append(indexed, path, 1)
    original = path.read_bytes()
    if fault == "body":
        path.write_bytes(original.replace(b"SYNTHETIC_EVENT", b"SYNTHETIC_EVENX"))
    elif fault == "previous":
        path.write_bytes(original.replace(b'"previous_event_sha256":"0', b'"previous_event_sha256":"1', 1))
    else:
        path.write_bytes(original[:-5])
    with pytest.raises(RuntimeError):
        indexed.verify(path)
    assert path.read_bytes() != original


def test_corrupted_derived_event_is_rejected_without_changing_jsonl(tmp_path):
    path = tmp_path / "paired.jsonl"
    context = activation()
    indexed = IndexedShadowTradeJournal(path)
    collector = A.PairedForwardEvidenceCollector(
        activation=context, journal_path=path, journal_backend=indexed,
    )
    snapshot = lifecycle_end_snapshot("BTCUSD", TARGET + .05)
    decision = collector.collect_decision(snapshot=snapshot)
    original = path.read_bytes()
    indexed._connection.execute(
        "UPDATE events SET event_json=replace(event_json, 'BTCUSD', 'ETCUSD')"
    )
    with pytest.raises(RuntimeError, match="authoritative hash"):
        indexed.phase_event(context.manifest_sha256, decision.pair_key, "decision")
    assert path.read_bytes() == original
    assert ShadowTradeJournal.verify(path)["valid"]


def test_semantically_wrong_rehashed_identity_is_rejected(tmp_path):
    path = tmp_path / "paired.jsonl"
    context = activation()
    indexed = IndexedShadowTradeJournal(path)
    collector = A.PairedForwardEvidenceCollector(
        activation=context, journal_path=path, journal_backend=indexed,
    )
    collector.collect_decision(snapshot=lifecycle_end_snapshot("BTCUSD", TARGET + .05))
    indexed.close()
    event = ShadowTradeJournal._read_events(path)[0]
    event["payload"]["sprint93_2b_event_id"] = "f" * 64
    event["position_id"] = "f" * 64
    event.pop("event_sha256")
    event["event_sha256"] = ShadowTradeJournal._sha256_text(
        ShadowTradeJournal._canonical_json(event)
    )
    path.write_text(ShadowTradeJournal._canonical_json(event) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="identity mismatch"):
        IndexedShadowTradeJournal(path)


def test_large_rebuild_has_bounded_python_memory(tmp_path, monkeypatch):
    path = tmp_path / "paired.jsonl"
    context = activation()
    monkeypatch.setattr(A, "_utc_now_epoch", lambda: TARGET + .05)
    seed = A.PairedForwardEvidenceCollector(activation=context, journal_path=path)
    for symbol in A.SYMBOL_MAP:
        decision = seed.collect_decision(snapshot=lifecycle_end_snapshot(symbol, TARGET + .05))
        seed.open_virtual_entries(
            pair_key=decision.pair_key, balance=10000., point=.01,
            time_authority=lifecycle_end_snapshot(symbol, TARGET + .05).time_authority(),
        )
    template = ShadowTradeJournal._read_events(path)
    previous, sequence = ShadowTradeJournal.GENESIS_SHA256, 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for index in range(64):
            for original in template:
                event = json.loads(json.dumps(original))
                sequence += 1
                event["event_sequence"] = sequence
                event["previous_event_sha256"] = previous
                event["broker_epoch"] += index * 900
                payload = event["payload"]
                pair = (payload["pair_key"][0], utc(START + index * 900))
                payload["pair_key"] = list(pair)
                payload["sprint93_2b_event_id"] = A._event_id(
                    manifest_sha256=context.manifest_sha256,
                    pair_key=pair, phase=payload["phase"],
                )
                event["position_id"] = payload["sprint93_2b_event_id"]
                event.pop("event_sha256")
                previous = ShadowTradeJournal._sha256_text(
                    ShadowTradeJournal._canonical_json(event)
                )
                event["event_sha256"] = previous
                handle.write(ShadowTradeJournal._canonical_json(event) + "\n")
    assert path.stat().st_size > 8_000_000
    gc.collect()
    tracemalloc.start()
    rebuilt = IndexedShadowTradeJournal(path)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert rebuilt.verify(path)["event_count"] == len(template) * 64
    assert peak < 16_000_000
