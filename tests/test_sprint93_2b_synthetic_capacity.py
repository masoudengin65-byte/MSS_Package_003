"""Bounded capacity diagnostic, not a strategy/backtest or live-latency claim.

History is replicated from real no-trade event shapes and rehashed, not claimed
to be semantically valid historical research evidence. Only the new timed pair
uses the real collector/strategy/durable-entry paths. All files stay in tmp_path.
"""

from copy import deepcopy
import json
import os
import sys
import time

import pytest

from mss.analysis import sprint93_paired_forward_activation as A
from mss.analysis import sprint93_paired_forward_runner as B
from mss.analysis.indexed_shadow_trade_journal import IndexedShadowTradeJournal
from test_sprint93_2b_boundary_runner import START, TARGET, activation, lifecycle_end_snapshot, utc


CAPACITY_SIZES = [0, 32, 256]
if os.environ.get("MSS_RUN_FULL_HORIZON_CAPACITY") == "1":
    CAPACITY_SIZES.append(4318)


@pytest.mark.parametrize("historical_boundaries", CAPACITY_SIZES)
def test_synthetic_journal_capacity_is_fail_closed(monkeypatch, tmp_path, historical_boundaries):
    class NoBrokerAccess:
        def __getattr__(self, name):
            raise AssertionError(f"synthetic capacity test forbids MT5 access: {name}")
    monkeypatch.setitem(sys.modules, "MetaTrader5", NoBrokerAccess())
    journal = tmp_path / "paired.jsonl"
    context = activation()
    monkeypatch.setattr(A, "_utc_now_epoch", lambda: float(TARGET + .05))
    seed = A.PairedForwardEvidenceCollector(activation=context, journal_path=journal)
    B._commit_pair_snapshots(seed, tuple(lifecycle_end_snapshot(s, TARGET + .05) for s in A.SYMBOL_MAP))
    template = A.ShadowTradeJournal._read_events(journal)
    assert sum(e["payload"]["phase"] == "decision" for e in template) == 2
    assert sum(e["payload"]["phase"] == "entry" for e in template) == 2
    assert all(not b["is_actual_trade"] for e in template if e["payload"]["phase"] == "entry"
               for b in e["payload"]["branches"].values())

    previous = A.ShadowTradeJournal.GENESIS_SHA256
    sequence = 0
    with journal.open("w", encoding="utf-8", newline="\n") as handle:
        for index in range(historical_boundaries):
            for original in template:
                event = deepcopy(original)
                event.pop("event_sha256")
                sequence += 1
                event["event_sequence"] = sequence
                event["previous_event_sha256"] = previous
                event["broker_epoch"] += index * 900
                payload = event["payload"]
                pair = (payload["pair_key"][0], utc(START + index * 900))
                payload["pair_key"] = list(pair)
                payload["sprint93_2b_event_id"] = A._event_id(
                    manifest_sha256=context.manifest_sha256, pair_key=pair, phase=payload["phase"],
                )
                event["position_id"] = payload["sprint93_2b_event_id"]
                previous = A.ShadowTradeJournal._sha256_text(A.ShadowTradeJournal._canonical_json(event))
                event["event_sha256"] = previous
                handle.write(A.ShadowTradeJournal._canonical_json(event) + "\n")
    assert A.ShadowTradeJournal.verify(journal)["valid"]
    initial_bytes = journal.stat().st_size
    target = TARGET + historical_boundaries * 900
    snapshots = tuple(lifecycle_end_snapshot(s, target + .05) for s in A.SYMBOL_MAP)
    backend = IndexedShadowTradeJournal(journal)
    # Clock advances by actual wall duration during the measured collector work.
    # There is no fabricated fast clock concealing a missed durable-entry limit.
    started = time.perf_counter()
    monkeypatch.setattr(A, "_utc_now_epoch", lambda: target + .05 + time.perf_counter() - started)
    failure = None
    try:
        collector = A.PairedForwardEvidenceCollector(
            activation=context, journal_path=journal, journal_backend=backend,
        )
        B._commit_pair_snapshots(collector, snapshots)
    except RuntimeError as exc:
        failure = str(exc)
        assert any(word in failure.lower() for word in ("deadline", "stale", "window")), failure
    elapsed = time.perf_counter() - started
    timed_events = [e for e in A.ShadowTradeJournal._read_events(journal)
                    if e["payload"]["pair_key"][1] == utc(target - 900)]
    if failure is None:
        assert sum(e["payload"]["phase"] == "entry" for e in timed_events) == 2
        assert all(b["reason"] != "RESTART_AFTER_ENTRY_WINDOW"
                   for e in timed_events if e["payload"]["phase"] == "entry"
                   for b in e["payload"]["branches"].values())
    assert A.ShadowTradeJournal.verify(journal)["valid"]
    print(json.dumps({
        "diagnostic": "SYNTHETIC_SHAPE_REPLICATED_JOURNAL_CAPACITY",
        "historical_boundaries": historical_boundaries,
        "historical_pairs": historical_boundaries * 2,
        "historical_bytes": initial_bytes,
        "indexed_access": True,
        "timed_pair_seconds": round(elapsed, 6),
        "durable_pair_completed": failure is None,
        "failure": failure,
        "live_data_used": False,
    }, sort_keys=True))
