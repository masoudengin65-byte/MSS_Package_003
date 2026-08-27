from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import mss.analysis.sprint93_paired_forward_activation as A
from mss.analysis.sprint93_confluence_gate_v2_preregistration import (
    Sprint93ConfluenceGateV2Preregistration as C,
)
from mss.analysis.virtual_position_engine import VirtualPositionEngine


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "integration_tests/run_sprint93_2b_paired_forward_activation.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("sprint93_2b_runner", RUNNER)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
R = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(R)


MERGE_SHA = "a" * 40
MANIFEST_COMMIT_SHA = "b" * 40
MERGED_AT = "2026-08-25T10:00:01Z"
START_UTC, END_UTC = C.activation_window(MERGED_AT)
CREATED_AT = "2026-08-25T10:01:00Z"
COMMITTED_AT = "2026-08-25T10:02:00Z"
PUSHED_AT = "2026-08-25T10:03:00Z"
TEST_NOW_EPOCH = 0.0


def public_metadata(state: str = "MERGED") -> dict[str, object]:
    return {
        "url": "https://github.com/masoudengin65-byte/MSS_Package_003/pull/5",
        "number": 5,
        "state": state,
        "mergedAt": MERGED_AT,
        "merge_commit_sha": MERGE_SHA,
        "repository_full_name": "masoudengin65-byte/MSS_Package_003",
        "base_ref_name": "main",
        "head_sha": "d" * 40,
        "metadata_source": "GITHUB_AUTHORITATIVE",
    }


def publication_metadata() -> dict[str, object]:
    return {
        "manifest_committed_at_utc": COMMITTED_AT,
        "manifest_publicly_pushed_at_utc": PUSHED_AT,
        "manifest_commit_sha": MANIFEST_COMMIT_SHA,
    }


def fake_identity() -> tuple[tuple[str, str], ...]:
    paths = set(C.REQUIRED_STRATEGY_COMPONENT_FILES)
    paths.update(A.EXECUTION_ROOT_PATHS)
    paths.update(C.PACKAGE_INITIALIZER_FILES)
    return tuple(
        (path, hashlib.sha256(path.encode("utf-8")).hexdigest())
        for path in sorted(paths)
    )


def patch_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(A, "execution_identity", lambda **_kwargs: fake_identity())
    monkeypatch.setattr(
        A,
        "observed_runtime_versions",
        lambda: {"python_version": "3.13.7", "numpy_version": "2.3.2"},
    )


def patch_verification_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(A, "_git_is_ancestor", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        A, "_execution_worktree_clean", lambda *_args, **_kwargs: True
    )


