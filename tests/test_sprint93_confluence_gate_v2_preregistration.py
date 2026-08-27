from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

from mss.analysis.sprint93_confluence_gate_v2_preregistration import (
    Sprint93ConfluenceGateV2Preregistration as C,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "integration_tests/run_sprint93_2a_confluence_gate_v2_preregistration.py"
REPORT = ROOT / "reports/MSS_Sprint93_2A_Confluence_Gate_V2_Preregistration_V3.json"
SPEC = importlib.util.spec_from_file_location("sprint93_2a_preregistration_runner", RUNNER)
assert SPEC is not None and SPEC.loader is not None
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


def baseline_blob(path: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{C.BASELINE_COMMIT}:{path}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


@lru_cache(maxsize=1)
def baseline_identity() -> tuple[tuple[str, str], ...]:
    return tuple(
        (path, hashlib.sha256(baseline_blob(path)).hexdigest())
        for path in C.REQUIRED_STRATEGY_COMPONENT_FILES
    )


def build() -> dict[str, object]:
    return C().build(
        baseline_commit=C.BASELINE_COMMIT,
        component_identity=baseline_identity(),
    )


def pair_member(record_type: str, net_r: float | None, settlement: str | None) -> dict[str, object]:
    return {
        "record_type": record_type,
        "actual_trade_net_r": net_r,
        "terminal_settlement_utc": settlement,
    }


def activation_fixture() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, str],
    tuple[tuple[str, str], ...],
]:
    observed = (
        ("activation/baseline.py", "1" * 64),
        ("activation/candidate.py", "2" * 64),
        ("activation/evaluation.py", "3" * 64),
        ("activation/executor.py", "4" * 64),
        ("activation/journal.py", "5" * 64),
        ("activation/risk.py", "6" * 64),
        ("activation/valuation.py", "7" * 64),
    )
    records = [
        {"path": path, "git_blob_sha256": digest} for path, digest in observed
    ]
    merged_at = "2026-08-25T10:00:01Z"
    start, end = C.activation_window(merged_at)
    manifest = {
        "activation_pr_url": "https://github.com/example/mss/pull/5",
        "activation_pr_number": 5,
        "activation_pr_public_merged_at_utc": merged_at,
        "activation_merge_commit_sha": "a" * 40,
        "manifest_created_at_utc": "2026-08-25T10:01:00Z",
        "python_version": "3.13.7",
        "numpy_version": "2.3.2",
        "paired_executor_identity": records[3].copy(),
        "baseline_strategy_identity": {
            "strategy_identifier": "BASELINE_SMART_MONEY_PIPELINE",
            "path_git_blob_sha256": [records[0].copy()],
        },
        "candidate_strategy_identity": {
            "strategy_identifier": "CANDIDATE_CONFLUENCE_GATE",
            "path_git_blob_sha256": [records[1].copy()],
        },
        "journal_implementation_identity": records[4].copy(),
        "journal_schema_identity": {
            "schema_identifier": "PAIRED_JOURNAL_V1",
            "implementation_path": records[4]["path"],
            "git_blob_sha256": records[4]["git_blob_sha256"],
        },
        "risk_implementation_identity": records[5].copy(),
        "valuation_implementation_identity": records[6].copy(),
        "evaluation_implementation_identity": records[2].copy(),
        "complete_transitive_execution_file_identity": deepcopy(records),
        "transitive_execution_file_universe_complete": True,
        "computed_first_eligible_m15_open_utc": start,
        "computed_exclusive_45_day_end_utc": end,
        "no_forward_outcome_access_before_activation": True,
        "all_data_before_computed_start_permanently_ineligible": True,
        "write_once": True,
    }
    public = {
        "url": manifest["activation_pr_url"],
        "number": manifest["activation_pr_number"],
        "state": "MERGED",
        "mergedAt": merged_at,
        "merge_commit_sha": manifest["activation_merge_commit_sha"],
    }
    publication = {
        "manifest_committed_at_utc": "2026-08-25T10:02:00Z",
        "manifest_publicly_pushed_at_utc": "2026-08-25T10:03:00Z",
    }
    runtime = {"python_version": "3.13.7", "numpy_version": "2.3.2"}
    return manifest, public, publication, runtime, observed


