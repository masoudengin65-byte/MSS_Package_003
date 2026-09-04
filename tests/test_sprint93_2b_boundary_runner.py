from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from mss.analysis import sprint93_paired_forward_activation as A
from mss.analysis import sprint93_paired_forward_runner as B
from mss.analysis.shadow_trade_journal import ShadowTradeJournalBusyError


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "boundary_cli", ROOT / A.ACTIVATION_RUNNER_PATH
)
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)
START = 1_800_000_000  # Synthetic, exactly M15 aligned; no live prices are used.
TARGET = START + 900


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def activation():
    return A.VerifiedActivation(
        manifest_sha256="a" * 64,
        activation_merge_commit_sha="b" * 40,
        first_eligible_m15_open_utc=utc(START),
        exclusive_45_day_end_utc=utc(START + 45 * 86400),
        python_version="test-python", numpy_version="test-numpy",
        execution_identity=(),
        _verification_marker=A._VERIFIED_ACTIVATION_MARKER,
    )


def rates():
    return [dict(
        time=TARGET - (500 - index) * 900,
        open=100., high=102., low=99., close=101.,
        tick_volume=10, spread=2, real_volume=0,
    ) for index in range(501)]


def snapshot(symbol, now):
    frozen = A._freeze_rates(rates(), current_bar_epoch=TARGET)
    authority = A.GlobalTimeAuthority().build(
        utc_epoch_before_tick=now, utc_epoch_after_tick=now,
        tick_epoch=int(now), current_bar_epoch=TARGET,
    )
    from dataclasses import asdict
    provenance = dict(
        schema_version=A.LIVE_ACQUISITION_VERSION,
        source="DIRECT_LIVE_MT5_READ_ONLY",
        canonical_symbol=symbol, broker_symbol=A.SYMBOL_MAP[symbol],
        timeframe="M15", tick_epoch=int(now), current_bar_epoch=TARGET,
        rate_record_count=501, rates_sha256=A._canonical_sha256([asdict(r) for r in frozen]),
        time_authority_sha256=A._canonical_sha256(authority),
        read_only=True, real_order_send_allowed=False,
        order_send_called=False, order_check_called=False,
        account_server="Synthetic-Demo", account_currency="USD", terminal_build=5000,
    )
    return A.LiveMt5Snapshot(
        canonical_symbol=symbol, broker_symbol=A.SYMBOL_MAP[symbol],
        current_bar_epoch=TARGET, tick_epoch=int(now),
        bid=100., ask=100.02, balance=10000., point=.01, rates=frozen,
        time_authority_json=A._canonical_json_bytes(authority).decode(),
        provenance_json=A._canonical_json_bytes(provenance).decode(),
        _verification_marker=A._LIVE_MT5_SNAPSHOT_MARKER,
    )


@pytest.fixture
def rig(monkeypatch, tmp_path):
    state = SimpleNamespace(
        now=float(TARGET - 70), monotonic=0., calls=[], writes=[],
        setup_delay=0., capture_delay=.05, pending=(), open_pairs=(),
        failure_symbol=None, mutate_snapshot=None, late_entry=False,
    )
    def advance(seconds):
        state.now += seconds
        state.monotonic += seconds
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
        def require_context(self, provenance):
            state.calls.append(("context", state.now))
            expected = snapshot("BTCUSD", TARGET + .1).provenance()
            if any(provenance.get(f) != expected[f]
                   for f in ("account_server", "account_currency", "terminal_build")):
                raise RuntimeError("lifecycle broker context changed since the decision")
        def capture(self, symbol, **kwargs):
            state.calls.append(("capture", symbol, state.now))
            if symbol == state.failure_symbol:
                raise RuntimeError("synthetic acquisition failure")
            advance(state.capture_delay)
            value = snapshot(symbol, state.now)
            return state.mutate_snapshot(value) if state.mutate_snapshot else value

    class Collector:
        def __init__(self, **kwargs):
            self.journal_path = kwargs["journal_path"]
        def recover(self):
            return SimpleNamespace(pending_entry_pair_keys=state.pending, open_pair_keys=state.open_pairs)
        def _events(self):
            return []
        def collect_decision(self, *, snapshot):
            state.writes.append(snapshot.canonical_symbol)
            state.calls.append(("write", snapshot.canonical_symbol, state.now))
            return SimpleNamespace(pair_key=(snapshot.canonical_symbol, utc(START)), write=SimpleNamespace(appended=True))
        def open_virtual_entries(self, **kwargs):
            return SimpleNamespace(write=SimpleNamespace(appended=True), baseline_position=None, candidate_position=None)
        def _event_for(self, *_):
            return {"payload": {"branches": {"baseline": {
                "reason": "RESTART_AFTER_ENTRY_WINDOW" if state.late_entry else "BASELINE_NO_TRADE"
            }}}}

    monkeypatch.setattr(B, "LiveMt5ReadOnlySession", Session)
    monkeypatch.setattr(B, "PairedForwardEvidenceCollector", Collector)
    state.advance = advance
    state.run = lambda **kwargs: B.collect_pair_at_boundary(
        activation=activation(), repository_root=tmp_path,
        journal_path=tmp_path / "paired.jsonl",
        entry_bar_open_utc=kwargs.get("target", utc(TARGET)),
    )
    return state


