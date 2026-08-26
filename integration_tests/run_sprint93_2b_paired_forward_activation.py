"""Post-merge activation and paired-decision CLI for Sprint 93.2B."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from mss.analysis.sprint93_paired_forward_activation import (
    DEFAULT_EVIDENCE_RELATIVE_PATH,
    DEFAULT_MANIFEST_RELATIVE_PATH,
    PAIRED_EXECUTOR_PATH,
    PairedForwardEvidenceCollector,
    build_activation_manifest_after_merge,
    create_activation_manifest_once,
    verify_package_safety,
    verify_published_activation_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / DEFAULT_MANIFEST_RELATIVE_PATH
DEFAULT_EVIDENCE_JOURNAL = ROOT / DEFAULT_EVIDENCE_RELATIVE_PATH


def _json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to load {label} JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return value


def _json_array(path: Path, label: str) -> list[object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to load {label} JSON") from exc
    if not isinstance(value, list):
        raise RuntimeError(f"{label} must be a JSON array")
    return value


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_manifest(args: argparse.Namespace) -> None:
    public = _json_object(args.public_pr_metadata, "public PR metadata")
    manifest = build_activation_manifest_after_merge(
        repository_root=ROOT,
        public_pr_metadata=public,
        manifest_created_at_utc=args.created_at_utc or _now_utc_z(),
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
    return verify_published_activation_manifest(
        manifest_path=args.manifest,
        repository_root=ROOT,
        public_pr_metadata=_json_object(
            args.public_pr_metadata, "public PR metadata"
        ),
        publication_metadata=_json_object(
            args.publication_metadata, "publication metadata"
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
    result = collector.collect_decision(
        canonical_symbol=args.canonical_symbol,
        decision_candle_open_utc=args.decision_candle_open_utc,
        current_bar_epoch=args.current_bar_epoch,
        rates=_json_array(args.rates_snapshot, "rates snapshot"),
        time_authority=_json_object(args.time_authority, "time authority"),
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
                "real_order_send_allowed": False,
                "production_execution_enabled": False,
            },
            sort_keys=True,
        )
    )


def verify_package(_args: argparse.Namespace) -> None:
    verify_package_safety(ROOT / PAIRED_EXECUTOR_PATH)
    print("SPRINT93_2B_PACKAGE_VERIFY_PASS")


def _activation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(manifest=DEFAULT_MANIFEST)
    parser.add_argument(
        "--public-pr-metadata", type=Path, required=True
    )
    parser.add_argument(
        "--no-forward-outcome-access-verified",
        action="store_true",
        required=True,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)

    package = subcommands.add_parser("verify-package")
    package.set_defaults(handler=verify_package)

    create = subcommands.add_parser("create-manifest")
    _activation_arguments(create)
    create.add_argument("--created-at-utc")
    create.set_defaults(handler=create_manifest)

    verify = subcommands.add_parser("verify-manifest")
    _activation_arguments(verify)
    verify.add_argument("--publication-metadata", type=Path, required=True)
    verify.set_defaults(handler=verify_manifest)

    collect = subcommands.add_parser("collect-decision")
    _activation_arguments(collect)
    collect.add_argument("--publication-metadata", type=Path, required=True)
    collect.add_argument("--canonical-symbol", choices=("BTCUSD", "ETHUSD"), required=True)
    collect.add_argument("--decision-candle-open-utc", required=True)
    collect.add_argument("--current-bar-epoch", type=int, required=True)
    collect.add_argument("--rates-snapshot", type=Path, required=True)
    collect.add_argument("--time-authority", type=Path, required=True)
    collect.set_defaults(handler=collect_decision)
    return result


def main() -> None:
    args = parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