def validate_activation(
    manifest: dict[str, object],
    public: dict[str, object],
    publication: dict[str, object],
    runtime: dict[str, str],
    observed: tuple[tuple[str, str], ...],
    **overrides: object,
) -> bool:
    arguments = {
        "public_pr_metadata": public,
        "publication_metadata": publication,
        "runtime_versions": runtime,
        "observed_execution_identity": observed,
        "no_forward_outcome_access_verified": True,
        "existing_manifest": None,
    }
    arguments.update(overrides)
    return C.validate_activation_manifest(manifest, **arguments)


def test_prior_versions_are_superseded_and_inert():
    report = build()
    supersession = report["v1_supersession"]
    assert report["schema_version"].endswith("_V3")
    assert report["execution_id"].endswith("_V3")
    assert supersession["v1_authorizes_eligible_forward_data"] is False
    assert supersession["candles_at_or_before_invalid_v1_boundary_eligible"] is False
    assert report["v2_supersession"] == {
        "superseded_schema_version": "MSS_SPRINT93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_PREREGISTRATION_V2",
        "superseded_execution_id": "MSS_93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_V2",
        "supersession_reason": "OUTCOME_BLIND_SHARED_JOURNAL_SAFETY_HARDENING_BEFORE_ACTIVATION",
        "v2_authorizes_eligible_forward_data": False,
        "forward_outcomes_observed_before_v3_freeze": False,
        "candles_collected_before_v3_activation_manifest_eligible": False,
    }


def test_current_activation_remains_blocked_false_and_null():
    report = build()
    activation = report["activation"]
    assert report["protocol_state"] == "BLOCKED_PENDING_PAIRED_EXECUTION_FREEZE"
    assert activation["forward_data_eligible"] is False
    assert activation["first_eligible_candle_open_utc"] is None
    assert activation["exclusive_experiment_end_utc"] is None
    assert activation["activation_manifest"] is None
    assert report["v1_supersession"]["candles_collected_before_activation_manifest_eligible"] is False