@pytest.mark.parametrize("verification_seconds", [39.615, 42.502, 46.235])
def test_network_variance_is_absorbed_before_boundary(rig, monkeypatch, verification_seconds):
    def verify(_args):
        rig.calls.append(("public_verification", rig.now))
        rig.advance(verification_seconds)
        return activation()
    monkeypatch.setattr(R, "verified_context", verify)
    monkeypatch.setattr(R, "collect_pair_at_boundary", lambda **_: rig.run())
    R.collect_pair(SimpleNamespace(entry_bar_open_utc=utc(TARGET)))
    assert rig.calls[0][0] == "public_verification"
    captures = [c for c in rig.calls if c[0] == "capture"]
    assert [c[1] for c in captures] == ["BTCUSD", "ETHUSD"]
    assert captures[0][2] == TARGET
    assert rig.writes == ["BTCUSD", "ETHUSD"]
    assert max(c[2] for c in captures) < TARGET + 2
    assert sum(c[0] == "initialize" for c in rig.calls) == 1
    assert rig.calls[-1][0] == "shutdown"


def test_all_acquisitions_precede_any_evidence_write(rig):
    result = rig.run()
    kinds = [c[0] for c in rig.calls]
    assert max(i for i, c in enumerate(kinds) if c == "capture") < kinds.index("write")
    assert result["bounded_cycle_only"] is True
    assert result["lifecycle_supervisor_running"] is False
    assert result["production_execution_enabled"] is False


def test_no_mt5_setup_or_capture_before_activation(rig):
    rig.now = START - 30.
    rig.run()
    assert next(c[1] for c in rig.calls if c[0] == "initialize") >= START
    assert next(c[2] for c in rig.calls if c[0] == "capture") >= TARGET


@pytest.mark.parametrize("target", [START, TARGET + 1, START + 45 * 86400])
def test_rejects_pre_activation_unaligned_or_end_target(rig, target):
    with pytest.raises(RuntimeError):
        rig.run(target=utc(target))
    assert not rig.writes
    assert not any(c[0] == "initialize" for c in rig.calls)


def test_late_start_never_moves_to_another_candle(rig):
    rig.now = TARGET - 5.
    with pytest.raises(RuntimeError, match="will not be shifted"):
        rig.run()
    assert not any(c[0] == "capture" for c in rig.calls)


def test_slow_mt5_setup_fails_before_capture_and_closes_session(rig):
    rig.setup_delay = 65.
    with pytest.raises(RuntimeError, match="setup missed"):
        rig.run()
    assert not rig.writes
    assert rig.calls[-1][0] == "shutdown"


@pytest.mark.parametrize("field", ["pending", "open_pairs"])
def test_no_wait_while_existing_lifecycle_needs_attention(rig, field):
    setattr(rig, field, (("BTCUSD", utc(START)),))
    with pytest.raises(RuntimeError, match="lifecycle"):
        rig.run()
    assert not any(c[0] == "initialize" for c in rig.calls)


def test_second_symbol_acquisition_failure_writes_nothing(rig):
    rig.failure_symbol = "ETHUSD"
    with pytest.raises(RuntimeError, match="acquisition failure"):
        rig.run()
    assert rig.writes == []
    assert rig.calls[-1][0] == "shutdown"


def test_slow_pair_acquisition_writes_nothing(rig):
    rig.capture_delay = 1.1
    with pytest.raises(RuntimeError, match="entry window"):
        rig.run()
    assert rig.writes == []


def test_stale_bar_is_not_relabelled_as_target(rig):
    rig.mutate_snapshot = lambda s: replace(s, current_bar_epoch=TARGET - 900)
    with pytest.raises(RuntimeError):
        rig.run()
    assert not rig.writes


def test_mixed_broker_context_blocks_before_writes(rig):
    def mutate(s):
        if s.canonical_symbol == "ETHUSD":
            provenance = s.provenance()
            provenance["account_server"] = "Another-Demo"
            return replace(s, provenance_json=A._canonical_json_bytes(provenance).decode())
        return s
    rig.mutate_snapshot = mutate
    with pytest.raises(RuntimeError, match="broker context"):
        rig.run()
    assert not rig.writes


def test_expired_durable_entry_is_not_reported_as_success(rig):
    rig.late_entry = True
    with pytest.raises(RuntimeError, match="partial evidence retained"):
        rig.run()
    assert rig.writes == ["BTCUSD"]  # Preserved, never erased or retried.
    assert rig.calls[-1][0] == "shutdown"


def test_local_freeze_is_rechecked_after_wait_before_capture(rig, monkeypatch):
    def verify(*_):
        if rig.now >= TARGET:
            raise RuntimeError("execution changed")
    monkeypatch.setattr(B, "verify_local_freeze", verify)
    with pytest.raises(RuntimeError, match="execution changed"):
        rig.run()
    assert not any(c[0] == "capture" for c in rig.calls)


