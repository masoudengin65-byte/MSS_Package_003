"""Post-merge activation and paired-decision CLI for Sprint 93.2B."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mss.analysis.sprint93_paired_forward_activation import (
    DEFAULT_EVIDENCE_RELATIVE_PATH,
    DEFAULT_MANIFEST_RELATIVE_PATH,
    ACTIVATION_RUNNER_PATH,
    PAIRED_EXECUTOR_PATH,
    PairedForwardEvidenceCollector,
    build_activation_manifest_after_merge,
    capture_live_mt5_snapshot,
    create_activation_manifest_once,
    verify_package_safety,
    verify_published_activation_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / DEFAULT_MANIFEST_RELATIVE_PATH
DEFAULT_EVIDENCE_JOURNAL = ROOT / DEFAULT_EVIDENCE_RELATIVE_PATH


def _command_json(arguments: list[str], label: str) -> dict[str, object]:
    try:
        completed = subprocess.run(
            arguments,
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        value = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to obtain authoritative {label}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"authoritative {label} must be a JSON object")
    return value


def _github_api_json(path: str, label: str) -> dict[str, object]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MSS-Sprint93-2B-Activation",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/{path.lstrip('/')}", headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, HTTPError, URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to obtain authoritative {label}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"authoritative {label} must be a JSON object")
    return value


def _github_api_array(path: str, label: str) -> list[object]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MSS-Sprint93-2B-Activation",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/{path.lstrip('/')}", headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, HTTPError, URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to obtain authoritative {label}") from exc
    if not isinstance(value, list):
        raise RuntimeError(f"authoritative {label} must be a JSON array")
    return value


def _public_push_timestamp(repository: str, commit_sha: str) -> str:
    for page in range(1, 11):
        events = _github_api_array(
            f"repos/{repository}/events?per_page=100&page={page}",
            "GitHub repository events",
        )
        for event in events:
            if not isinstance(event, dict) or event.get("type") != "PushEvent":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            commits = payload.get("commits")
            commit_shas = {
                item.get("sha")
                for item in commits
                if isinstance(item, dict)
            } if isinstance(commits, list) else set()
            if payload.get("head") == commit_sha or commit_sha in commit_shas:
                created_at = event.get("created_at")
                if isinstance(created_at, str):
                    return created_at
                raise RuntimeError("GitHub push event timestamp is unavailable")
        if not events:
            break
    raise RuntimeError(
        "manifest commit has no authoritative GitHub PushEvent publication proof"
    )


def _repository_full_name() -> str:
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("unable to resolve the GitHub origin repository") from exc
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([^/\s]+/[^/\s]+?)(?:\.git)?",
        remote,
    )
    if match is None:
        raise RuntimeError("origin must be one exact GitHub repository")
    return match.group(1)


def _authoritative_pr_metadata(pr_number: int) -> dict[str, object]:
    if isinstance(pr_number, bool) or int(pr_number) <= 0:
        raise RuntimeError("activation PR number must be positive")
    repository = _repository_full_name()
    try:
        payload = _command_json(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repository,
                "--json",
                "url,number,state,mergedAt,mergeCommit,headRefOid,baseRefName",
            ],
            "GitHub PR metadata",
        )
        merge_commit = payload.get("mergeCommit")
        merge_sha = (
            merge_commit.get("oid") if isinstance(merge_commit, dict) else None
        )
        url = payload.get("url")
        state = payload.get("state")
        merged_at = payload.get("mergedAt")
        head_sha = payload.get("headRefOid")
        base_ref = payload.get("baseRefName")
    except RuntimeError:
        payload = _github_api_json(
            f"repos/{repository}/pulls/{int(pr_number)}",
            "GitHub PR metadata",
        )
        merge_sha = payload.get("merge_commit_sha")
        url = payload.get("html_url")
        merged_at = payload.get("merged_at")
        state = "MERGED" if merged_at is not None else str(payload.get("state", "")).upper()
        head = payload.get("head")
        base = payload.get("base")
        head_sha = head.get("sha") if isinstance(head, dict) else None
        base_ref = base.get("ref") if isinstance(base, dict) else None
    result = {
        "url": url,
        "number": payload.get("number"),
        "state": state,
        "mergedAt": merged_at,
        "merge_commit_sha": merge_sha,
        "repository_full_name": repository,
        "base_ref_name": base_ref,
        "head_sha": head_sha,
        "metadata_source": "GITHUB_AUTHORITATIVE",
    }
    expected_url = f"https://github.com/{repository}/pull/{int(pr_number)}"
    if result["url"] != expected_url or result["number"] != int(pr_number):
        raise RuntimeError("GitHub PR identity differs from the origin repository")
    return result


def _authoritative_publication_metadata(commit_sha: str) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{40}", str(commit_sha)) is None:
        raise RuntimeError("manifest commit must be a full lowercase Git SHA")
    repository = _repository_full_name()
    try:
        commit = _command_json(
            ["gh", "api", f"repos/{repository}/commits/{commit_sha}"],
            "GitHub manifest commit",
        )
        comparison = _command_json(
            ["gh", "api", f"repos/{repository}/compare/{commit_sha}...main"],
            "GitHub main ancestry",
        )
    except RuntimeError:
        commit = _github_api_json(
            f"repos/{repository}/commits/{commit_sha}",
            "GitHub manifest commit",
        )
        comparison = _github_api_json(
            f"repos/{repository}/compare/{commit_sha}...main",
            "GitHub main ancestry",
        )
    commit_record = commit.get("commit")
    committer = commit_record.get("committer") if isinstance(commit_record, dict) else None
    committed_at = committer.get("date") if isinstance(committer, dict) else None
    merge_base = comparison.get("merge_base_commit")
    merge_base_sha = merge_base.get("sha") if isinstance(merge_base, dict) else None
    if (
        commit.get("sha") != commit_sha
        or merge_base_sha != commit_sha
        or comparison.get("status") not in {"ahead", "identical"}
        or not isinstance(committed_at, str)
    ):
        raise RuntimeError("manifest commit is not publicly reachable from GitHub main")
    pushed_at = _public_push_timestamp(repository, commit_sha)
    return {
        "manifest_committed_at_utc": committed_at,
        "manifest_publicly_pushed_at_utc": pushed_at,
        "manifest_commit_sha": commit_sha,
        "publication_source": "GITHUB_AUTHORITATIVE",
    }


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_manifest(args: argparse.Namespace) -> None:
    public = _authoritative_pr_metadata(args.activation_pr_number)
    manifest = build_activation_manifest_after_merge(
        repository_root=ROOT,
        public_pr_metadata=public,
        manifest_created_at_utc=_now_utc_z(),
        no_forward_outcome_access_verified=(
            args.no_forward_outcome_access_verified
        ),
    )
    digest = create_activation_manifest_once(
        repository_root=ROOT,
        manifest=manifest,
    )
    print(
        json.dumps(
            {
                "result": "SPRINT93_2B_MANIFEST_CREATED",
                "manifest_path": str(DEFAULT_MANIFEST.resolve()),
                "manifest_sha256": digest,
                "activation_boundary_utc": manifest[
                    "computed_first_eligible_m15_open_utc"
                ],
                "exclusive_end_utc": manifest[
                    "computed_exclusive_45_day_end_utc"
                ],
            },
            sort_keys=True,
        )
    )


def verified_context(args: argparse.Namespace):
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("unable to read the activation manifest") from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("activation manifest must be a JSON object")
    pr_number = manifest.get("activation_pr_number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int):
        raise RuntimeError("activation manifest PR number is invalid")
    return verify_published_activation_manifest(
        manifest_path=args.manifest,
        repository_root=ROOT,
        public_pr_metadata=_authoritative_pr_metadata(pr_number),
        publication_metadata=_authoritative_publication_metadata(
            args.manifest_commit_sha
        ),
        no_forward_outcome_access_verified=(
            args.no_forward_outcome_access_verified
        ),
    )


def verify_manifest(args: argparse.Namespace) -> None:
    context = verified_context(args)
    print(
        json.dumps(
            {
                "result": "SPRINT93_2B_ACTIVATION_VERIFY_PASS",
                "manifest_sha256": context.manifest_sha256,
                "activation_merge_commit_sha": (
                    context.activation_merge_commit_sha
                ),
                "activation_boundary_utc": (
                    context.first_eligible_m15_open_utc
                ),
                "exclusive_end_utc": context.exclusive_45_day_end_utc,
                "execution_file_count": len(context.execution_identity),
                "real_order_send_allowed": False,
                "production_execution_enabled": False,
            },
            sort_keys=True,
        )
    )


def collect_decision(args: argparse.Namespace) -> None:
    context = verified_context(args)
    collector = PairedForwardEvidenceCollector(
        activation=context,
        journal_path=DEFAULT_EVIDENCE_JOURNAL,
    )
    resumed = collector.resume_pending_entry(
        canonical_symbol=args.canonical_symbol
    )
    if resumed is not None:
        print(
            json.dumps(
                {
                    "result": "SPRINT93_2B_PENDING_ENTRY_RECOVERED",
                    "pair_key": list(resumed.pair_key),
                    "entry_appended": resumed.write.appended,
                    "baseline_virtual_position_open": (
                        resumed.baseline_position is not None
                    ),
                    "candidate_virtual_position_open": (
                        resumed.candidate_position is not None
                    ),
                    "entry_source": "FROZEN_DECISION_EVIDENCE",
                    "live_mt5_recaptured": False,
                    "real_order_send_allowed": False,
                    "production_execution_enabled": False,
                },
                sort_keys=True,
            )
        )
        return
    snapshot = _capture_for_collector(collector, args.canonical_symbol)
    result = collector.collect_decision(snapshot=snapshot)
    entry = collector.open_virtual_entries(
        pair_key=result.pair_key,
        balance=snapshot.balance,
        point=snapshot.point,
        time_authority=snapshot.time_authority(),
    )
    print(
        json.dumps(
            {
                "result": "SPRINT93_2B_PAIRED_DECISION_RECORDED",
                "appended": result.write.appended,
                "event_id": result.write.event_id,
                "event_sha256": result.write.event_sha256,
                "pair_key": list(result.pair_key),
                "input_snapshot_sha256": result.input_snapshot_sha256,
                "baseline_decision_identity": (
                    result.baseline_decision_identity
                ),
                "candidate_decision_identity": (
                    result.candidate_decision_identity
                ),
                "entry_appended": entry.write.appended,
                "baseline_virtual_position_open": (
                    entry.baseline_position is not None
                ),
                "candidate_virtual_position_open": (
                    entry.candidate_position is not None
                ),
                "live_mt5_source": "DIRECT_LIVE_MT5_READ_ONLY",
                "real_order_send_allowed": False,
                "production_execution_enabled": False,
            },
            sort_keys=True,
        )
    )


def _collector(args: argparse.Namespace) -> PairedForwardEvidenceCollector:
    return PairedForwardEvidenceCollector(
        activation=verified_context(args),
        journal_path=DEFAULT_EVIDENCE_JOURNAL,
    )


def _pair_key(args: argparse.Namespace) -> tuple[str, str]:
    return (args.canonical_symbol, args.decision_candle_open_utc)


def _capture_for_collector(
    collector: PairedForwardEvidenceCollector,
    canonical_symbol: str,
):
    previous_offset = None
    for event in reversed(collector._events()):
        payload = event.get("payload")
        authority = (
            payload.get("global_time_authority")
            if isinstance(payload, dict)
            else None
        )
        observation = (
            authority.get("observation")
            if isinstance(authority, dict)
            else None
        )
        offset = (
            observation.get("detected_broker_offset_seconds")
            if isinstance(observation, dict)
            else None
        )
        if isinstance(offset, int) and not isinstance(offset, bool):
            previous_offset = offset
            break
    return capture_live_mt5_snapshot(
        canonical_symbol,
        previous_broker_offset_seconds=previous_offset,
    )


def update_virtual_trades(args: argparse.Namespace) -> None:
    collector = _collector(args)
    pair_key = _pair_key(args)
    snapshot = _capture_for_collector(collector, args.canonical_symbol)
    entry = collector._event_for(pair_key, "entry")["payload"]["branches"]
    results: dict[str, object] = {}
    for branch in ("baseline", "candidate"):
        if not bool(entry[branch]["is_actual_trade"]):
            results[branch] = {"action": "NO_ACTUAL_VIRTUAL_TRADE"}
            continue
        update = collector.update_virtual_trade(
            pair_key=pair_key,
            branch=branch,
            bid=snapshot.bid,
            ask=snapshot.ask,
            broker_epoch=snapshot.tick_epoch,
            time_authority=snapshot.time_authority(),
        )
        results[branch] = {
            "action": update.action,
            "terminal_appended": (
                update.terminal_write.appended
                if update.terminal_write is not None
                else None
            ),
        }
    print(
        json.dumps(
            {
                "result": "SPRINT93_2B_VIRTUAL_TRADES_UPDATED",
                "pair_key": list(pair_key),
                "branches": results,
                "real_order_send_allowed": False,
                "production_execution_enabled": False,
            },
            sort_keys=True,
        )
    )


def timebox_close(args: argparse.Namespace) -> None:
    collector = _collector(args)
    pair_key = _pair_key(args)
    snapshot = _capture_for_collector(collector, args.canonical_symbol)
    authority = snapshot.time_authority()
    offset = int(authority["observation"]["detected_broker_offset_seconds"])
    end_epoch = int(
        datetime.fromisoformat(
            collector.activation.exclusive_45_day_end_utc.replace("Z", "+00:00")
        ).timestamp()
    )
    final_broker_epoch = end_epoch + offset - 900
    final_rows = [
        asdict(rate) for rate in snapshot.rates if rate.time == final_broker_epoch
    ]
    if len(final_rows) != 1:
        raise RuntimeError("live MT5 snapshot lacks the frozen final M15 candle")
    entry = collector._event_for(pair_key, "entry")["payload"]["branches"]
    results: dict[str, object] = {}
    for branch in ("baseline", "candidate"):
        if not bool(entry[branch]["is_actual_trade"]):
            results[branch] = {"action": "NO_ACTUAL_VIRTUAL_TRADE"}
            continue
        closed = collector.timebox_close_virtual_trade(
            pair_key=pair_key,
            branch=branch,
            final_completed_candle=final_rows[0],
            point=snapshot.point,
            time_authority=authority,
        )
        results[branch] = {
            "action": "TIMEBOX_MTM_CLOSED",
            "net_r": closed.settlement.net_r,
            "terminal_appended": (
                closed.terminal_write.appended
                if closed.terminal_write is not None
                else None
            ),
        }
    print(
        json.dumps(
            {
                "result": "SPRINT93_2B_TIMEBOX_CLOSE_COMPLETE",
                "pair_key": list(pair_key),
                "branches": results,
                "real_order_send_allowed": False,
                "production_execution_enabled": False,
            },
            sort_keys=True,
        )
    )


def finalize_settlement(args: argparse.Namespace) -> None:
    collector = _collector(args)
    pair_key = _pair_key(args)
    write = collector.finalize_settlement(pair_key=pair_key)
    print(
        json.dumps(
            {
                "result": "SPRINT93_2B_PAIR_SETTLED",
                "pair_key": list(pair_key),
                "appended": write.appended,
                "event_sha256": write.event_sha256,
                "real_order_send_allowed": False,
                "production_execution_enabled": False,
            },
            sort_keys=True,
        )
    )


def verify_package(_args: argparse.Namespace) -> None:
    for path in (PAIRED_EXECUTOR_PATH, ACTIVATION_RUNNER_PATH):
        verify_package_safety(ROOT / path)
    print("SPRINT93_2B_PACKAGE_VERIFY_PASS")


def _activation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(manifest=DEFAULT_MANIFEST)
    parser.add_argument(
        "--no-forward-outcome-access-verified",
        action="store_true",
        required=True,
    )


def _published_arguments(parser: argparse.ArgumentParser) -> None:
    _activation_arguments(parser)
    parser.add_argument("--manifest-commit-sha", required=True)


def _pair_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--canonical-symbol", choices=("BTCUSD", "ETHUSD"), required=True
    )
    parser.add_argument("--decision-candle-open-utc", required=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)

    package = subcommands.add_parser("verify-package")
    package.set_defaults(handler=verify_package)

    create = subcommands.add_parser("create-manifest")
    _activation_arguments(create)
    create.add_argument("--activation-pr-number", type=int, required=True)
    create.set_defaults(handler=create_manifest)

    verify = subcommands.add_parser("verify-manifest")
    _published_arguments(verify)
    verify.set_defaults(handler=verify_manifest)

    collect = subcommands.add_parser("collect-decision")
    _published_arguments(collect)
    collect.add_argument(
        "--canonical-symbol", choices=("BTCUSD", "ETHUSD"), required=True
    )
    collect.set_defaults(handler=collect_decision)

    update = subcommands.add_parser("update-virtual-trades")
    _published_arguments(update)
    _pair_arguments(update)
    update.set_defaults(handler=update_virtual_trades)

    timebox = subcommands.add_parser("timebox-close")
    _published_arguments(timebox)
    _pair_arguments(timebox)
    timebox.set_defaults(handler=timebox_close)

    settle = subcommands.add_parser("finalize-settlement")
    _published_arguments(settle)
    _pair_arguments(settle)
    settle.set_defaults(handler=finalize_settlement)
    return result


def main() -> None:
    args = parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