def manifest(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    patch_identity(monkeypatch)
    return A.build_activation_manifest_after_merge(
        repository_root=Path.cwd(),
        public_pr_metadata=public_metadata(),
        manifest_created_at_utc=CREATED_AT,
        no_forward_outcome_access_verified=True,
    )


def activation() -> A.VerifiedActivation:
    return A.VerifiedActivation(
        manifest_sha256="c" * 64,
        activation_merge_commit_sha=MERGE_SHA,
        first_eligible_m15_open_utc=START_UTC,
        exclusive_45_day_end_utc=END_UTC,
        python_version="3.13.7",
        numpy_version="2.3.2",
        execution_identity=fake_identity(),
        _verification_marker=A._VERIFIED_ACTIVATION_MARKER,
    )


def utc_epoch(value: str) -> int:
    return int(datetime.fromisoformat(value[:-1] + "+00:00").timestamp())


TEST_NOW_EPOCH = utc_epoch(START_UTC) + 901


@pytest.fixture(autouse=True)
def stable_authority_clock(monkeypatch):
    monkeypatch.setattr(A, "_utc_now_epoch", lambda: TEST_NOW_EPOCH)


def time_authority(
    offset: int = 0,
    *,
    current_bar_epoch: int | None = None,
    tick_epoch: int | None = None,
) -> dict[str, object]:
    global TEST_NOW_EPOCH
    current_bar_epoch = (
        utc_epoch(START_UTC) + offset + 900
        if current_bar_epoch is None
        else int(current_bar_epoch)
    )
    tick_epoch = current_bar_epoch + 1 if tick_epoch is None else int(tick_epoch)
    midpoint = float(tick_epoch - offset)
    TEST_NOW_EPOCH = midpoint
    return A.GlobalTimeAuthority().build(
        utc_epoch_before_tick=midpoint - 0.05,
        utc_epoch_after_tick=midpoint + 0.05,
        tick_epoch=tick_epoch,
        current_bar_epoch=current_bar_epoch,
    )


def rates(signal_epoch: int, *, close: float = 100.5) -> list[dict[str, object]]:
    first_epoch = signal_epoch - (A.LIVE_RATE_COUNT - 2) * 900
    result = []
    for index in range(A.LIVE_RATE_COUNT):
        epoch = first_epoch + index * 900
        is_signal = epoch == signal_epoch
        result.append(
            {
                "time": epoch,
                "open": 100.0,
                "high": 101.5,
                "low": 99.0,
                "close": close if is_signal else 101.0,
                "tick_volume": 10,
                "spread": 2,
                "real_volume": 0,
            }
        )
    return result


def live_snapshot(
    *,
    signal_epoch: int,
    snapshot: list[dict[str, object]] | None = None,
    authority: dict[str, object] | None = None,
) -> A.LiveMt5Snapshot:
    current_bar_epoch = signal_epoch + 900
    raw_rates = snapshot or rates(signal_epoch)
    frozen = A._freeze_rates(raw_rates, current_bar_epoch=current_bar_epoch)
    authority = authority or time_authority(
        current_bar_epoch=current_bar_epoch,
        tick_epoch=current_bar_epoch + 1,
    )
    records = [asdict(rate) for rate in frozen]
    provenance = {
        "schema_version": A.LIVE_ACQUISITION_VERSION,
        "source": "DIRECT_LIVE_MT5_READ_ONLY",
        "canonical_symbol": "BTCUSD",
        "broker_symbol": A.SYMBOL_MAP["BTCUSD"],
        "timeframe": A.TIMEFRAME,
        "tick_epoch": authority["observation"]["mt5_raw_tick_epoch"],
        "current_bar_epoch": current_bar_epoch,
        "rate_record_count": len(records),
        "rates_sha256": A._canonical_sha256(records),
        "time_authority_sha256": A._canonical_sha256(authority),
        "read_only": True,
        "real_order_send_allowed": False,
        "order_send_called": False,
        "order_check_called": False,
    }
    return A.LiveMt5Snapshot(
        canonical_symbol="BTCUSD",
        broker_symbol=A.SYMBOL_MAP["BTCUSD"],
        current_bar_epoch=current_bar_epoch,
        tick_epoch=int(authority["observation"]["mt5_raw_tick_epoch"]),
        bid=100.0,
        ask=100.5,
        balance=10_000.0,
        point=0.01,
        rates=frozen,
        time_authority_json=A._canonical_json_bytes(authority).decode("utf-8"),
        provenance_json=A._canonical_json_bytes(provenance).decode("utf-8"),
        _verification_marker=A._LIVE_MT5_SNAPSHOT_MARKER,
    )


@dataclass(frozen=True)
class FakeSignal:
    valid: bool
    reason: str
    real_order_send_allowed: bool = False


class FakeEngine:
    def __init__(self, *, trade: bool, rejected: bool = False) -> None:
        self.trade = trade
        self.rejected = rejected
        self.rate_object_ids: list[int] = []
        self.calls = 0

    def evaluate(self, *, symbol: str, rates: object, current_bar_epoch: int):
        self.calls += 1
        self.rate_object_ids.append(id(rates))
        return SimpleNamespace(
            valid=True,
            reason="FROZEN_BOS_SIGNAL_ARMED" if self.trade else "NO_BOS",
            signal_bar_epoch=current_bar_epoch - 900,
            completed_candle_count=len(rates) - 1,
            frozen_signal=FakeSignal(
                valid=self.trade,
                reason="FROZEN_BOS_SIGNAL_ARMED" if self.trade else "NO_BOS",
            ),
            pipeline_result=SimpleNamespace(
                valid=True,
                bos_detected=self.trade,
                bos_direction="BULLISH" if self.trade else "",
                confluence_valid=not self.rejected,
                confluence_signal="BUY" if not self.rejected else "",
                confluence_gate_rejected=self.rejected,
            ),
        )


def collector(
    tmp_path: Path,
    *,
    baseline_trade: bool = True,
    candidate_trade: bool = False,
    candidate_rejected: bool = True,
) -> tuple[A.PairedForwardEvidenceCollector, FakeEngine, FakeEngine]:
    baseline = FakeEngine(trade=baseline_trade)
    candidate = FakeEngine(trade=candidate_trade, rejected=candidate_rejected)
    result = A.PairedForwardEvidenceCollector(
        activation=activation(),
        journal_path=tmp_path / "paired.jsonl",
        baseline_engine=baseline,
        candidate_engine=candidate,
    )
    return result, baseline, candidate


def collect_start(
    value: A.PairedForwardEvidenceCollector,
    *,
    snapshot: list[dict[str, object]] | None = None,
) -> A.PairedDecisionResult:
    signal_epoch = utc_epoch(START_UTC)
    return value.collect_decision(
        snapshot=live_snapshot(
            signal_epoch=signal_epoch,
            snapshot=snapshot,
        )
    )


def test_builds_exact_frozen_manifest_after_merged_pr(monkeypatch):
    result = manifest(monkeypatch)
    assert tuple(result) == C.ACTIVATION_MANIFEST_REQUIRED_FIELDS
    assert result["activation_merge_commit_sha"] == MERGE_SHA
    assert result["computed_first_eligible_m15_open_utc"] == START_UTC
    assert result["computed_exclusive_45_day_end_utc"] == END_UTC
    assert result["python_version"] == "3.13.7"
    assert result["numpy_version"] == "2.3.2"
    assert result["paired_executor_identity"]["path"] == A.PAIRED_EXECUTOR_PATH
    baseline_paths = {
        item["path"]
        for item in result["baseline_strategy_identity"]["path_git_blob_sha256"]
    }
    candidate_paths = {
        item["path"]
        for item in result["candidate_strategy_identity"]["path_git_blob_sha256"]
    }
    candidate_path = "src/mss/analysis/confluence_gated_smart_money_pipeline.py"
    assert candidate_path not in baseline_paths
    assert candidate_path in candidate_paths
    assert result["journal_schema_identity"]["schema_identifier"].startswith(
        "MSS_SPRINT92H14_2_SHADOW_TRADE_JOURNAL"
    )
    universe = result["complete_transitive_execution_file_identity"]
    assert [item["path"] for item in universe] == sorted(
        item["path"] for item in universe
    )
    assert result["write_once"] is True


@pytest.mark.parametrize(
    ("state", "created", "message"),
    [
        ("OPEN", CREATED_AT, "already be merged"),
        ("MERGED", MERGED_AT, "after merge"),
        ("MERGED", START_UTC, "before the activation boundary"),
    ],
)
def test_manifest_creation_cannot_be_premerge_or_retroactive(
    monkeypatch, state, created, message
):
    patch_identity(monkeypatch)
    with pytest.raises(RuntimeError, match=message):
        A.build_activation_manifest_after_merge(
            repository_root=Path.cwd(),
            public_pr_metadata=public_metadata(state),
            manifest_created_at_utc=created,
            no_forward_outcome_access_verified=True,
        )


def test_manifest_requires_external_no_outcome_access_proof(monkeypatch):
    patch_identity(monkeypatch)
    with pytest.raises(RuntimeError, match="no-forward-outcome-access"):
        A.build_activation_manifest_after_merge(
            repository_root=Path.cwd(),
            public_pr_metadata=public_metadata(),
            manifest_created_at_utc=CREATED_AT,
            no_forward_outcome_access_verified=False,
        )


def test_manifest_is_exclusive_write_once_and_preserves_existing_file(
    monkeypatch, tmp_path
):
    value = manifest(monkeypatch)
    path = A.activation_manifest_path(tmp_path)
    digest = A.create_activation_manifest_once(
        repository_root=tmp_path, manifest=value
    )
    before = path.read_bytes()
    stat = path.stat()
    assert digest == hashlib.sha256(before).hexdigest()
    with pytest.raises(FileExistsError):
        A.create_activation_manifest_once(repository_root=tmp_path, manifest=value)
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == stat.st_mtime_ns


def test_verified_activation_binds_published_manifest_runtime_and_source(
    monkeypatch, tmp_path
):
    value = manifest(monkeypatch)
    path = A.activation_manifest_path(tmp_path)
    A.create_activation_manifest_once(repository_root=tmp_path, manifest=value)
    canonical = path.read_bytes()
    patch_verification_environment(monkeypatch)
    monkeypatch.setattr(
        A,
        "_resolve_commit",
        lambda _root, revision: MANIFEST_COMMIT_SHA if revision == "HEAD" else revision,
    )
    monkeypatch.setattr(
        A,
        "_git_blob",
        lambda _root, _commit, blob_path: canonical
        if blob_path == A.DEFAULT_MANIFEST_RELATIVE_PATH
        else b"unused",
    )
    context = A.verify_published_activation_manifest(
        manifest_path=path,
        repository_root=tmp_path,
        public_pr_metadata=public_metadata(),
        publication_metadata=publication_metadata(),
        no_forward_outcome_access_verified=True,
    )
    assert context.activation_merge_commit_sha == MERGE_SHA
    assert context.first_eligible_m15_open_utc == START_UTC
    assert context.execution_identity == fake_identity()
    with pytest.raises(FrozenInstanceError):
        context.activation_merge_commit_sha = "f" * 40


def test_verified_activation_rejects_runtime_or_source_mutation(monkeypatch, tmp_path):
    value = manifest(monkeypatch)
    path = A.activation_manifest_path(tmp_path)
    A.create_activation_manifest_once(repository_root=tmp_path, manifest=value)
    canonical = path.read_bytes()
    patch_verification_environment(monkeypatch)
    monkeypatch.setattr(
        A,
        "_resolve_commit",
        lambda _root, revision: MANIFEST_COMMIT_SHA if revision == "HEAD" else revision,
    )
    monkeypatch.setattr(A, "_git_blob", lambda *_args, **_kwargs: canonical)
    identities = iter(
        (
            fake_identity(),
            fake_identity(),
            (("different.py", "f" * 64),),
        )
    )
    monkeypatch.setattr(A, "execution_identity", lambda **_kwargs: next(identities))
    with pytest.raises(RuntimeError, match="running execution source differs"):
        A.verify_published_activation_manifest(
            manifest_path=path,
            repository_root=tmp_path,
            public_pr_metadata=public_metadata(),
            publication_metadata=publication_metadata(),
            no_forward_outcome_access_verified=True,
        )

    patch_identity(monkeypatch)
    monkeypatch.setattr(
        A,
        "observed_runtime_versions",
        lambda: {"python_version": "different", "numpy_version": "2.3.2"},
    )
    with pytest.raises(RuntimeError, match="runtime versions"):
        A.verify_published_activation_manifest(
            manifest_path=path,
            repository_root=tmp_path,
            public_pr_metadata=public_metadata(),
            publication_metadata=publication_metadata(),
            no_forward_outcome_access_verified=True,
        )


def test_boundary_accepts_exact_start_and_rejects_before_and_end(tmp_path):
    value, baseline, candidate = collector(tmp_path)
    before = (
        datetime.fromisoformat(START_UTC[:-1] + "+00:00")
        - timedelta(minutes=15)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(RuntimeError, match="pre-activation"):
        value.collect_decision(
            snapshot=live_snapshot(signal_epoch=utc_epoch(before)),
        )
    with pytest.raises(RuntimeError, match="exclusive experiment end"):
        value.collect_decision(
            snapshot=live_snapshot(signal_epoch=utc_epoch(END_UTC)),
        )
    result = collect_start(value)
    assert result.write.appended is True
    assert baseline.calls == candidate.calls == 1


def test_final_signal_cannot_create_entry_at_exclusive_end(tmp_path):
    value, baseline, candidate = collector(tmp_path)
    final_signal = (
        datetime.fromisoformat(END_UTC[:-1] + "+00:00")
        - timedelta(minutes=15)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(RuntimeError, match="new entries are prohibited"):
        value.collect_decision(
            snapshot=live_snapshot(
                signal_epoch=utc_epoch(final_signal),
                authority=time_authority(
                current_bar_epoch=utc_epoch(END_UTC),
                ),
            )
        )
    assert baseline.calls == candidate.calls == 0


def test_identical_immutable_snapshot_is_supplied_to_both_branches(tmp_path):
    value, baseline, candidate = collector(tmp_path)
    result = collect_start(value)
    assert baseline.rate_object_ids == candidate.rate_object_ids
    assert result.baseline_decision_identity == "BASELINE_TRADE"
    assert result.candidate_decision_identity == "REJECTED_CANDIDATE"
    event = json.loads((tmp_path / "paired.jsonl").read_text(encoding="utf-8"))
    branches = event["payload"]["branches"]
    assert branches["baseline"]["input_snapshot_sha256"] == (
        branches["candidate"]["input_snapshot_sha256"]
    )
    assert branches["candidate"]["decision_identity"] == "REJECTED_CANDIDATE"
    assert event["payload"]["safety"]["real_order_send_allowed"] is False


def test_exact_duplicate_is_noop_and_conflicting_snapshot_fails(tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    first = collect_start(value)
    before = (tmp_path / "paired.jsonl").read_bytes()
    repeated = collect_start(value)
    assert first.write.appended is True
    assert repeated.write.appended is False
    assert repeated.write.event_sha256 == first.write.event_sha256
    assert (tmp_path / "paired.jsonl").read_bytes() == before

    changed = rates(utc_epoch(START_UTC), close=100.75)
    with pytest.raises(RuntimeError, match="conflicting duplicate"):
        collect_start(value, snapshot=changed)
    assert (tmp_path / "paired.jsonl").read_bytes() == before


def test_restart_recovers_pending_and_prevents_duplicate(tmp_path):
    first, _baseline, _candidate = collector(tmp_path)
    collect_start(first)
    restarted, _baseline2, _candidate2 = collector(tmp_path)
    state = restarted.recover()
    assert state.pending_entry_pair_keys == (("BTCUSD", START_UTC),)
    repeated = collect_start(restarted)
    assert repeated.write.appended is False
    assert restarted.recover().decision_pair_keys == (("BTCUSD", START_UTC),)


def test_corrupt_or_truncated_journal_blocks_restart(tmp_path):
    path = tmp_path / "paired.jsonl"
    path.write_bytes(b'{"truncated":')
    with pytest.raises(RuntimeError, match="INVALID_JOURNAL_JSON"):
        A.PairedForwardEvidenceCollector(
            activation=activation(),
            journal_path=path,
            baseline_engine=FakeEngine(trade=True),
            candidate_engine=FakeEngine(trade=False, rejected=True),
        )


def test_entry_and_settlement_keep_rejection_and_actual_zero_r_distinct(tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    entry = value.record_entry_outcome(
        pair_key=decision.pair_key,
        baseline=A.BranchEntryOutcome(
            True, "VIRTUAL_POSITION_OPENED", decision.baseline_position_id
        ),
        candidate=A.BranchEntryOutcome(False, "REJECTED_CANDIDATE"),
        entry_broker_epoch=utc_epoch(START_UTC) + 900,
        time_authority=time_authority(),
    )
    assert entry.appended is True
    settlement = value._record_settlement(
        pair_key=decision.pair_key,
        baseline=A.BranchSettlement(True, 0.0, "2026-08-26T11:00:00Z"),
        candidate=A.BranchSettlement(False, None, None),
        settlement_broker_epoch=utc_epoch("2026-08-26T11:00:00Z"),
        terminal_event_sha256={"baseline": "b" * 64, "candidate": "c" * 64},
        _lock_held=False,
    )
    assert settlement.appended is True
    events = [
        json.loads(line)
        for line in (tmp_path / "paired.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    entry_payload = events[1]["payload"]
    settled_payload = events[2]["payload"]
    assert entry_payload["branches"]["candidate"]["entry_identity"] == (
        "CANDIDATE_NO_TRADE"
    )
    assert settled_payload["baseline_member"] == {
        "record_type": "BASELINE_ACTUAL_TRADE",
        "actual_trade_net_r": 0.0,
        "terminal_settlement_utc": "2026-08-26T11:00:00Z",
    }
    assert settled_payload["candidate_member"]["record_type"] == "CANDIDATE_NO_TRADE"
    assert settled_payload["actual_zero_r"] == {"baseline": True, "candidate": False}


def test_both_no_trade_observation_is_not_an_evaluation_pair(tmp_path):
    value, _baseline, _candidate = collector(
        tmp_path,
        baseline_trade=False,
        candidate_trade=False,
        candidate_rejected=False,
    )
    decision = collect_start(value)
    value.record_entry_outcome(
        pair_key=decision.pair_key,
        baseline=A.BranchEntryOutcome(False, "BASELINE_NO_TRADE"),
        candidate=A.BranchEntryOutcome(False, "CANDIDATE_NO_TRADE"),
        entry_broker_epoch=utc_epoch(START_UTC) + 900,
        time_authority=time_authority(),
    )
    with pytest.raises(RuntimeError, match="both-no-trade observations"):
        value.finalize_settlement(pair_key=decision.pair_key)


def test_candidate_rejection_can_never_open_position(tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    with pytest.raises(RuntimeError, match="no-trade decision cannot open"):
        value.record_entry_outcome(
            pair_key=decision.pair_key,
            baseline=A.BranchEntryOutcome(
                True, "OPEN", decision.baseline_position_id
            ),
            candidate=A.BranchEntryOutcome(
                True, "OPEN", decision.candidate_position_id
            ),
            entry_broker_epoch=utc_epoch(START_UTC) + 900,
            time_authority=time_authority(),
        )


def test_entry_and_settlement_are_duplicate_safe_across_restart(tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    arguments = {
        "pair_key": decision.pair_key,
        "baseline": A.BranchEntryOutcome(
            True, "OPEN", decision.baseline_position_id
        ),
        "candidate": A.BranchEntryOutcome(False, "REJECTED_CANDIDATE"),
        "entry_broker_epoch": utc_epoch(START_UTC) + 900,
        "time_authority": time_authority(),
    }
    assert value.record_entry_outcome(**arguments).appended is True
    restarted, _baseline2, _candidate2 = collector(tmp_path)
    assert restarted.record_entry_outcome(**arguments).appended is False
    settlement_arguments = {
        "pair_key": decision.pair_key,
        "baseline": A.BranchSettlement(True, -0.5, "2026-08-26T12:00:00Z"),
        "candidate": A.BranchSettlement(False, None, None),
        "settlement_broker_epoch": utc_epoch("2026-08-26T12:00:00Z"),
        "terminal_event_sha256": {"baseline": "b" * 64, "candidate": "c" * 64},
        "_lock_held": False,
    }
    assert restarted._record_settlement(**settlement_arguments).appended is True
    final, _baseline3, _candidate3 = collector(tmp_path)
    assert final._record_settlement(**settlement_arguments).appended is False
    assert final.recover().settled_pair_keys == (("BTCUSD", START_UTC),)


def test_timebox_uses_frozen_final_candle_and_virtual_valuation(monkeypatch, tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    position = VirtualPositionEngine.open_position(
        position_id="base-1",
        symbol="BITCOIN",
        direction="BUY",
        volume=0.01,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        broker_epoch=utc_epoch(START_UTC) + 900,
    )
    monkeypatch.setattr(
        A.ShadowTradeValuation,
        "calculate",
        lambda **_kwargs: SimpleNamespace(
            valid=True,
            reason="VALUED",
            pnl_account_currency=1.0,
            real_order_send_allowed=False,
            order_send_called=False,
            order_check_called=False,
        ),
    )
    final_open = (
        datetime.fromisoformat(END_UTC[:-1] + "+00:00")
        - timedelta(minutes=15)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = value.timebox_close(
        position=position,
        final_completed_candle_open_utc=final_open,
        close_broker_epoch=utc_epoch(END_UTC),
        bid=105.0,
        ask=105.5,
        time_authority=time_authority(
            current_bar_epoch=utc_epoch(END_UTC),
            tick_epoch=utc_epoch(END_UTC),
        ),
    )
    assert result.closed_position.status == "CLOSED"
    assert result.closed_position.exit_reason == "TIMEBOX_MTM_CLOSE"
    assert result.settlement.timebox_mtm is True
    assert result.settlement.settlement_utc == END_UTC


def test_real_order_and_production_enablement_are_hard_prohibited(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError, match="shadow-only"):
        A.PairedForwardEvidenceCollector(
            activation=activation(),
            journal_path=tmp_path / "paired.jsonl",
            real_order_send_allowed=True,
        )
    with pytest.raises(RuntimeError, match="shadow-only"):
        A.PairedForwardEvidenceCollector(
            activation=activation(),
            journal_path=tmp_path / "paired.jsonl",
            production_execution_enabled=True,
        )

    calls = {"send": 0, "check": 0}

    def forbidden_send(*_args, **_kwargs):
        calls["send"] += 1
        raise AssertionError("real order send called")

    def forbidden_check(*_args, **_kwargs):
        calls["check"] += 1
        raise AssertionError("real order check called")

    import MetaTrader5 as mt5

    monkeypatch.setattr(mt5, "order_send", forbidden_send)
    monkeypatch.setattr(mt5, "order_check", forbidden_check)
    value, _baseline, _candidate = collector(tmp_path)
    collect_start(value)
    assert calls == {"send": 0, "check": 0}
    assert A.verify_package_safety(Path(A.__file__)) is True


def test_unconfirmed_or_invalid_time_authority_fails_before_strategy(tmp_path):
    value, baseline, candidate = collector(tmp_path)
    authority = time_authority()
    authority["time_authority"]["confirmed"] = False
    with pytest.raises(RuntimeError, match="must be confirmed"):
        value.collect_decision(
            snapshot=live_snapshot(
                signal_epoch=utc_epoch(START_UTC),
                authority=authority,
            )
        )
    assert baseline.calls == candidate.calls == 0


def test_time_authority_is_rebuilt_from_raw_observations(tmp_path):
    value, baseline, candidate = collector(tmp_path)
    authority = time_authority()
    authority["observation"]["detected_broker_offset_seconds"] = 900
    with pytest.raises(RuntimeError, match="derived claims differ"):
        value.collect_decision(
            snapshot=live_snapshot(
                signal_epoch=utc_epoch(START_UTC),
                authority=authority,
            )
        )
    assert baseline.calls == candidate.calls == 0


def test_late_live_observation_is_rejected_before_strategy_or_journal(tmp_path):
    value, baseline, candidate = collector(tmp_path)
    signal_epoch = utc_epoch(START_UTC)
    current_bar_epoch = signal_epoch + A.TIMEFRAME_SECONDS
    authority = time_authority(
        current_bar_epoch=current_bar_epoch,
        tick_epoch=(
            current_bar_epoch + A.MAX_ENTRY_OBSERVATION_DELAY_SECONDS + 1
        ),
    )
    with pytest.raises(RuntimeError, match="next-candle entry window"):
        value.collect_decision(
            snapshot=live_snapshot(
                signal_epoch=signal_epoch,
                authority=authority,
            )
        )
    assert baseline.calls == candidate.calls == 0
    assert not (tmp_path / "paired.jsonl").exists()


def test_quiet_market_cannot_hide_late_acquisition_behind_early_tick(tmp_path):
    global TEST_NOW_EPOCH
    value, baseline, candidate = collector(tmp_path)
    signal_epoch = utc_epoch(START_UTC)
    current_bar_epoch = signal_epoch + A.TIMEFRAME_SECONDS
    acquisition_midpoint = current_bar_epoch + 100.0
    authority = A.GlobalTimeAuthority().build(
        utc_epoch_before_tick=acquisition_midpoint - 0.05,
        utc_epoch_after_tick=acquisition_midpoint + 0.05,
        tick_epoch=current_bar_epoch + A.MAX_ENTRY_OBSERVATION_DELAY_SECONDS,
        current_bar_epoch=current_bar_epoch,
    )
    TEST_NOW_EPOCH = acquisition_midpoint
    with pytest.raises(RuntimeError, match="next-candle entry window"):
        value.collect_decision(
            snapshot=live_snapshot(
                signal_epoch=signal_epoch,
                authority=authority,
            )
        )
    assert baseline.calls == candidate.calls == 0
    assert not (tmp_path / "paired.jsonl").exists()


def test_frozen_symbol_and_event_mappings_reject_runtime_mutation():
    with pytest.raises(TypeError):
        A.SYMBOL_MAP["BTCUSD"] = "FORGED"
    with pytest.raises(TypeError):
        A.EVIDENCE_EVENT_TYPES["decision"] = "FORGED"


def test_entry_authority_mismatch_propagates_instead_of_recording_no_trade(tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    frozen = time_authority()
    observation = frozen["observation"]
    different = A.GlobalTimeAuthority().build(
        utc_epoch_before_tick=observation["utc_epoch_before_tick"],
        utc_epoch_after_tick=observation["utc_epoch_after_tick"],
        tick_epoch=observation["mt5_raw_tick_epoch"],
        current_bar_epoch=observation["mt5_raw_current_m15_bar_epoch"],
        previous_broker_offset_seconds=0,
    )
    with pytest.raises(RuntimeError, match="same frozen time-authority snapshot"):
        value.open_virtual_entries(
            pair_key=decision.pair_key,
            balance=10_000.0,
            point=0.01,
            time_authority=different,
        )
    assert value.recover().pending_entry_pair_keys == (decision.pair_key,)


def test_stale_matching_entry_authority_records_restart_no_trade(tmp_path):
    global TEST_NOW_EPOCH
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    frozen = value._event_for(decision.pair_key, "decision")["payload"][
        "global_time_authority"
    ]
    TEST_NOW_EPOCH += A.GlobalTimeAuthority.MAX_TICK_RESIDUAL_SECONDS + 1
    result = value.open_virtual_entries(
        pair_key=decision.pair_key,
        balance=10_000.0,
        point=0.01,
        time_authority=frozen,
    )
    assert result.baseline_position is None
    assert result.candidate_position is None
    event = value._event_for(decision.pair_key, "entry")
    assert event["payload"]["branches"]["baseline"]["reason"] == (
        "RESTART_AFTER_ENTRY_WINDOW"
    )


def test_stale_restart_completes_both_branches_from_frozen_entry_intent(
    monkeypatch, tmp_path
):
    global TEST_NOW_EPOCH

    class TradeEngine:
        def evaluate(self, *, symbol, rates, current_bar_epoch):
            signal = A.FrozenShadowSignal(
                valid=True,
                action="PENDING_NEXT_CANDLE_ENTRY",
                reason="FROZEN_BOS_SIGNAL_ARMED",
                symbol=symbol,
                timeframe=A.TIMEFRAME,
                direction="BUY",
                signal_bar_epoch=current_bar_epoch - A.TIMEFRAME_SECONDS,
                expected_entry_bar_epoch=current_bar_epoch,
                stop_loss=90.0,
            )
            return SimpleNamespace(
                valid=True,
                reason="FROZEN_BOS_SIGNAL_ARMED",
                signal_bar_epoch=current_bar_epoch - A.TIMEFRAME_SECONDS,
                completed_candle_count=len(rates) - 1,
                frozen_signal=signal,
                pipeline_result=SimpleNamespace(
                    valid=True,
                    bos_detected=True,
                    bos_direction="BULLISH",
                    confluence_valid=True,
                    confluence_signal="BUY",
                    confluence_gate_rejected=False,
                ),
            )

    value = A.PairedForwardEvidenceCollector(
        activation=activation(),
        journal_path=tmp_path / "paired.jsonl",
        baseline_engine=TradeEngine(),
        candidate_engine=TradeEngine(),
    )
    decision = collect_start(value)
    frozen_authority = value._event_for(
        decision.pair_key, "decision"
    )["payload"]["global_time_authority"]

    def append_open(**kwargs):
        position = VirtualPositionEngine.open_position(
            position_id=kwargs["position_id"],
            symbol=kwargs["symbol"],
            direction=kwargs["direction"],
            volume=0.01,
            entry_price=kwargs["entry_price"],
            stop_loss=kwargs["stop_loss"],
            take_profit=kwargs["take_profit"],
            broker_epoch=kwargs["broker_epoch"],
        )
        A.ShadowTradeJournal.append_event(
            path=kwargs["journal_path"],
            event_type="POSITION_OPENED",
            position_id=kwargs["position_id"],
            broker_epoch=kwargs["broker_epoch"],
            payload={
                "symbol": position.symbol,
                "direction": position.direction,
                "volume": position.volume,
                "entry_price": position.entry_price,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "initial_risk_price": position.initial_risk_price,
            },
        )
        return SimpleNamespace(
            valid=True,
            reason="VIRTUAL_POSITION_OPENED",
            position=position,
            real_order_send_allowed=False,
            order_send_called=False,
            order_check_called=False,
        )

    def crash_after_baseline(**kwargs):
        if "candidate" in kwargs["position_id"]:
            raise RuntimeError("simulated crash after baseline open")
        return append_open(**kwargs)

    monkeypatch.setattr(A.ShadowTradeEngine, "open_trade", crash_after_baseline)
    with pytest.raises(RuntimeError, match="simulated crash"):
        value.open_virtual_entries(
            pair_key=decision.pair_key,
            balance=10_000.0,
            point=0.01,
            time_authority=frozen_authority,
        )
    assert value._phase_events().get((decision.pair_key, "entry_input"))
    assert value._recover_position(decision.pair_key, "baseline") is not None
    assert value._recover_position(decision.pair_key, "candidate") is None

    TEST_NOW_EPOCH += A.GlobalTimeAuthority.MAX_TICK_RESIDUAL_SECONDS + 1
    restarted = A.PairedForwardEvidenceCollector(
        activation=activation(),
        journal_path=tmp_path / "paired.jsonl",
        baseline_engine=TradeEngine(),
        candidate_engine=TradeEngine(),
    )
    monkeypatch.setattr(A.ShadowTradeEngine, "open_trade", append_open)
    result = restarted.open_virtual_entries(
        pair_key=decision.pair_key,
        balance=1.0,
        point=1.0,
        time_authority=frozen_authority,
    )
    assert result.baseline_position is not None
    assert result.candidate_position is not None
    branches = restarted._event_for(decision.pair_key, "entry")["payload"][
        "branches"
    ]
    assert branches["baseline"]["is_actual_trade"] is True
    assert branches["candidate"]["is_actual_trade"] is True


def test_timebox_accepts_first_tick_after_boundary(monkeypatch, tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    position = VirtualPositionEngine.open_position(
        position_id="base-late-tick",
        symbol="BITCOIN",
        direction="BUY",
        volume=0.01,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        broker_epoch=utc_epoch(START_UTC) + 900,
    )
    monkeypatch.setattr(
        A.ShadowTradeValuation,
        "calculate",
        lambda **_kwargs: SimpleNamespace(
            valid=True,
            reason="VALUED",
            pnl_account_currency=1.0,
            real_order_send_allowed=False,
            order_send_called=False,
            order_check_called=False,
        ),
    )
    final_open = (
        datetime.fromisoformat(END_UTC[:-1] + "+00:00")
        - timedelta(minutes=15)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = value.timebox_close(
        position=position,
        final_completed_candle_open_utc=final_open,
        close_broker_epoch=utc_epoch(END_UTC),
        bid=105.0,
        ask=105.5,
        time_authority=time_authority(
            current_bar_epoch=utc_epoch(END_UTC),
            tick_epoch=utc_epoch(END_UTC) + 1,
        ),
    )
    assert result.closed_position.close_broker_epoch == utc_epoch(END_UTC)


def test_timebox_accepts_authority_from_a_later_post_boundary_bar(
    monkeypatch, tmp_path
):
    value, _baseline, _candidate = collector(tmp_path)
    position = VirtualPositionEngine.open_position(
        position_id="base-later-bar",
        symbol="BITCOIN",
        direction="BUY",
        volume=0.01,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        broker_epoch=utc_epoch(START_UTC) + 900,
    )
    monkeypatch.setattr(
        A.ShadowTradeValuation,
        "calculate",
        lambda **_kwargs: SimpleNamespace(
            valid=True,
            reason="VALUED",
            pnl_account_currency=1.0,
            real_order_send_allowed=False,
            order_send_called=False,
            order_check_called=False,
        ),
    )
    final_open = (
        datetime.fromisoformat(END_UTC[:-1] + "+00:00")
        - timedelta(minutes=15)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = value.timebox_close(
        position=position,
        final_completed_candle_open_utc=final_open,
        close_broker_epoch=utc_epoch(END_UTC),
        bid=105.0,
        ask=105.5,
        time_authority=time_authority(
            current_bar_epoch=utc_epoch(END_UTC) + A.TIMEFRAME_SECONDS,
            tick_epoch=utc_epoch(END_UTC) + A.TIMEFRAME_SECONDS + 1,
        ),
    )
    assert result.closed_position.close_broker_epoch == utc_epoch(END_UTC)


def test_journaled_timebox_accepts_later_bar_but_closes_at_exact_boundary(
    monkeypatch, tmp_path
):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    value.record_entry_outcome(
        pair_key=decision.pair_key,
        baseline=A.BranchEntryOutcome(
            True, "OPEN", decision.baseline_position_id
        ),
        candidate=A.BranchEntryOutcome(False, "REJECTED_CANDIDATE"),
        entry_broker_epoch=utc_epoch(START_UTC) + A.TIMEFRAME_SECONDS,
        time_authority=time_authority(),
    )
    A.ShadowTradeJournal.append_event(
        path=value.trade_journal_path(decision.pair_key, "baseline"),
        event_type="POSITION_OPENED",
        position_id=decision.baseline_position_id,
        broker_epoch=utc_epoch(START_UTC) + A.TIMEFRAME_SECONDS,
        payload={
            "symbol": "BITCOIN",
            "direction": "BUY",
            "volume": 0.01,
            "entry_price": 100.0,
            "stop_loss": 90.0,
            "take_profit": 120.0,
            "initial_risk_price": 10.0,
        },
    )
    monkeypatch.setattr(
        A.ShadowTradeValuation,
        "calculate",
        lambda **_kwargs: SimpleNamespace(
            valid=True,
            reason="VALUED",
            pnl_account_currency=1.0,
            real_order_send_allowed=False,
            order_send_called=False,
            order_check_called=False,
        ),
    )
    close_epoch = utc_epoch(END_UTC)
    value.collect_decision(
        snapshot=live_snapshot(
            signal_epoch=close_epoch - 2 * A.TIMEFRAME_SECONDS,
            authority=time_authority(
                current_bar_epoch=close_epoch - A.TIMEFRAME_SECONDS,
                tick_epoch=close_epoch - A.TIMEFRAME_SECONDS + 1,
            ),
        )
    )
    result = value.timebox_close_virtual_trade(
        pair_key=decision.pair_key,
        branch="baseline",
        final_completed_candle={
            "time": close_epoch - A.TIMEFRAME_SECONDS,
            "open": 104.0,
            "high": 106.0,
            "low": 103.0,
            "close": 105.0,
            "tick_volume": 10,
            "spread": 2,
            "real_volume": 0,
        },
        point=0.01,
        time_authority=time_authority(
            current_bar_epoch=close_epoch + A.TIMEFRAME_SECONDS,
            tick_epoch=close_epoch + A.TIMEFRAME_SECONDS + 1,
        ),
    )
    assert result.closed_position.close_broker_epoch == close_epoch
    terminal_input = value._event_for(
        decision.pair_key, "terminal_input_baseline"
    )
    assert terminal_input["broker_epoch"] == close_epoch
    assert terminal_input["payload"]["boundary_broker_offset_seconds"] == 0
    A.Preregistration._require_sha256(
        terminal_input["payload"]["boundary_time_authority_event_sha256"],
        "timebox boundary authority event",
    )


def test_ordinary_virtual_update_is_blocked_at_exclusive_end(tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    value.record_entry_outcome(
        pair_key=decision.pair_key,
        baseline=A.BranchEntryOutcome(
            True, "OPEN", decision.baseline_position_id
        ),
        candidate=A.BranchEntryOutcome(False, "REJECTED_CANDIDATE"),
        entry_broker_epoch=utc_epoch(START_UTC) + 900,
        time_authority=time_authority(),
    )
    A.ShadowTradeJournal.append_event(
        path=value.trade_journal_path(decision.pair_key, "baseline"),
        event_type="POSITION_OPENED",
        position_id=decision.baseline_position_id,
        broker_epoch=utc_epoch(START_UTC) + 900,
        payload={
            "symbol": "BITCOIN",
            "direction": "BUY",
            "volume": 0.01,
            "entry_price": 100.0,
            "stop_loss": 90.0,
            "take_profit": 120.0,
            "initial_risk_price": 10.0,
        },
    )
    with pytest.raises(RuntimeError, match="use the frozen timebox close"):
        value.update_virtual_trade(
            pair_key=decision.pair_key,
            branch="baseline",
            bid=89.0,
            ask=89.5,
            broker_epoch=utc_epoch(END_UTC),
            time_authority=time_authority(
                current_bar_epoch=utc_epoch(END_UTC),
                tick_epoch=utc_epoch(END_UTC),
            ),
        )


def test_runner_has_no_file_or_backdated_forward_inputs():
    parsed = R.parser().parse_args(
        [
            "collect-decision",
            "--manifest-commit-sha",
            MANIFEST_COMMIT_SHA,
            "--no-forward-outcome-access-verified",
            "--canonical-symbol",
            "BTCUSD",
        ]
    )
    for removed in (
        "rates_snapshot",
        "time_authority",
        "current_bar_epoch",
        "decision_candle_open_utc",
        "public_pr_metadata",
        "publication_metadata",
        "created_at_utc",
    ):
        assert not hasattr(parsed, removed)
    assert {
        action.dest
        for action in R.parser()._subparsers._group_actions[0].choices[
            "collect-decision"
        ]._actions
    }.isdisjoint({"rates_snapshot", "time_authority", "current_bar_epoch"})


def test_runner_resumes_frozen_pending_entry_before_live_recapture(
    monkeypatch, tmp_path, capsys
):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    assert value.recover().pending_entry_pair_keys == (decision.pair_key,)
    monkeypatch.setattr(R, "verified_context", lambda _args: value.activation)
    monkeypatch.setattr(
        R,
        "PairedForwardEvidenceCollector",
        lambda **_kwargs: value,
    )

    def forbidden_capture(*_args, **_kwargs):
        raise AssertionError("live MT5 was recaptured before pending recovery")

    monkeypatch.setattr(R, "_capture_for_collector", forbidden_capture)
    R.collect_decision(SimpleNamespace(canonical_symbol="BTCUSD"))
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "SPRINT93_2B_PENDING_ENTRY_RECOVERED"
    assert output["pair_key"] == list(decision.pair_key)
    assert output["entry_source"] == "FROZEN_DECISION_EVIDENCE"
    assert output["live_mt5_recaptured"] is False
    assert value.recover().pending_entry_pair_keys == ()


def test_runner_selects_final_candle_with_boundary_not_delayed_dst_offset(
    monkeypatch, capsys
):
    close_epoch = utc_epoch(END_UTC)
    observed: dict[str, object] = {}

    class FakeCollector:
        activation = SimpleNamespace(exclusive_45_day_end_utc=END_UTC)

        def timebox_boundary_evidence(self):
            return 0, "d" * 64

        def _event_for(self, _pair_key, phase):
            assert phase == "entry"
            return {
                "payload": {
                    "branches": {
                        "baseline": {"is_actual_trade": True},
                        "candidate": {"is_actual_trade": False},
                    }
                }
            }

        def timebox_close_virtual_trade(self, **kwargs):
            observed["final_time"] = kwargs["final_completed_candle"]["time"]
            return SimpleNamespace(
                settlement=SimpleNamespace(net_r=0.0),
                terminal_write=None,
            )

    delayed_offset = 3600
    delayed_current_bar = close_epoch + delayed_offset + A.TIMEFRAME_SECONDS
    authority = time_authority(
        offset=delayed_offset,
        current_bar_epoch=delayed_current_bar,
        tick_epoch=delayed_current_bar + 1,
    )
    snapshot = SimpleNamespace(
        time_authority=lambda: authority,
        point=0.01,
        rates=(
            A._FrozenRate(
                time=close_epoch - A.TIMEFRAME_SECONDS,
                open=104.0,
                high=106.0,
                low=103.0,
                close=105.0,
                tick_volume=10,
                spread=2,
                real_volume=0,
            ),
            A._FrozenRate(
                time=close_epoch + delayed_offset - A.TIMEFRAME_SECONDS,
                open=204.0,
                high=206.0,
                low=203.0,
                close=205.0,
                tick_volume=10,
                spread=2,
                real_volume=0,
            ),
        ),
    )
    fake = FakeCollector()
    monkeypatch.setattr(R, "_collector", lambda _args: fake)
    monkeypatch.setattr(R, "_capture_for_collector", lambda *_args: snapshot)
    R.timebox_close(
        SimpleNamespace(
            canonical_symbol="BTCUSD",
            decision_candle_open_utc=START_UTC,
        )
    )
    assert observed["final_time"] == close_epoch - A.TIMEFRAME_SECONDS
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "SPRINT93_2B_TIMEBOX_CLOSE_COMPLETE"


def test_runner_normalizes_authoritative_github_pr_metadata(monkeypatch):
    monkeypatch.setattr(
        R,
        "_repository_full_name",
        lambda: "masoudengin65-byte/MSS_Package_003",
    )
    monkeypatch.setattr(
        R,
        "_command_json",
        lambda _arguments, _label: {
            "url": "https://github.com/masoudengin65-byte/MSS_Package_003/pull/5",
            "number": 5,
            "state": "MERGED",
            "mergedAt": MERGED_AT,
            "mergeCommit": {"oid": MERGE_SHA},
            "headRefOid": "d" * 40,
            "baseRefName": "main",
        },
    )
    result = R._authoritative_pr_metadata(5)
    assert result["metadata_source"] == "GITHUB_AUTHORITATIVE"
    assert result["repository_full_name"] == (
        "masoudengin65-byte/MSS_Package_003"
    )
    assert result["merge_commit_sha"] == MERGE_SHA


def test_publication_time_comes_from_authoritative_github_push_event(monkeypatch):
    monkeypatch.setattr(
        R,
        "_github_api_array",
        lambda _path, _label: [
            {
                "type": "PushEvent",
                "created_at": PUSHED_AT,
                "payload": {
                    "head": MANIFEST_COMMIT_SHA,
                    "commits": [{"sha": MANIFEST_COMMIT_SHA}],
                },
            }
        ],
    )
    assert R._public_push_timestamp(
        "masoudengin65-byte/MSS_Package_003", MANIFEST_COMMIT_SHA
    ) == PUSHED_AT


def test_missing_public_push_event_fails_closed(monkeypatch):
    monkeypatch.setattr(R, "_github_api_array", lambda _path, _label: [])
    with pytest.raises(RuntimeError, match="no authoritative GitHub PushEvent"):
        R._public_push_timestamp(
            "masoudengin65-byte/MSS_Package_003", MANIFEST_COMMIT_SHA
        )


def test_manifest_rejects_self_asserted_or_wrong_repository_metadata(monkeypatch):
    patch_identity(monkeypatch)
    forged = public_metadata()
    forged["url"] = "https://example.invalid/pull/5"
    with pytest.raises(RuntimeError, match="authoritative GitHub"):
        A.build_activation_manifest_after_merge(
            repository_root=Path.cwd(),
            public_pr_metadata=forged,
            manifest_created_at_utc=CREATED_AT,
            no_forward_outcome_access_verified=True,
        )


def test_live_capture_uses_only_direct_read_only_mt5_calls(monkeypatch, tmp_path):
    import MetaTrader5 as mt5

    signal_epoch = utc_epoch(START_UTC)
    current_bar_epoch = signal_epoch + 900
    calls: list[str] = []

    def called(name, value):
        def invoke(*_args, **_kwargs):
            calls.append(name)
            return value

        return invoke

    raw_rates = rates(signal_epoch)
    monkeypatch.setattr(A, "_utc_now_epoch", lambda: float(current_bar_epoch + 1))
    monkeypatch.setattr(mt5, "TIMEFRAME_M15", 15, raising=False)
    monkeypatch.setattr(mt5, "initialize", called("initialize", True))
    monkeypatch.setattr(
        mt5,
        "terminal_info",
        called(
            "terminal_info",
            SimpleNamespace(
                connected=True,
                company="MetaQuotes",
                name="MT5",
                build=5000,
            ),
        ),
    )
    monkeypatch.setattr(
        mt5,
        "account_info",
        called(
            "account_info",
            SimpleNamespace(
                balance=10_000.0,
                server="Broker-Demo",
                company="Broker",
                currency="USD",
            ),
        ),
    )
    monkeypatch.setattr(mt5, "symbol_select", called("symbol_select", True))
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        called("symbol_info", SimpleNamespace(point=0.01)),
    )
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        called(
            "symbol_info_tick",
            SimpleNamespace(
                time=current_bar_epoch + 1,
                time_msc=(current_bar_epoch + 1) * 1000,
                bid=100.0,
                ask=100.5,
            ),
        ),
    )
    monkeypatch.setattr(
        mt5,
        "copy_rates_from_pos",
        called("copy_rates_from_pos", raw_rates),
    )
    monkeypatch.setattr(mt5, "shutdown", called("shutdown", None))
    monkeypatch.setattr(
        mt5,
        "order_send",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("order_send called")
        ),
    )
    monkeypatch.setattr(
        mt5,
        "order_check",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("order_check called")
        ),
    )

    snapshot = A.capture_live_mt5_snapshot("BTCUSD")
    provenance = snapshot.provenance()
    assert provenance["source"] == "DIRECT_LIVE_MT5_READ_ONLY"
    assert provenance["account_server"] == "Broker-Demo"
    assert provenance["rate_record_count"] == A.LIVE_RATE_COUNT
    assert "order_send" not in calls and "order_check" not in calls
    value, _baseline, _candidate = collector(tmp_path)
    result = value.collect_decision(snapshot=snapshot)
    assert result.pair_key == ("BTCUSD", START_UTC)


def test_unmarked_live_snapshot_is_rejected_before_strategy(tmp_path):
    value, baseline, candidate = collector(tmp_path)
    valid = live_snapshot(signal_epoch=utc_epoch(START_UTC))
    forged = A.LiveMt5Snapshot(
        canonical_symbol=valid.canonical_symbol,
        broker_symbol=valid.broker_symbol,
        current_bar_epoch=valid.current_bar_epoch,
        tick_epoch=valid.tick_epoch,
        bid=valid.bid,
        ask=valid.ask,
        balance=valid.balance,
        point=valid.point,
        rates=valid.rates,
        time_authority_json=valid.time_authority_json,
        provenance_json=valid.provenance_json,
    )
    with pytest.raises(RuntimeError, match="directly verified live MT5 snapshot"):
        value.collect_decision(snapshot=forged)
    assert baseline.calls == candidate.calls == 0