def test_clock_step_is_not_hidden(rig, monkeypatch):
    def step(seconds):
        rig.advance(seconds)
        rig.now += 3
    monkeypatch.setattr(B.time, "sleep", step)
    with pytest.raises(RuntimeError, match="clock stepped"):
        rig.run()
    assert not rig.writes


def test_runner_lease_is_exclusive_and_released(tmp_path):
    journal = tmp_path / "paired.jsonl"
    with B.runner_lease(journal):
        with pytest.raises(ShadowTradeJournalBusyError):
            with B.runner_lease(journal):
                pytest.fail("second writer acquired lease")
    with B.runner_lease(journal):
        assert not journal.exists()


def test_local_freeze_checks_source_manifest_runtime_and_marker(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    source.write_bytes(b"pass\r\n")
    manifest = tmp_path / A.DEFAULT_MANIFEST_RELATIVE_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"{}\n")
    value = replace(activation(),
        execution_identity=(("source.py", hashlib.sha256(b"pass\n").hexdigest()),),
        manifest_sha256=hashlib.sha256(b"{}\n").hexdigest(),
    )
    monkeypatch.setattr(B, "observed_runtime_versions", lambda: {
        "python_version": "test-python", "numpy_version": "test-numpy"
    })
    B.verify_local_freeze(value, tmp_path)
    with pytest.raises(RuntimeError, match="verified activation"):
        B.verify_local_freeze(replace(value, _verification_marker=None), tmp_path)
    with pytest.raises(RuntimeError, match="runtime changed"):
        B.verify_local_freeze(replace(value, numpy_version="different"), tmp_path)
    source.write_bytes(b"changed\n")
    with pytest.raises(RuntimeError, match="source changed"):
        B.verify_local_freeze(value, tmp_path)
    source.write_bytes(b"pass\n")
    manifest.write_bytes(b"changed\n")
    with pytest.raises(RuntimeError, match="manifest changed"):
        B.verify_local_freeze(value, tmp_path)


def test_pair_cli_requires_published_manifest_and_explicit_target():
    with pytest.raises(SystemExit):
        R.parser().parse_args(["collect-pair-at-boundary"])
    args = R.parser().parse_args([
        "collect-pair-at-boundary", "--manifest-commit-sha", "a" * 40,
        "--manifest-publication-pr-number", "12",
        "--no-forward-outcome-access-verified", "--entry-bar-open-utc", utc(TARGET),
    ])
    assert args.handler is R.collect_pair
    assert args.manifest.name.endswith("_V4.json")


def test_boundary_runner_is_frozen_and_has_no_order_api_calls():
    assert A.BOUNDARY_RUNNER_PATH in A.EXECUTION_ROOT_PATHS
    assert A.verify_package_safety(ROOT / A.BOUNDARY_RUNNER_PATH)


def test_shared_mt5_session_initializes_once_and_cleans_up(monkeypatch):
    calls = []
    def called(name, value):
        def invoke(*args, **kwargs):
            calls.append(name)
            return value
        return invoke
    mt5 = SimpleNamespace(
        initialize=called("initialize", True), shutdown=called("shutdown", None),
        symbol_select=called("symbol_select", True), TIMEFRAME_M15=15,
        terminal_info=called("terminal_info", SimpleNamespace(connected=True)),
        account_info=called("account_info", SimpleNamespace(server="Synthetic-Demo", balance=10000.)),
        symbol_info=called("symbol_info", SimpleNamespace(point=.01)),
        symbol_info_tick=called("tick", SimpleNamespace(time=TARGET, bid=100., ask=100.02)),
        copy_rates_from_pos=called("rates", rates()),
    )
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5)
    monkeypatch.setattr(A, "_utc_now_epoch", lambda: float(TARGET))
    session = A.LiveMt5ReadOnlySession()
    with session:
        assert "tick" not in calls and "rates" not in calls
        snapshots = [session.capture(s) for s in A.SYMBOL_MAP]
        assert all(s.require_verified() is None for s in snapshots)
        assert calls.count("initialize") == 1
        assert "shutdown" not in calls
    assert calls.count("shutdown") == 1
    with pytest.raises(RuntimeError, match="not active"):
        session.capture("BTCUSD")


def test_shared_session_cleanup_on_selection_failure(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "MetaTrader5", SimpleNamespace(
        initialize=lambda **_: True, symbol_select=lambda *_: False,
        shutdown=lambda: calls.append("shutdown"),
    ))
    with pytest.raises(RuntimeError, match="selection failed"):
        with A.LiveMt5ReadOnlySession():
            pytest.fail("session setup should fail")
    assert calls == ["shutdown"]


def test_shared_session_cleanup_on_initialization_failure(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "MetaTrader5", SimpleNamespace(
        initialize=lambda **_: False, last_error=lambda: (1, "synthetic error"),
        shutdown=lambda: calls.append("shutdown"),
    ))
    with pytest.raises(RuntimeError, match="synthetic error"):
        with A.LiveMt5ReadOnlySession():
            pytest.fail("session setup should fail")
    assert calls == ["shutdown"]


