"""Synthetic single-writer scheduling tests; never initialize a live broker."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from mss.analysis import sprint93_paired_forward_activation as A
from mss.analysis import sprint93_paired_forward_runner as B
from mss.analysis.shadow_trade_journal import ShadowTradeJournalBusyError
from test_sprint93_2b_boundary_runner import (
    START, TARGET, R, LifecycleFakeCollector, activation, lifecycle_end_snapshot,
    snapshot, utc,
)


@pytest.fixture
def supervisor(monkeypatch, tmp_path):
    state = SimpleNamespace(
        now=float(START - 60), monotonic=0., calls=[], capture_delay=.02,
        setup_delay=0., open_trades=False, hold_polls=0, write_delay=0.,
        failure_symbol=None, mutate_snapshot=None, closed_on_end=False,
    )
    # Short synthetic window only in this verified test fixture. The public CLI
    # has no start/end override and receives the real manifest's fixed window.
    context = replace(activation(), exclusive_45_day_end_utc=utc(START + 2700))
    journal = tmp_path / "paired.jsonl"
    def advance(seconds):
        state.now += seconds
        state.monotonic += seconds
    state.advance = advance
    monkeypatch.setattr(B, "_utc_now_epoch", lambda: state.now)
    monkeypatch.setattr(A, "_utc_now_epoch", lambda: state.now)
    monkeypatch.setattr(B.time, "monotonic", lambda: state.monotonic)
    monkeypatch.setattr(B.time, "sleep", advance)
    monkeypatch.setattr(B, "verify_local_freeze", lambda *_: state.calls.append(("freeze", state.now)))

    class Session:
        def __enter__(self):
            state.calls.append(("initialize", state.now))
            advance(state.setup_delay)
            return self
        def __exit__(self, *_):
            state.calls.append(("shutdown", state.now))
        def capture(self, symbol, **kwargs):
            state.calls.append(("capture", symbol, state.now, kwargs))
            if symbol == state.failure_symbol:
                raise RuntimeError("synthetic capture failure")
            advance(state.capture_delay)
            value = lifecycle_end_snapshot(symbol, state.now)
            return state.mutate_snapshot(value) if state.mutate_snapshot else value

    class Collector(LifecycleFakeCollector):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.events = {}
        def collect_decision(self, *, snapshot):
            state.calls.append(("decision", snapshot.canonical_symbol, state.now))
            pair = (snapshot.canonical_symbol, utc(snapshot.current_bar_epoch - 900))
            self.events[pair, "decision"] = {"payload": {
                "live_mt5_acquisition": snapshot.provenance(),
            }}
            advance(state.write_delay)
            return SimpleNamespace(pair_key=pair, write=SimpleNamespace(appended=True))
        def open_virtual_entries(self, *, pair_key, **kwargs):
            state.calls.append(("entry", pair_key, state.now))
            self.events[pair_key, "entry"] = {"payload": {"branches": {
                branch: {"is_actual_trade": state.open_trades,
                         "reason": "SYNTHETIC_ENTRY"}
                for branch in ("baseline", "candidate")
            }}}
            return SimpleNamespace(
                pair_key=pair_key, write=SimpleNamespace(appended=True),
                baseline_position=object() if state.open_trades else None,
                candidate_position=object() if state.open_trades else None,
            )
        def _event_for(self, pair, phase):
            return self.events[pair, phase]
        def recover(self):
            pending = super().recover().pending_entry_pair_keys
            return SimpleNamespace(
                pending_entry_pair_keys=pending,
                decision_pair_keys=tuple(p for p, phase in self.events if phase == "decision"),
            )
        def update_virtual_trade(self, **kwargs):
            self.hold = state.hold_polls > 0
            if self.hold:
                state.hold_polls -= 1
            state.calls.append(("update", kwargs["pair_key"], state.now))
            return super().update_virtual_trade(**kwargs)
        def timebox_close_virtual_trade(self, **kwargs):
            state.closed_on_end = True
            state.calls.append(("timebox", kwargs["pair_key"], state.now))
            return super().timebox_close_virtual_trade(**kwargs)

    collector = Collector(activation=context, journal_path=journal)
    monkeypatch.setattr(B, "PairedForwardEvidenceCollector", lambda **_: collector)
    monkeypatch.setattr(B, "LiveMt5ReadOnlySession", Session)
    state.run = lambda: B.run_forward_supervisor(
        activation=context, repository_root=tmp_path, journal_path=journal,
    )
    state.audit = lambda: A.ShadowTradeJournal._read_events(tmp_path / "paired.jsonl.supervisor.jsonl")
    state.context, state.collector, state.journal = context, collector, journal
    return state


def test_supervisor_exact_boundaries_and_single_session(supervisor):
    result = supervisor.run()
    assert result["completed_boundaries"] == 2
    assert result["research_validity_certified"] is False
    assert [c[1] for c in supervisor.calls if c[0] == "initialize"] == [START]
    assert sum(c[0] == "shutdown" for c in supervisor.calls) == 1
    decisions = [c for c in supervisor.calls if c[0] == "decision"]
    assert [c[1] for c in decisions] == ["BTCUSD", "ETHUSD"] * 2
    assert all(0 <= c[2] - target <= 2 for c, target in zip(decisions, [TARGET] * 2 + [TARGET + 900] * 2))
    assert not any(c[0] == "capture" and c[2] < TARGET for c in supervisor.calls)
    assert [e["event_type"] for e in supervisor.audit()] == [
        "SUPERVISOR_STARTED", "SUPERVISOR_BOUNDARY_COMPLETED",
        "SUPERVISOR_BOUNDARY_COMPLETED", "SUPERVISOR_FINISHED_PENDING_REVIEW",
    ]
    assert supervisor.audit()[0]["payload"]["next_entry_boundary_utc_epoch"] == TARGET
    assert supervisor.audit()[1]["payload"]["next_entry_boundary_utc_epoch"] == TARGET + 900


def test_supervisor_polls_brief_boundary_publication_lag(supervisor):
    lagged = False

    def lag_first_btc(value):
        nonlocal lagged
        if value.canonical_symbol == "BTCUSD" and not lagged:
            lagged = True
            return snapshot("BTCUSD", supervisor.now, current=TARGET - 900)
        return value

    supervisor.mutate_snapshot = lag_first_btc
    result = supervisor.run()
    assert result["completed_boundaries"] == 2
    first = [c for c in supervisor.calls if c[0] == "capture"][:3]
    assert [c[1] for c in first] == ["BTCUSD", "BTCUSD", "ETHUSD"]


def test_supervisor_polls_open_positions_between_new_boundaries(supervisor):
    supervisor.open_trades = True
    supervisor.hold_polls = 8
    supervisor.run()
    updates = [c for c in supervisor.calls if c[0] == "update"]
    assert any(TARGET + .5 < c[2] < TARGET + 900 for c in updates)
    assert sum(c[0] == "decision" for c in supervisor.calls) == 4
    assert sum(c[0] == "initialize" for c in supervisor.calls) == 1
    assert not B.LifecycleCoordinator(supervisor.collector).outstanding()
    # New entry writes have priority over lifecycle valuation at the boundary.
    first_update = next(i for i, c in enumerate(supervisor.calls) if c[0] == "update")
    assert sum(c[0] == "entry" for c in supervisor.calls[:first_update]) == 2


def test_supervisor_timeboxes_survivors_at_exclusive_end(supervisor):
    supervisor.open_trades = True
    supervisor.hold_polls = 100000
    supervisor.run()
    assert supervisor.closed_on_end
    end = START + 2700
    assert all(c[2] < end for c in supervisor.calls if c[0] in {"entry", "update", "decision"})
    assert all(c[2] >= end for c in supervisor.calls if c[0] == "timebox")
    assert len(supervisor.collector.events) > 4


@pytest.mark.parametrize("late", [START, TARGET - 1, TARGET + 901])
def test_supervisor_rejects_late_start_before_any_market_access(supervisor, late):
    supervisor.now = late
    with pytest.raises(RuntimeError, match="before activation"):
        supervisor.run()
    assert not any(c[0] == "initialize" for c in supervisor.calls)
    assert not supervisor.audit()


def test_supervisor_cannot_restart_a_finished_run(supervisor):
    supervisor.run()
    original_events = supervisor.audit()
    supervisor.now = START - 60.
    captures = sum(c[0] == "capture" for c in supervisor.calls)
    with pytest.raises(RuntimeError, match="pristine journals"):
        supervisor.run()
    assert supervisor.audit() == original_events
    assert sum(c[0] == "capture" for c in supervisor.calls) == captures


def test_supervisor_cannot_restart_after_partial_failure(supervisor):
    supervisor.failure_symbol = "ETHUSD"
    with pytest.raises(RuntimeError, match="capture failure"):
        supervisor.run()
    assert not any(c[0] == "decision" for c in supervisor.calls)
    assert supervisor.audit()[-1]["event_type"] == "SUPERVISOR_FAILED"
    supervisor.now = START - 1.
    with pytest.raises(RuntimeError, match="pristine journals"):
        supervisor.run()


def test_supervisor_refuses_existing_evidence_and_orphans(supervisor, tmp_path):
    orphan = tmp_path / "virtual_positions" / "orphan" / "shadow_position.jsonl"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("preserve", encoding="utf-8")
    with pytest.raises(RuntimeError, match="orphan"):
        supervisor.run()
    assert orphan.read_text() == "preserve"
    assert not supervisor.audit()


def test_supervisor_owns_the_existing_writer_lease(supervisor):
    with B.runner_lease(supervisor.journal):
        with pytest.raises(ShadowTradeJournalBusyError):
            supervisor.run()
    assert not supervisor.audit()


def test_supervisor_slow_setup_does_not_shift_first_target(supervisor):
    supervisor.setup_delay = 891
    with pytest.raises(RuntimeError, match="preparation deadline"):
        supervisor.run()
    assert not any(c[0] == "capture" for c in supervisor.calls)
    assert supervisor.audit()[-1]["payload"]["next_entry_boundary_utc_epoch"] == TARGET


def test_supervisor_clock_step_during_capture_fails_before_writes(supervisor):
    def step(snapshot):
        supervisor.now += 1.
        return snapshot
    supervisor.mutate_snapshot = step
    with pytest.raises(RuntimeError, match="clock stepped"):
        supervisor.run()
    assert not any(c[0] == "decision" for c in supervisor.calls)


def test_supervisor_late_acquisition_has_no_decision(supervisor):
    supervisor.capture_delay = 1.1
    with pytest.raises(RuntimeError, match="entry window|preparation deadline"):
        supervisor.run()
    assert not any(c[0] == "decision" for c in supervisor.calls)


def test_supervisor_preserves_written_decision_on_late_entry(supervisor, monkeypatch):
    original = supervisor.collector.open_virtual_entries
    def late(**kwargs):
        result = original(**kwargs)
        supervisor.collector.events[kwargs["pair_key"], "entry"]["payload"]["branches"]["baseline"]["reason"] = "RESTART_AFTER_ENTRY_WINDOW"
        return result
    monkeypatch.setattr(supervisor.collector, "open_virtual_entries", late)
    with pytest.raises(RuntimeError, match="durable entry missed"):
        supervisor.run()
    assert sum(c[0] == "decision" for c in supervisor.calls) == 1
    assert supervisor.audit()[-1]["event_type"] == "SUPERVISOR_FAILED"


def test_supervisor_changed_broker_between_flat_periods_is_rejected(supervisor):
    def switch(value):
        if supervisor.now >= TARGET + 900:
            provenance = value.provenance()
            provenance["account_currency"] = "EUR"
            return replace(value, provenance_json=A._canonical_json_bytes(provenance).decode())
        return value
    supervisor.mutate_snapshot = switch
    with pytest.raises(RuntimeError, match="broker context changed"):
        supervisor.run()
    assert sum(c[0] == "decision" for c in supervisor.calls) == 2


def test_supervisor_crossing_boundary_in_a_poll_is_not_relabelled(supervisor):
    supervisor.open_trades = True
    supervisor.hold_polls = 100000
    def slow_near_boundary(value):
        if TARGET + 898.9 <= supervisor.now < TARGET + 900:
            supervisor.advance(1.2)
        return value
    supervisor.mutate_snapshot = slow_near_boundary
    with pytest.raises(RuntimeError, match="poll crossed a scheduled boundary"):
        supervisor.run()
    assert sum(c[0] == "decision" for c in supervisor.calls) == 2


def test_supervisor_detects_polling_gap_without_catchup(supervisor, monkeypatch):
    supervisor.open_trades = True
    supervisor.hold_polls = 100000
    original_wait = B._wait_until_utc
    def stalled(target):
        original_wait(target)
        if target == TARGET + 1:
            supervisor.advance(6.)
    monkeypatch.setattr(B, "_wait_until_utc", stalled)
    with pytest.raises(RuntimeError, match="observation gap"):
        supervisor.run()
    assert sum(c[0] == "capture" for c in supervisor.calls) == 2


def test_supervisor_missed_boundary_is_never_backfilled(supervisor, monkeypatch):
    original_wait = B._wait_until_utc
    def stalled(target):
        original_wait(target)
        if target == TARGET + 900:
            supervisor.advance(3.)
    monkeypatch.setattr(B, "_wait_until_utc", stalled)
    with pytest.raises(RuntimeError, match="missed decision boundary"):
        supervisor.run()
    assert sum(c[0] == "decision" for c in supervisor.calls) == 2
    assert supervisor.audit()[-1]["payload"]["completed_boundaries"] == 1


def test_supervisor_final_coverage_is_checked(supervisor, monkeypatch):
    original = supervisor.collector.recover
    def missing():
        result = original()
        result.decision_pair_keys = ()
        return result
    monkeypatch.setattr(supervisor.collector, "recover", missing)
    with pytest.raises(RuntimeError, match="final coverage"):
        supervisor.run()
    assert supervisor.audit()[-1]["event_type"] == "SUPERVISOR_FAILED"


def test_supervisor_cli_has_no_window_override(monkeypatch, capsys):
    argv = ["supervise-forward", "--no-forward-outcome-access-verified",
            "--manifest-commit-sha", "b" * 40, "--manifest-publication-pr-number", "99"]
    args = R.parser().parse_args(argv)
    calls = []
    monkeypatch.setattr(R, "verified_context", lambda _: calls.append("verified") or activation())
    monkeypatch.setattr(R, "run_forward_supervisor", lambda **_: calls.append("supervise") or {"ok": True})
    args.handler(args)
    assert calls == ["verified", "supervise"]
    assert '"ok": true' in capsys.readouterr().out
    with pytest.raises(SystemExit):
        R.parser().parse_args(argv + ["--entry-bar-open-utc", utc(TARGET)])


def test_supervisor_with_real_collector_and_synthetic_no_trade_journal(supervisor, monkeypatch):
    monkeypatch.setattr(B, "PairedForwardEvidenceCollector", A.PairedForwardEvidenceCollector)
    result = supervisor.run()
    assert result["completed_boundaries"] == 2
    assert A.ShadowTradeJournal.verify(supervisor.journal)["valid"]
    collector = A.PairedForwardEvidenceCollector(activation=supervisor.context, journal_path=supervisor.journal)
    assert len(collector.recover().decision_pair_keys) == 4
    assert not collector.recover().pending_entry_pair_keys


def test_supervisor_real_virtual_trades_are_managed_before_next_boundary(supervisor, monkeypatch):
    class Signals:
        def evaluate(self, *, symbol, rates, current_bar_epoch):
            return SimpleNamespace(
                valid=True, reason="FROZEN_BOS_SIGNAL_ARMED",
                signal_bar_epoch=current_bar_epoch - 900,
                completed_candle_count=len(rates) - 1,
                frozen_signal=A.FrozenShadowSignal(
                    valid=True, action="PENDING_NEXT_CANDLE_ENTRY",
                    reason="FROZEN_BOS_SIGNAL_ARMED", symbol=symbol, timeframe="M15",
                    direction="BUY", signal_bar_epoch=current_bar_epoch - 900,
                    expected_entry_bar_epoch=current_bar_epoch, stop_loss=90.,
                ),
                pipeline_result=SimpleNamespace(
                    valid=True, bos_detected=True, bos_direction="BULLISH",
                    confluence_valid=True, confluence_signal="BUY", confluence_gate_rejected=False,
                ),
            )
    def factory(**kwargs):
        return A.PairedForwardEvidenceCollector(**kwargs, baseline_engine=Signals(), candidate_engine=Signals())
    def synthetic_open(**kwargs):
        position = A.VirtualPositionEngine.open_position(
            position_id=kwargs["position_id"], symbol=kwargs["symbol"],
            direction=kwargs["direction"], volume=.01,
            entry_price=kwargs["entry_price"], stop_loss=kwargs["stop_loss"],
            take_profit=kwargs["take_profit"], broker_epoch=kwargs["broker_epoch"],
        )
        A.ShadowTradeJournal.append_event(
            path=kwargs["journal_path"], event_type="POSITION_OPENED",
            position_id=position.position_id, broker_epoch=kwargs["broker_epoch"],
            payload={key: getattr(position, key) for key in (
                "symbol", "direction", "volume", "entry_price", "stop_loss",
                "take_profit", "initial_risk_price",
            )},
        )
        return SimpleNamespace(valid=True, reason="VIRTUAL_POSITION_OPENED", position=position,
                               real_order_send_allowed=False, order_send_called=False, order_check_called=False)
    monkeypatch.setattr(B, "PairedForwardEvidenceCollector", factory)
    monkeypatch.setattr(A.ShadowTradeEngine, "open_trade", synthetic_open)
    monkeypatch.setattr(A.ShadowTradeValuation, "calculate", lambda **_: SimpleNamespace(
        valid=True, reason="SYNTHETIC_VALUATION", pnl_account_currency=-.15,
        real_order_send_allowed=False, order_send_called=False, order_check_called=False,
    ))
    supervisor.mutate_snapshot = lambda s: (
        replace(s, bid=85., ask=85.02) if supervisor.now % 900 >= 1 else s
    )
    supervisor.run()
    recovered = factory(activation=supervisor.context, journal_path=supervisor.journal)
    assert len(recovered.recover().settled_pair_keys) == 4
    assert not recovered.recover().open_pair_keys
    for pair in recovered.recover().settled_pair_keys:
        for branch in ("baseline", "candidate"):
            assert A.ShadowTradeJournal.verify(recovered.trade_journal_path(pair, branch))["valid"]
            terminal = recovered._event_for(pair, "terminal_" + branch)
            entry_target = A._epoch_from_utc_z(pair[1], "synthetic decision") + 900
            assert entry_target < terminal["broker_epoch"] < entry_target + 900


def test_supervisor_preserves_torn_start_marker(supervisor, tmp_path):
    path = tmp_path / "paired.jsonl.supervisor.jsonl"
    path.write_bytes(b'{"incomplete":')
    with pytest.raises(RuntimeError, match="pristine journals"):
        supervisor.run()
    assert path.read_bytes() == b'{"incomplete":'
    assert not any(c[0] == "initialize" for c in supervisor.calls)


def test_supervisor_source_change_after_wait_blocks_acquisition(supervisor, monkeypatch):
    def changed(*_):
        if supervisor.now >= TARGET:
            raise RuntimeError("execution source changed after verification")
    monkeypatch.setattr(B, "verify_local_freeze", changed)
    with pytest.raises(RuntimeError, match="source changed"):
        supervisor.run()
    assert not any(c[0] == "capture" for c in supervisor.calls)
    assert supervisor.audit()[-1]["event_type"] == "SUPERVISOR_FAILED"