def test_full_baseline_commit_is_exactly_resolved_and_bound():
    resolved = subprocess.run(
        ["git", "rev-parse", "fcad910^{commit}"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    assert C.BASELINE_COMMIT == resolved == "fcad91029799a4cd5fdee1fe130f58334cf63452"
    assert len(C.BASELINE_COMMIT) == 40
    with pytest.raises(RuntimeError):
        C().build(baseline_commit="0e643da", component_identity=baseline_identity())
    with pytest.raises(RuntimeError):
        C().build(baseline_commit="f" * 40, component_identity=baseline_identity())


def test_complete_40_file_closure_plus_two_package_initializers():
    assert len(C.TRANSITIVE_STRATEGY_COMPONENT_FILES) == 40
    assert len(C.PACKAGE_INITIALIZER_FILES) == 2
    assert len(C.REQUIRED_STRATEGY_COMPONENT_FILES) == 42
    assert not set(C.PACKAGE_INITIALIZER_FILES) & set(C.TRANSITIVE_STRATEGY_COMPONENT_FILES)
    assert set(C.REQUIRED_STRATEGY_COMPONENT_FILES) == (
        set(C.TRANSITIVE_STRATEGY_COMPONENT_FILES) | set(C.PACKAGE_INITIALIZER_FILES)
    )
    assert R.transitive_closure(commit=C.BASELINE_COMMIT) == C.TRANSITIVE_STRATEGY_COMPONENT_FILES


def test_both_package_initializers_have_exact_frozen_hashes():
    frozen = dict(C.EXPECTED_STRATEGY_COMPONENT_IDENTITY)
    assert frozen["src/mss/__init__.py"] == "b3a65c460b1862136f011b1f5d8299b915af4c0bca3149cb3a8252f0b34d53bd"
    assert frozen["src/mss/analysis/__init__.py"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert baseline_identity() == C.EXPECTED_STRATEGY_COMPONENT_IDENTITY


def test_expected_identity_and_each_item_are_immutable_tuples():
    identity = C.EXPECTED_STRATEGY_COMPONENT_IDENTITY
    assert isinstance(identity, tuple)
    assert all(isinstance(item, tuple) for item in identity)
    with pytest.raises(TypeError):
        identity[0] = identity[0]
    with pytest.raises(TypeError):
        identity[0][1] = "0" * 64


@pytest.mark.parametrize(
    "mutation",
    ["fabricated", "missing", "additional", "reordered", "substituted", "uppercase", "short"],
)
def test_invalid_ordered_component_identities_are_rejected(mutation: str):
    items = list(baseline_identity())
    if mutation == "fabricated":
        items[0] = ("src/mss/fabricated.py", items[0][1])
    elif mutation == "missing":
        items.pop()
    elif mutation == "additional":
        items.append(("src/mss/z_additional.py", "0" * 64))
    elif mutation == "reordered":
        items[0], items[1] = items[1], items[0]
    elif mutation == "substituted":
        items[0] = (items[0][0], items[1][1])
    elif mutation == "uppercase":
        items[0] = (items[0][0], items[0][1].upper())
    else:
        items[0] = (items[0][0], items[0][1][:-1])
    with pytest.raises(RuntimeError):
        C().build(baseline_commit=C.BASELINE_COMMIT, component_identity=tuple(items))


def test_report_identity_is_an_exact_ordered_list_of_path_hash_records():
    identity = build()["strategy_component_identity"]["ordered_path_sha256"]
    assert isinstance(identity, list)
    assert identity == [
        {"path": path, "sha256": digest} for path, digest in baseline_identity()
    ]
    assert all(set(record) == {"path", "sha256"} for record in identity)


def test_protected_source_artifacts_are_hash_only_metadata():
    artifacts = build()["protected_source_artifacts"]
    assert artifacts == [
        {
            "path": path,
            "schema_identifier": schema,
            "expected_sha256": digest,
        }
        for path, schema, digest in C.PROTECTED_SOURCE_ARTIFACTS
    ]
    assert all(set(record) == {"path", "schema_identifier", "expected_sha256"} for record in artifacts)
    assert "source_git_blob_sha256" not in build()


def test_protected_source_verifier_never_json_parses_or_content_inspects(monkeypatch):
    sentinel = b"\xff\x00not-json\r\n{still-not-json}"
    expected = hashlib.sha256(sentinel).hexdigest()

    def forbidden_loads(*_args, **_kwargs):
        raise AssertionError("protected blob was JSON parsed")

    monkeypatch.setattr(R.json, "loads", forbidden_loads)
    monkeypatch.setattr(C, "PROTECTED_SOURCE_ARTIFACTS", (("opaque.bin", "FROZEN_SCHEMA", expected),))
    monkeypatch.setattr(R, "git_bytes", lambda path, *, commit: sentinel)
    R.verify_protected_source_artifacts(commit=C.BASELINE_COMMIT)
    assert "json.loads" not in RUNNER.read_text(encoding="utf-8")
    assert tuple(inspect.signature(C.build).parameters) == (
        "self",
        "baseline_commit",
        "component_identity",
    )


def test_pair_record_schema_has_exact_required_types_and_key():
    gate = build()["research_evaluation_gate"]
    assert gate["pair_key"] == ["canonical_symbol", "decision_candle_open_utc"]
    assert gate["pair_record_schema"]["record_types"] == list(C.PAIR_RECORD_TYPES)
    assert gate["pair_population"] == "UNION_OF_DECISION_TIMESTAMPS_WHERE_EITHER_BRANCH_OPENS_AN_ACTUAL_VIRTUAL_POSITION"


def test_actual_zero_r_trade_is_distinct_from_no_trade_member():
    projection = C.validate_pair_record(
        {
            "pair_key": ("BTCUSD", "2026-09-01T00:00:00Z"),
            "baseline_member": pair_member("BASELINE_ACTUAL_TRADE", 0.0, "2026-09-01T01:00:00Z"),
            "candidate_member": pair_member("CANDIDATE_NO_TRADE", None, None),
        }
    )
    assert projection["baseline_is_actual_trade"] is True
    assert projection["candidate_is_actual_trade"] is False
    assert projection["baseline_paired_r"] == projection["candidate_paired_r"] == 0.0
    schema = build()["research_evaluation_gate"]["pair_record_schema"]
    assert schema["actual_zero_r_remains_actual_trade"] is True
    assert schema["actual_zero_r_is_non_win"] is True
    assert schema["actual_zero_r_included_in"] == list(C.ACTUAL_TRADE_DENOMINATORS)
    assert schema["actual_zero_r_profit_factor_contribution"] == {
        "positive_sum_r": 0.0,
        "negative_sum_r": 0.0,
    }
    assert schema["no_trade_actual_trade_net_r"] is None


def test_timebox_mtm_is_terminal_actual_and_in_every_denominator():
    projection = C.validate_pair_record(
        {
            "pair_key": ("ETHUSD", "2026-09-01T00:00:00Z"),
            "baseline_member": pair_member("BASELINE_NO_TRADE", None, None),
            "candidate_member": pair_member("TIMEBOX_MTM_CLOSE", 0.25, "2026-10-10T10:00:00Z"),
        }
    )
    assert projection["candidate_is_actual_trade"] is True
    assert projection["candidate_is_timebox_mtm"] is True
    timebox = build()["research_evaluation_gate"]["timebox_mtm_close"]
    assert timebox["is_terminal_settled_actual_trade"] is True
    assert timebox["applies_to_every_position_still_open_at_exclusive_end"] is True
    assert timebox["deterministic"] is True
    assert timebox["included_in"] == list(C.ACTUAL_TRADE_DENOMINATORS)
    assert "FINAL_ELIGIBLE_COMPLETED_M15_CANDLE" in timebox["valuation_candle"]
    assert build()["paired_forward_shadow_contract"]["no_new_entries_at_or_after_exclusive_end"] is True


def test_pair_with_no_actual_position_is_structurally_invalid():
    with pytest.raises(RuntimeError):
        C.validate_pair_record(
            {
                "pair_key": ("BTCUSD", "2026-09-01T00:00:00Z"),
                "baseline_member": pair_member("BASELINE_NO_TRADE", None, None),
                "candidate_member": pair_member("CANDIDATE_NO_TRADE", None, None),
            }
        )


def test_metric_formulas_profit_factor_edges_and_order_are_frozen():
    metrics = build()["research_evaluation_gate"]["metric_definitions"]
    assert metrics["actual_trade_mean_r"] == "SUM(ACTUAL_TRADE_NET_R) / ACTUAL_TERMINAL_SETTLED_TRADE_COUNT"
    assert metrics["expectancy"] == "WIN_RATE * MEAN_POSITIVE_R - NON_WIN_RATE * MEAN_ABSOLUTE_NON_POSITIVE_R"
    assert metrics["mean_positive_r"].startswith("SUM(POSITIVE_ACTUAL_TRADE_NET_R)")
    assert metrics["mean_absolute_non_positive_r"].startswith("SUM(ABS(NON_POSITIVE_ACTUAL_TRADE_NET_R))")
    assert metrics["expectancy_zero_r_rule"] == "ZERO_R_ACTUAL_TRADES_ARE_INCLUDED_AMONG_NON_WINS"
    assert metrics["profit_factor_zero_loss_behavior"] == {
        "positive_sum_greater_than_zero": "POSITIVE_INFINITY",
        "positive_infinity_passes_threshold": True,
        "positive_and_negative_sums_both_zero": 0.0,
    }
    assert metrics["win_rate"] == "COUNT(ACTUAL_TRADE_NET_R > 0) / ACTUAL_TERMINAL_SETTLED_TRADE_COUNT"
    assert "BEGINNING_AT_0.0_R" in metrics["maximum_drawdown"]
    assert metrics["pooled_order"] == [
        "pair_settlement_utc",
        "canonical_symbol",
        "decision_candle_open_utc",
    ]


def test_all_mean_expectancy_pf_win_sample_drawdown_bootstrap_and_integrity_gates():
    gates = build()["research_evaluation_gate"]["gates"]
    assert [(gate["name"], gate["operator"], gate["threshold"]) for gate in gates] == [
        ("paired_pooled_candidate_minus_baseline_mean_r", ">", 0.0),
        ("candidate_actual_trade_pooled_mean_r", ">", 0.0),
        ("candidate_actual_trade_pooled_expectancy", ">", 0.0),
        ("candidate_pooled_profit_factor", ">=", 1.10),
        ("candidate_pooled_win_rate", ">=", 0.36),
        ("candidate_maximum_drawdown_r", "<=", "BASELINE_MAXIMUM_DRAWDOWN_R"),
        ("candidate_terminal_settled_actual_trades_pooled", ">=", 50),
        ("candidate_terminal_settled_actual_trades_per_symbol", ">=", 15),
        ("ordinary_bootstrap_probability_paired_mean_difference_gt_zero", ">=", 0.80),
        ("moving_block_bootstrap_probability_paired_mean_difference_gt_zero", ">=", 0.80),
        ("failure_counts", "==", 0),
    ]
    assert gates[-1]["categories"] == list(C.INTEGRITY_FAILURE_CATEGORIES)


def test_ordinary_and_moving_block_bootstrap_algorithms_are_fully_frozen():
    bootstrap = build()["research_evaluation_gate"]["bootstrap"]
    assert bootstrap["input"] == "PAIRED_CANDIDATE_R_MINUS_BASELINE_R"
    assert bootstrap["symbol_strata_preserved"] is True
    assert bootstrap["within_symbol_order"] == ["decision_candle_open_utc", "pair_key"]
    assert bootstrap["resamples"] == 10_000
    assert bootstrap["rng"] == {
        "api": "numpy.random.Generator",
        "bit_generator": "numpy.random.PCG64",
        "construction": "numpy.random.Generator(numpy.random.PCG64(seed))",
        "seed": 9320260825,
    }
    assert bootstrap["ordinary"] == {
        "symbols_sampled_independently": True,
        "sampling": "WITH_REPLACEMENT",
        "per_symbol_sample_count": "ORIGINAL_SYMBOL_PAIR_COUNT",
        "pool_completed_symbol_samples": True,
    }
    assert bootstrap["moving_block"] == {
        "circular_wrapping": True,
        "block_length_pair_rows": 8,
        "block_start_indices": "UNIFORM_WITH_REPLACEMENT",
        "blocks_per_symbol": "CEIL(SYMBOL_PAIR_COUNT / 8)",
        "concatenate_blocks": True,
        "truncate_to_original_symbol_pair_count": True,
        "pool_completed_symbol_samples": True,
    }
    assert bootstrap["probability"].startswith("EXACT_FRACTION_OF_10000")
    assert bootstrap["empty_incomplete_or_structurally_invalid_population_result"] == "INCONCLUSIVE"
    assert bootstrap["inconclusive_can_pass"] is False
    assert bootstrap["runtime_versions_must_be_frozen_in_activation_manifest"] == [
        "python_version",
        "numpy_version",
    ]


def test_activation_boundary_exactly_24_hours_ceil_m15_plus_45_days():
    assert C.activation_window("2026-08-25T10:00:00Z") == (
        "2026-08-26T10:00:00Z",
        "2026-10-10T10:00:00Z",
    )
    assert C.activation_window("2026-08-25T10:00:01Z") == (
        "2026-08-26T10:15:00Z",
        "2026-10-10T10:15:00Z",
    )


def test_activation_manifest_contract_requires_all_identities_and_nonretroactive_rules():
    activation = build()["activation"]
    assert activation["write_once_manifest_required_fields"] == list(C.ACTIVATION_MANIFEST_REQUIRED_FIELDS)
    rules = activation["activation_rules"]
    assert rules == {
        "activation_pr_must_be_merged_before_manifest_creation": True,
        "manifest_commit_and_public_push_must_be_strictly_before_start": True,
        "commit_or_push_at_or_after_start_requires_new_activation_pr_and_boundary": True,
        "retroactive_activation_allowed": False,
        "hash_mismatch_keeps_activation_blocked": True,
        "all_pre_start_data_permanently_ineligible": True,
        "manifest_write_once": True,
    }


def test_valid_future_activation_manifest_is_enforceable_without_activating_current_report():
    manifest, public, publication, runtime, observed = activation_fixture()
    assert validate_activation(manifest, public, publication, runtime, observed) is True
    assert build()["activation"]["activation_manifest"] is None
    assert build()["activation"]["forward_data_eligible"] is False


@pytest.mark.parametrize("missing_field", C.ACTIVATION_MANIFEST_REQUIRED_FIELDS)
def test_each_future_activation_manifest_field_is_mandatory(missing_field: str):
    manifest, public, publication, runtime, observed = activation_fixture()
    del manifest[missing_field]
    with pytest.raises(RuntimeError):
        validate_activation(manifest, public, publication, runtime, observed)


@pytest.mark.parametrize(
    "identity_field",
    [
        "paired_executor_identity",
        "journal_implementation_identity",
        "risk_implementation_identity",
        "valuation_implementation_identity",
        "evaluation_implementation_identity",
    ],
)
def test_each_activation_implementation_git_blob_hash_is_mandatory(identity_field: str):
    manifest, public, publication, runtime, observed = activation_fixture()
    del manifest[identity_field]["git_blob_sha256"]
    with pytest.raises(RuntimeError):
        validate_activation(manifest, public, publication, runtime, observed)


@pytest.mark.parametrize("location", ["universe", "baseline", "candidate", "journal_schema"])
def test_activation_universe_strategy_and_schema_hashes_are_mandatory(location: str):
    manifest, public, publication, runtime, observed = activation_fixture()
    if location == "universe":
        del manifest["complete_transitive_execution_file_identity"][0]["git_blob_sha256"]
    elif location == "journal_schema":
        del manifest["journal_schema_identity"]["git_blob_sha256"]
    else:
        del manifest[f"{location}_strategy_identity"]["path_git_blob_sha256"][0]["git_blob_sha256"]
    with pytest.raises(RuntimeError):
        validate_activation(manifest, public, publication, runtime, observed)


def test_activation_hash_mismatch_stays_blocked():
    manifest, public, publication, runtime, observed = activation_fixture()
    mismatched = list(observed)
    mismatched[0] = (mismatched[0][0], "f" * 64)
    with pytest.raises(RuntimeError):
        validate_activation(manifest, public, publication, runtime, tuple(mismatched))
    assert C.PROTOCOL_STATE == "BLOCKED_PENDING_PAIRED_EXECUTION_FREEZE"


def test_activation_requires_already_merged_public_pr_and_matching_runtime():
    manifest, public, publication, runtime, observed = activation_fixture()
    public["state"] = "OPEN"
    with pytest.raises(RuntimeError):
        validate_activation(manifest, public, publication, runtime, observed)
    public["state"] = "MERGED"
    runtime["numpy_version"] = "DIFFERENT"
    with pytest.raises(RuntimeError):
        validate_activation(manifest, public, publication, runtime, observed)


@pytest.mark.parametrize("boundary_case", ["created_at_merge", "commit_at_start", "push_at_start", "push_after_start"])
def test_activation_can_never_be_retroactive(boundary_case: str):
    manifest, public, publication, runtime, observed = activation_fixture()
    start = manifest["computed_first_eligible_m15_open_utc"]
    if boundary_case == "created_at_merge":
        manifest["manifest_created_at_utc"] = manifest["activation_pr_public_merged_at_utc"]
    elif boundary_case == "commit_at_start":
        publication["manifest_committed_at_utc"] = start
        publication["manifest_publicly_pushed_at_utc"] = start
    elif boundary_case == "push_at_start":
        publication["manifest_publicly_pushed_at_utc"] = start
    else:
        publication["manifest_publicly_pushed_at_utc"] = "2026-08-26T10:15:01Z"
    with pytest.raises(RuntimeError, match="new activation PR"):
        validate_activation(manifest, public, publication, runtime, observed)


def test_activation_manifest_is_write_once_and_requires_external_no_access_proof():
    manifest, public, publication, runtime, observed = activation_fixture()
    with pytest.raises(RuntimeError, match="write-once"):
        validate_activation(
            manifest,
            public,
            publication,
            runtime,
            observed,
            existing_manifest={"already": "present"},
        )
    with pytest.raises(RuntimeError, match="no-forward-outcome-access"):
        validate_activation(
            manifest,
            public,
            publication,
            runtime,
            observed,
            no_forward_outcome_access_verified=False,
        )


def test_committed_report_equals_complete_proved_rebuild():
    assert REPORT.read_bytes() == R.deterministic_rebuild()


def test_two_independent_builds_precede_determinism_claim(monkeypatch):
    template = build()
    rebuild_ids: list[int] = []
    flags_during_serialization: list[bool] = []
    real_canonical = R.canonical

    def fake_rebuild():
        artifact = deepcopy(template)
        rebuild_ids.append(id(artifact))
        return artifact

    def observed_canonical(artifact):
        flags_during_serialization.append(artifact["audit"]["deterministic_rebuild"])
        return real_canonical(artifact)

    monkeypatch.setattr(R, "rebuild", fake_rebuild)
    monkeypatch.setattr(R, "canonical", observed_canonical)
    R.deterministic_rebuild()
    assert len(rebuild_ids) == 2
    assert rebuild_ids[0] != rebuild_ids[1]
    assert flags_during_serialization == [False, False, True, True]


def test_complete_in_memory_artifact_mismatch_is_rejected(monkeypatch):
    first = build()
    second = deepcopy(first)
    second["research_evaluation_gate"]["metric_definitions"]["win_rate"] = "TAMPERED"
    artifacts = iter((first, second))
    monkeypatch.setattr(R, "rebuild", lambda: next(artifacts))
    with pytest.raises(RuntimeError, match="in-memory"):
        R.deterministic_rebuild()


def test_verify_snapshots_before_two_builds_and_after_without_writes(tmp_path, monkeypatch, capsys):
    template = build()
    expected = deepcopy(template)
    expected["audit"]["deterministic_rebuild"] = True
    report = tmp_path / "report.json"
    report.write_bytes(R.canonical(expected))
    events: list[str] = []
    real_snapshot = R.report_snapshot

    def tracked_snapshot():
        events.append("snapshot")
        return real_snapshot()

    def tracked_rebuild():
        events.append("build")
        return deepcopy(template)

    monkeypatch.setattr(R, "OUTPUT", report)
    monkeypatch.setattr(R, "report_snapshot", tracked_snapshot)
    monkeypatch.setattr(R, "rebuild", tracked_rebuild)
    before = (hashlib.sha256(report.read_bytes()).hexdigest(), report.stat().st_size, report.stat().st_mtime_ns)
    observed_modes: list[str] = []
    real_open = Path.open

    def read_only_open(self, mode="r", *args, **kwargs):
        if self == report:
            observed_modes.append(mode)
            if any(marker in mode for marker in "wax+"):
                raise AssertionError("--verify attempted a write-capable open")
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", read_only_open)
    R.main(["--verify"])
    after = (hashlib.sha256(report.read_bytes()).hexdigest(), report.stat().st_size, report.stat().st_mtime_ns)
    assert events == ["snapshot", "build", "build", "snapshot"]
    assert observed_modes and set(observed_modes) == {"rb"}
    assert before == after
    assert capsys.readouterr().out.strip() == "PREREGISTRATION_VERIFY_PASS"


@pytest.mark.parametrize("line_endings", ["LF", "CRLF"])
def test_lf_and_crlf_checkout_representations_verify_identically(line_endings: str, tmp_path, monkeypatch, capsys):
    rendered = b'{\n  "complete": true\n}\n'
    checkout = rendered if line_endings == "LF" else rendered.replace(b"\n", b"\r\n")
    report = tmp_path / "report.json"
    report.write_bytes(checkout)
    monkeypatch.setattr(R, "OUTPUT", report)
    monkeypatch.setattr(R, "deterministic_rebuild", lambda: rendered)
    before = (hashlib.sha256(checkout).hexdigest(), report.stat().st_size, report.stat().st_mtime_ns)
    R.main(["--verify"])
    after_raw = report.read_bytes()
    after = (hashlib.sha256(after_raw).hexdigest(), report.stat().st_size, report.stat().st_mtime_ns)
    assert before == after
    assert after_raw == checkout
    assert capsys.readouterr().out.strip() == "PREREGISTRATION_VERIFY_PASS"


def test_mixed_or_bare_carriage_return_report_bytes_are_not_normalized():
    canonical = b"{\n  \"x\": 1\n}\n"
    assert R.checkout_representation_matches(canonical, canonical)
    assert R.checkout_representation_matches(canonical.replace(b"\n", b"\r\n"), canonical)
    assert not R.checkout_representation_matches(b"{\r\n  \"x\": 1\n}\r\n", canonical)
    assert not R.checkout_representation_matches(canonical.replace(b"\n", b"\r"), canonical)


def test_write_refuses_overwrite_via_exact_exclusive_open(tmp_path, monkeypatch):
    report = tmp_path / "report.json"
    sentinel = b"DO NOT OVERWRITE"
    report.write_bytes(sentinel)
    observed_modes: list[str] = []
    real_open = Path.open

    def forbidden_exists(_self):
        raise AssertionError("exists() must not be used before exclusive creation")

    def tracked_open(self, mode="r", *args, **kwargs):
        if self == report:
            observed_modes.append(mode)
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(R, "OUTPUT", report)
    monkeypatch.setattr(R, "deterministic_rebuild", lambda: b"replacement")
    monkeypatch.setattr(Path, "exists", forbidden_exists)
    monkeypatch.setattr(Path, "open", tracked_open)
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        R.main(["--write"])
    assert observed_modes == ["xb"]
    assert report.read_bytes() == sentinel


def test_write_and_verify_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        R.main(["--write", "--verify"])


def test_runner_verify_subprocess_is_read_only_and_passes():
    before_raw = REPORT.read_bytes()
    before = (hashlib.sha256(before_raw).hexdigest(), REPORT.stat().st_size, REPORT.stat().st_mtime_ns)
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--verify"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    after_raw = REPORT.read_bytes()
    after = (hashlib.sha256(after_raw).hexdigest(), REPORT.stat().st_size, REPORT.stat().st_mtime_ns)
    assert result.stdout.strip() == "PREREGISTRATION_VERIFY_PASS"
    assert before == after
    assert before_raw == after_raw


def test_prohibited_access_ordering_and_production_behavior_remain_disabled():
    report = build()
    audit = report["audit"]
    assert all(
        audit[key] is False
        for key in (
            "mt5_accessed",
            "market_data_accessed",
            "replay_data_accessed",
            "strategy_replay_run",
            "outcomes_analyzed",
            "development_accessed",
            "validation_accessed",
            "quarantine_accessed",
            "true_oos_accessed",
            "production_behavior_changed",
            "order_check_called",
            "order_send_called",
            "real_order_called",
        )
    )
    forward = report["paired_forward_shadow_contract"]
    assert forward["order_check_allowed"] is False
    assert forward["order_send_allowed"] is False
    assert forward["real_order_allowed"] is False
    assert "MetaTrader5" not in RUNNER.read_text(encoding="utf-8")