@pytest.mark.parametrize("command", [
    "collect-decision", "update-virtual-trades", "timebox-close", "finalize-settlement",
])
def test_other_mutating_cli_commands_share_runner_lease(monkeypatch, tmp_path, command):
    calls = []
    journal = tmp_path / "paired.jsonl"
    args = SimpleNamespace(command=command, handler=lambda _: calls.append("handler"))
    monkeypatch.setattr(R, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(R, "DEFAULT_EVIDENCE_JOURNAL", journal)
    with B.runner_lease(journal):
        with pytest.raises(ShadowTradeJournalBusyError):
            R.main()
    assert not calls
    R.main()
    assert calls == ["handler"]


def test_real_collector_with_synthetic_pair_produces_valid_journal(rig, monkeypatch, tmp_path):
    import time
    monkeypatch.setattr(B, "PairedForwardEvidenceCollector", A.PairedForwardEvidenceCollector)
    started = time.perf_counter()
    result = rig.run()
    elapsed = time.perf_counter() - started
    assert result["result"] == "SPRINT93_2B_BOUNDARY_PAIR_COLLECTED"
    journal = tmp_path / "paired.jsonl"
    assert A.ShadowTradeJournal.verify(journal)["valid"]
    events = A.ShadowTradeJournal._read_events(journal)
    decisions = [e for e in events if e["event_type"] == A.EVIDENCE_EVENT_TYPES["decision"]]
    entries = [e for e in events if e["event_type"] == A.EVIDENCE_EVENT_TYPES["entry"]]
    assert len(decisions) == len(entries) == 2
    assert {e["payload"]["canonical_symbol"] for e in decisions} == set(A.SYMBOL_MAP)
    assert all(not b["is_actual_trade"] for e in entries for b in e["payload"]["branches"].values())
    print(f"Synthetic pair with real strategy/journal elapsed seconds: {elapsed:.3f}")


def test_real_collector_retains_late_entry_evidence(rig, monkeypatch, tmp_path):
    class DelayedCollector(A.PairedForwardEvidenceCollector):
        def collect_decision(self, **kwargs):
            result = super().collect_decision(**kwargs)
            rig.advance(2.1)
            return result
    monkeypatch.setattr(B, "PairedForwardEvidenceCollector", DelayedCollector)
    with pytest.raises(RuntimeError, match="partial evidence retained"):
        rig.run()
    journal = tmp_path / "paired.jsonl"
    assert A.ShadowTradeJournal.verify(journal)["valid"]
    events = A.ShadowTradeJournal._read_events(journal)
    entries = [e for e in events if e["event_type"] == A.EVIDENCE_EVENT_TYPES["entry"]]
    assert len(entries) == 1
    assert entries[0]["payload"]["branches"]["baseline"]["reason"] == "RESTART_AFTER_ENTRY_WINDOW"


@pytest.mark.parametrize("exit_mode", ["stop", "timebox"])
@pytest.mark.parametrize("interrupt_terminal", [False, True])
def test_real_paired_entry_and_open_lifecycle_guard(rig, monkeypatch, tmp_path, exit_mode, interrupt_terminal):
    class TradeSignalEngine:
        def evaluate(self, *, symbol, rates, current_bar_epoch):
            signal = A.FrozenShadowSignal(
                valid=True, action="PENDING_NEXT_CANDLE_ENTRY",
                reason="FROZEN_BOS_SIGNAL_ARMED", symbol=symbol, timeframe="M15",
                direction="BUY", signal_bar_epoch=current_bar_epoch - 900,
                expected_entry_bar_epoch=current_bar_epoch, stop_loss=90.,
            )
            return SimpleNamespace(
                valid=True, reason="FROZEN_BOS_SIGNAL_ARMED",
                signal_bar_epoch=current_bar_epoch - 900,
                completed_candle_count=len(rates) - 1, frozen_signal=signal,
                pipeline_result=SimpleNamespace(
                    valid=True, bos_detected=True, bos_direction="BULLISH",
                    confluence_valid=True, confluence_signal="BUY",
                    confluence_gate_rejected=False,
                ),
            )
    def collector(**kwargs):
        return A.PairedForwardEvidenceCollector(
            **kwargs, baseline_engine=TradeSignalEngine(), candidate_engine=TradeSignalEngine()
        )
    def open_trade(**kwargs):
        # Synthetic risk/valuation seam: real virtual-position and journal paths,
        # but never query a live broker for sizing in this unit test.
        position = A.VirtualPositionEngine.open_position(
            position_id=kwargs["position_id"], symbol=kwargs["symbol"],
            direction=kwargs["direction"], volume=.01,
            entry_price=kwargs["entry_price"], stop_loss=kwargs["stop_loss"],
            take_profit=kwargs["take_profit"], broker_epoch=kwargs["broker_epoch"],
        )
        A.ShadowTradeJournal.append_event(
            path=kwargs["journal_path"], event_type="POSITION_OPENED",
            position_id=position.position_id, broker_epoch=kwargs["broker_epoch"],
            payload={
                "symbol": position.symbol, "direction": position.direction,
                "volume": position.volume, "entry_price": position.entry_price,
                "stop_loss": position.stop_loss, "take_profit": position.take_profit,
                "initial_risk_price": position.initial_risk_price,
            },
        )
        return SimpleNamespace(valid=True, reason="VIRTUAL_POSITION_OPENED", position=position,
                               real_order_send_allowed=False, order_send_called=False, order_check_called=False)
    monkeypatch.setattr(B, "PairedForwardEvidenceCollector", collector)
    monkeypatch.setattr(A.ShadowTradeEngine, "open_trade", open_trade)
    result = rig.run()
    assert all(s["baseline_virtual_position_open"] and s["candidate_virtual_position_open"]
               for s in result["symbols"])
    recovered = collector(activation=activation(), journal_path=tmp_path / "paired.jsonl")
    assert len(recovered.recover().open_pair_keys) == 2
    for item in result["symbols"]:
        for branch in ("baseline", "candidate"):
            pair_key = tuple(item["pair_key"])
            assert recovered._recover_position(pair_key, branch) is not None
            branch_events = A.ShadowTradeJournal._read_events(recovered.trade_journal_path(pair_key, branch))
            assert sum(e["event_type"] == "POSITION_OPENED" for e in branch_events) == 1
    assert A.ShadowTradeJournal.verify(tmp_path / "paired.jsonl")["valid"]
    captures_before = sum(c[0] == "capture" for c in rig.calls)
    with pytest.raises(RuntimeError, match="lifecycle"):
        rig.run(target=utc(TARGET + 900))
    assert sum(c[0] == "capture" for c in rig.calls) == captures_before

    # The lifecycle coordinator uses real branch journals and settlement logic.
    coordinator = B.LifecycleCoordinator(recovered)
    coordinator.apply_snapshots(tuple(snapshot(s, rig.now) for s in A.SYMBOL_MAP))
    assert len(coordinator.outstanding()) == 4
    monkeypatch.setattr(A.ShadowTradeValuation, "calculate", lambda **_: SimpleNamespace(
        valid=True, reason="SYNTHETIC_VALUATION", pnl_account_currency=-.15,
        real_order_send_allowed=False, order_send_called=False, order_check_called=False,
    ))
    if exit_mode == "timebox":
        rig.now = coordinator.end - 900 + .1
        coordinator.apply_snapshots(tuple(lifecycle_end_snapshot(s, rig.now) for s in A.SYMBOL_MAP))
        assert len(coordinator.outstanding()) == 4
        rig.now = coordinator.end + .1
    def closing_snapshots():
        if exit_mode == "timebox":
            return tuple(lifecycle_end_snapshot(s, rig.now) for s in A.SYMBOL_MAP)
        return tuple(
            replace(snapshot(s, rig.now), bid=85., ask=85.02) for s in A.SYMBOL_MAP
        )
    if interrupt_terminal:
        original_terminal = recovered._append_terminal_unlocked
        def crash_before_terminal(**_):
            raise RuntimeError("synthetic crash after durable position close")
        monkeypatch.setattr(recovered, "_append_terminal_unlocked", crash_before_terminal)
        with pytest.raises(RuntimeError, match="synthetic crash"):
            coordinator.apply_snapshots(closing_snapshots())
        monkeypatch.setattr(recovered, "_append_terminal_unlocked", original_terminal)
        rig.advance(10.)
        recovered = collector(activation=activation(), journal_path=tmp_path / "paired.jsonl")
        coordinator = B.LifecycleCoordinator(recovered)
        coordinator.recover_frozen()
        assert len(coordinator.outstanding()) == 3
    coordinator.apply_snapshots(closing_snapshots())
    assert not coordinator.outstanding()
    assert len(recovered.recover().settled_pair_keys) == 2
    counts = {(p, b): len(recovered._trade_events(p, b))
              for p in recovered.recover().settled_pair_keys for b in ("baseline", "candidate")}
    coordinator.recover_frozen()
    coordinator.finalize_ready()
    assert len(recovered.recover().settled_pair_keys) == 2
    assert counts == {(p, b): len(recovered._trade_events(p, b))
                      for p in recovered.recover().settled_pair_keys for b in ("baseline", "candidate")}


class LifecycleFakeCollector:
    def __init__(self, *, activation, journal_path):
        self.activation = activation
        self.journal_path = journal_path
        self.events = {}
        self.calls = []
        self.hold = False
        self.boundary_offset = 0
        self.missing_boundary = False
        for symbol in A.SYMBOL_MAP:
            pair = (symbol, utc(START))
            self.events[pair, "decision"] = {"payload": {
                "live_mt5_acquisition": snapshot(symbol, TARGET + .1).provenance(),
            }}
            self.events[pair, "entry"] = {"payload": {"branches": {
                "baseline": {"is_actual_trade": True},
                "candidate": {"is_actual_trade": True},
            }}}

    def _events(self):
        return list(self.events.values())

    def _phase_events(self):
        return self.events.copy()

    def recover(self):
        decisions = {p for p, phase in self.events if phase == "decision"}
        entries = {p for p, phase in self.events if phase == "entry"}
        return SimpleNamespace(pending_entry_pair_keys=tuple(sorted(decisions - entries)))

    def resume_pending_entry(self, *, canonical_symbol):
        pair = next(p for p in self.recover().pending_entry_pair_keys if p[0] == canonical_symbol)
        self.calls.append(("resume", pair))
        self.events[pair, "entry"] = {"payload": {"branches": {
            b: {"is_actual_trade": False} for b in ("baseline", "candidate")
        }}}
        return SimpleNamespace(pair_key=pair)

    def update_virtual_trade(self, **kwargs):
        pair, branch = kwargs["pair_key"], kwargs["branch"]
        self.calls.append(("update", pair, branch, kwargs))
        if not self.hold:
            self.events[pair, f"terminal_{branch}"] = {"payload": {}}

    def record_timebox_boundary_authority_if_due(self, **kwargs):
        self.calls.append(("boundary", kwargs["pair_key"]))

    def timebox_boundary_evidence(self, **kwargs):
        if self.missing_boundary:
            raise RuntimeError("missing final-bar boundary authority")
        return self.boundary_offset, "f" * 64

    def timebox_close_virtual_trade(self, **kwargs):
        pair, branch = kwargs["pair_key"], kwargs["branch"]
        self.calls.append(("timebox", pair, branch, kwargs))
        self.events[pair, f"terminal_{branch}"] = {"payload": {}}

    def finalize_settlement(self, *, pair_key):
        self.calls.append(("settle", pair_key))
        self.events[pair_key, "settlement"] = {"payload": {}}


@pytest.fixture
def lifecycle(rig, monkeypatch, tmp_path):
    collector = LifecycleFakeCollector(activation=activation(), journal_path=tmp_path / "paired.jsonl")
    monkeypatch.setattr(B, "PairedForwardEvidenceCollector", lambda **_: collector)
    rig.now = TARGET + .1
    rig.collector = collector
    rig.coordinator = B.LifecycleCoordinator(collector)
    rig.manage = lambda: B.manage_existing_lifecycles(
        activation=collector.activation, repository_root=tmp_path, journal_path=collector.journal_path,
    )
    rig.audit = lambda: A.ShadowTradeJournal._read_events(tmp_path / "paired.jsonl.lifecycle.jsonl")
    return rig


def test_lifecycle_shared_snapshot_once_per_symbol_and_settlement(lifecycle):
    result = lifecycle.manage()
    captures = [c[1] for c in lifecycle.calls if c[0] == "capture"]
    assert captures == list(A.SYMBOL_MAP)
    calls = lifecycle.collector.calls
    assert sum(c[0] == "update" for c in calls) == 4
    assert sum(c[0] == "boundary" for c in calls) == 2
    assert sum(c[0] == "settle" for c in calls) == 2
    assert not lifecycle.writes  # No new decisions.
    assert result["experiment_continuity_verified"] is False
    assert all(e["payload"]["experiment_continuity"] == "UNVERIFIED" for e in lifecycle.audit())
    assert [e["event_type"] for e in lifecycle.audit()] == [
        "LIFECYCLE_RECOVERY_STARTED", "LIFECYCLE_RECOVERY_COMPLETED",
    ]


def test_lifecycle_finalizes_already_terminal_pair_without_capture(lifecycle):
    for pair, branch in lifecycle.coordinator.outstanding():
        lifecycle.collector.events[pair, f"terminal_{branch}"] = {"payload": {}}
    lifecycle.manage()
    assert not any(c[0] == "capture" for c in lifecycle.calls)
    assert sum(c[0] == "settle" for c in lifecycle.collector.calls) == 2
    lifecycle.coordinator.finalize_ready()
    assert sum(c[0] == "settle" for c in lifecycle.collector.calls) == 2


def test_lifecycle_both_no_trade_excluded_from_settlement(lifecycle):
    for (pair, phase), event in lifecycle.collector.events.items():
        if phase == "entry":
            for branch in event["payload"]["branches"].values():
                branch["is_actual_trade"] = False
    lifecycle.manage()
    assert not lifecycle.collector.calls
    assert not any(c[0] == "capture" for c in lifecycle.calls)


def test_lifecycle_recovers_every_pending_entry_without_prices(lifecycle):
    for symbol in A.SYMBOL_MAP:
        del lifecycle.collector.events[(symbol, utc(START)), "entry"]
        lifecycle.collector.events[(symbol, utc(START + 900)), "decision"] = {
            "payload": {"live_mt5_acquisition": snapshot(symbol, TARGET + .1).provenance()},
        }
    lifecycle.manage()
    assert [c[1] for c in lifecycle.collector.calls if c[0] == "resume"] == [
        (s, utc(t)) for s in A.SYMBOL_MAP for t in (START, START + 900)
    ]
    assert not any(c[0] == "capture" for c in lifecycle.calls)


def test_lifecycle_nonprogressing_recovery_fails(lifecycle, monkeypatch):
    del lifecycle.collector.events[("BTCUSD", utc(START)), "entry"]
    monkeypatch.setattr(lifecycle.collector, "resume_pending_entry", lambda **_: None)
    with pytest.raises(RuntimeError, match="no progress"):
        lifecycle.manage()
    assert lifecycle.audit()[-1]["event_type"] == "LIFECYCLE_RECOVERY_FAILED"
    assert not any(c[0] == "capture" for c in lifecycle.calls)


@pytest.mark.parametrize("trigger", ["STOP_LOSS_HIT", "TIMEBOX_MTM_CLOSE"])
def test_lifecycle_frozen_terminal_recovery_precedes_prices(lifecycle, trigger):
    original_authority = snapshot("BTCUSD", TARGET + .1).time_authority()
    frozen = dict(trigger=trigger, bid=88., ask=88.02, point=.01,
                  final_completed_candle={"time": 123}, global_time_authority=original_authority)
    for pair, branch in lifecycle.coordinator.outstanding():
        lifecycle.collector.events[pair, f"terminal_input_{branch}"] = {
            "payload": frozen, "broker_epoch": TARGET + 1,
        }
    lifecycle.manage()
    assert not any(c[0] == "capture" for c in lifecycle.calls)
    kind = "timebox" if trigger == "TIMEBOX_MTM_CLOSE" else "update"
    recovered = [c for c in lifecycle.collector.calls if c[0] == kind]
    assert len(recovered) == 4
    assert all(c[3]["time_authority"] == original_authority for c in recovered)
    assert not lifecycle.coordinator.outstanding()


def test_lifecycle_second_capture_failure_writes_no_updates(lifecycle):
    lifecycle.failure_symbol = "ETHUSD"
    with pytest.raises(RuntimeError, match="acquisition failure"):
        lifecycle.manage()
    assert not lifecycle.collector.calls
    assert lifecycle.audit()[-1]["event_type"] == "LIFECYCLE_RECOVERY_FAILED"
    assert lifecycle.calls[-1][0] == "shutdown"


def test_lifecycle_slow_capture_fails_before_updates(lifecycle):
    lifecycle.capture_delay = 3.
    with pytest.raises(RuntimeError, match="acquisition exceeded"):
        lifecycle.manage()
    assert not lifecycle.collector.calls


def test_lifecycle_no_pre_activation_setup(lifecycle):
    lifecycle.now = START - 1
    with pytest.raises(RuntimeError, match="before activation"):
        lifecycle.manage()
    assert not any(c[0] == "initialize" for c in lifecycle.calls)
    assert not lifecycle.audit()


def test_lifecycle_owns_runner_lease(lifecycle):
    with B.runner_lease(lifecycle.collector.journal_path):
        with pytest.raises(ShadowTradeJournalBusyError):
            lifecycle.manage()
    assert not lifecycle.audit()


def test_lifecycle_rejects_changed_original_broker(lifecycle):
    pair = ("BTCUSD", utc(START))
    lifecycle.collector.events[pair, "decision"]["payload"]["live_mt5_acquisition"]["account_server"] = "Other-Demo"
    with pytest.raises(RuntimeError, match="changed since the decision"):
        lifecycle.manage()
    assert not lifecycle.collector.calls


def test_lifecycle_clock_step_during_capture_fails_before_updates(lifecycle):
    def step(value):
        lifecycle.now += 1.
        return value
    lifecycle.mutate_snapshot = step
    with pytest.raises(RuntimeError, match="clock stepped"):
        lifecycle.manage()
    assert not lifecycle.collector.calls


def test_lifecycle_slow_write_retains_partial_evidence(lifecycle, monkeypatch):
    original = lifecycle.collector.update_virtual_trade
    def delayed(**kwargs):
        original(**kwargs)
        lifecycle.advance(1.5)
    monkeypatch.setattr(lifecycle.collector, "update_virtual_trade", delayed)
    with pytest.raises(RuntimeError, match="writes exceeded"):
        lifecycle.manage()
    assert any(c[0] == "update" for c in lifecycle.collector.calls)
    assert lifecycle.audit()[-1]["event_type"] == "LIFECYCLE_RECOVERY_FAILED"


def test_lifecycle_polls_held_positions_then_stops(lifecycle, monkeypatch):
    original = lifecycle.collector.update_virtual_trade
    lifecycle.collector.hold = True
    def close_second_poll(**kwargs):
        if lifecycle.now >= TARGET + 1.1:
            lifecycle.collector.hold = False
        original(**kwargs)
    monkeypatch.setattr(lifecycle.collector, "update_virtual_trade", close_second_poll)
    lifecycle.manage()
    captures = [c for c in lifecycle.calls if c[0] == "capture"]
    assert len(captures) == 4
    assert captures[2][2] - captures[0][2] == pytest.approx(1.)
    assert sum(c[0] == "initialize" for c in lifecycle.calls) == 1


def lifecycle_end_snapshot(symbol, now):
    # Shift the synthetic fixture to any M15 bar, including the exclusive end.
    base = snapshot(symbol, TARGET + .1)
    current = int(now // 900) * 900
    shift = current - TARGET
    frozen = tuple(replace(rate, time=rate.time + shift) for rate in base.rates)
    authority = A.GlobalTimeAuthority().build(
        utc_epoch_before_tick=now, utc_epoch_after_tick=now,
        tick_epoch=int(now), current_bar_epoch=current,
    )
    from dataclasses import asdict
    provenance = base.provenance()
    provenance.update(tick_epoch=int(now), current_bar_epoch=current,
                      rates_sha256=A._canonical_sha256([asdict(r) for r in frozen]),
                      time_authority_sha256=A._canonical_sha256(authority))
    return replace(base, rates=frozen, tick_epoch=int(now), current_bar_epoch=current,
                   time_authority_json=A._canonical_json_bytes(authority).decode(),
                   provenance_json=A._canonical_json_bytes(provenance).decode())


def test_lifecycle_end_uses_final_candle_and_skips_ordinary_updates(lifecycle):
    lifecycle.now = lifecycle.coordinator.end + .1
    values = tuple(lifecycle_end_snapshot(s, lifecycle.now) for s in A.SYMBOL_MAP)
    lifecycle.coordinator.apply_snapshots(values)
    calls = lifecycle.collector.calls
    assert not any(c[0] in {"update", "boundary"} for c in calls)
    closed = [c for c in calls if c[0] == "timebox"]
    assert len(closed) == 4
    assert all(c[3]["final_completed_candle"]["time"] == lifecycle.coordinator.end - 900 for c in closed)
    assert sum(c[0] == "settle" for c in calls) == 2


def test_lifecycle_already_terminal_branch_is_not_timeboxed_again(lifecycle):
    pair = ("BTCUSD", utc(START))
    lifecycle.collector.events[pair, "terminal_baseline"] = {"payload": {}}
    lifecycle.now = lifecycle.coordinator.end + .1
    lifecycle.coordinator.apply_snapshots(tuple(lifecycle_end_snapshot(s, lifecycle.now) for s in A.SYMBOL_MAP))
    closed = [c for c in lifecycle.collector.calls if c[0] == "timebox"]
    assert len(closed) == 3
    assert not any(c[1:3] == (pair, "baseline") for c in closed)


@pytest.mark.parametrize("fault", ["missing_boundary", "missing_candle", "stale_tick"])
def test_lifecycle_end_preflight_fails_without_terminal_writes(lifecycle, fault):
    lifecycle.now = lifecycle.coordinator.end + .1
    epoch = lifecycle.now
    if fault == "missing_boundary":
        lifecycle.collector.missing_boundary = True
    elif fault == "missing_candle":
        lifecycle.collector.boundary_offset = 90000
    else:
        epoch = lifecycle.coordinator.end - .1
    with pytest.raises(RuntimeError):
        lifecycle.coordinator.apply_snapshots(tuple(lifecycle_end_snapshot(s, epoch) for s in A.SYMBOL_MAP))
    assert not lifecycle.collector.calls


def test_lifecycle_command_requires_public_verification(monkeypatch, capsys):
    args = R.parser().parse_args([
        "manage-existing-lifecycles", "--no-forward-outcome-access-verified",
        "--manifest-commit-sha", "b" * 40, "--manifest-publication-pr-number", "99",
    ])
    calls = []
    monkeypatch.setattr(R, "verified_context", lambda _: calls.append("verify") or activation())
    monkeypatch.setattr(R, "manage_existing_lifecycles", lambda **_: calls.append("manage") or {"ok": True})
    args.handler(args)
    assert calls == ["verify", "manage"]
    assert '"ok": true' in capsys.readouterr().out


@pytest.mark.parametrize("fault", [None, "server", "currency", "build", "disconnected", "account_missing"])
def test_session_recovery_context_check_never_reads_prices(monkeypatch, fault):
    account = SimpleNamespace(server="Synthetic-Demo", currency="USD")
    terminal = SimpleNamespace(connected=True, build=5000)
    if fault in {"server", "currency"}:
        setattr(account, fault, "CHANGED")
    elif fault == "build":
        terminal.build += 1
    elif fault == "disconnected":
        terminal.connected = False
    elif fault == "account_missing":
        account = None
    calls = []
    # Price functions are deliberately absent: context checking may not call them.
    monkeypatch.setitem(sys.modules, "MetaTrader5", SimpleNamespace(
        initialize=lambda **_: True, symbol_select=lambda *_: True,
        shutdown=lambda: calls.append("shutdown"),
        terminal_info=lambda: terminal, account_info=lambda: account,
    ))
    session = A.LiveMt5ReadOnlySession()
    with session:
        if fault is None:
            session.require_context(snapshot("BTCUSD", TARGET + .1).provenance())
        else:
            with pytest.raises(RuntimeError):
                session.require_context(snapshot("BTCUSD", TARGET + .1).provenance())
    assert calls == ["shutdown"]
    with pytest.raises(RuntimeError, match="not active"):
        session.require_context({})
