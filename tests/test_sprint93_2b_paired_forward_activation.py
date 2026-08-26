from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import mss.analysis.sprint93_paired_forward_activation as A
from mss.analysis.sprint93_confluence_gate_v2_preregistration import (
    Sprint93ConfluenceGateV2Preregistration as C,
)
from mss.analysis.virtual_position_engine import VirtualPositionEngine


MERGE_SHA = "a" * 40
MANIFEST_COMMIT_SHA = "b" * 40
MERGED_AT = "2026-08-25T10:00:01Z"
START_UTC, END_UTC = C.activation_window(MERGED_AT)
CREATED_AT = "2026-08-25T10:01:00Z"
COMMITTED_AT = "2026-08-25T10:02:00Z"
PUSHED_AT = "2026-08-25T10:03:00Z"


def public_metadata(state: str = "MERGED") -> dict[str, object]:
    return {
        "url": "https://github.com/example/mss/pull/5",
        "number": 5,
        "state": state,
        "mergedAt": MERGED_AT,
        "merge_commit_sha": MERGE_SHA,
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


def time_authority(offset: int = 0) -> dict[str, object]:
    return {
        "time_authority": {"confirmed": True},
        "observation": {"detected_broker_offset_seconds": offset},
    }


def rates(signal_epoch: int, *, close: float = 100.5) -> list[dict[str, object]]:
    return [
        {
            "time": signal_epoch,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": close,
            "tick_volume": 10,
            "spread": 2,
            "real_volume": 0,
        },
        {
            "time": signal_epoch + 900,
            "open": 100.5,
            "high": 101.5,
            "low": 100.0,
            "close": 101.0,
            "tick_volume": 3,
            "spread": 2,
            "real_volume": 0,
        },
    ]


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
        canonical_symbol="BTCUSD",
        decision_candle_open_utc=START_UTC,
        current_bar_epoch=signal_epoch + 900,
        rates=snapshot or rates(signal_epoch),
        time_authority=time_authority(),
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
    monkeypatch.setattr(
        A,
        "_resolve_commit",
        lambda _root, revision: MANIFEST_COMMIT_SHA if revision == "HEAD" else revision,
    )
    monkeypatch.setattr(A, "_git_blob", lambda *_args, **_kwargs: canonical)
    identities = iter((fake_identity(), (("different.py", "f" * 64),)))
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
            canonical_symbol="BTCUSD",
            decision_candle_open_utc=before,
            current_bar_epoch=utc_epoch(before) + 900,
            rates=rates(utc_epoch(before)),
            time_authority=time_authority(),
        )
    with pytest.raises(RuntimeError, match="exclusive experiment end"):
        value.collect_decision(
            canonical_symbol="BTCUSD",
            decision_candle_open_utc=END_UTC,
            current_bar_epoch=utc_epoch(END_UTC) + 900,
            rates=rates(utc_epoch(END_UTC)),
            time_authority=time_authority(),
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
            canonical_symbol="BTCUSD",
            decision_candle_open_utc=final_signal,
            current_bar_epoch=utc_epoch(END_UTC),
            rates=rates(utc_epoch(final_signal)),
            time_authority=time_authority(),
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
        baseline=A.BranchEntryOutcome(True, "VIRTUAL_POSITION_OPENED", "base-1"),
        candidate=A.BranchEntryOutcome(False, "REJECTED_CANDIDATE"),
        entry_broker_epoch=utc_epoch(START_UTC) + 900,
        time_authority=time_authority(),
    )
    assert entry.appended is True
    settlement = value.record_settlement(
        pair_key=decision.pair_key,
        baseline=A.BranchSettlement(True, 0.0, "2026-08-26T11:00:00Z"),
        candidate=A.BranchSettlement(False, None, None),
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
    with pytest.raises(RuntimeError, match="actual virtual position"):
        value.record_settlement(
            pair_key=decision.pair_key,
            baseline=A.BranchSettlement(False, None, None),
            candidate=A.BranchSettlement(False, None, None),
        )


def test_candidate_rejection_can_never_open_position(tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    with pytest.raises(RuntimeError, match="no-trade decision cannot open"):
        value.record_entry_outcome(
            pair_key=decision.pair_key,
            baseline=A.BranchEntryOutcome(True, "OPEN", "base-1"),
            candidate=A.BranchEntryOutcome(True, "OPEN", "candidate-1"),
            entry_broker_epoch=utc_epoch(START_UTC) + 900,
            time_authority=time_authority(),
        )


def test_entry_and_settlement_are_duplicate_safe_across_restart(tmp_path):
    value, _baseline, _candidate = collector(tmp_path)
    decision = collect_start(value)
    arguments = {
        "pair_key": decision.pair_key,
        "baseline": A.BranchEntryOutcome(True, "OPEN", "base-1"),
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
    }
    assert restarted.record_settlement(**settlement_arguments).appended is True
    final, _baseline3, _candidate3 = collector(tmp_path)
    assert final.record_settlement(**settlement_arguments).appended is False
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
            valid=True, reason="VALUED", pnl_account_currency=1.0
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
        time_authority=time_authority(),
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
            canonical_symbol="BTCUSD",
            decision_candle_open_utc=START_UTC,
            current_bar_epoch=utc_epoch(START_UTC) + 900,
            rates=rates(utc_epoch(START_UTC)),
            time_authority=authority,
        )
    assert baseline.calls == candidate.calls == 0
