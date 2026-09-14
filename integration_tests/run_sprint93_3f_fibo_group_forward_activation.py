"""Build and verify a write-once FIBO forward-shadow activation manifest.

This command is deliberately offline with respect to GitHub.  The caller must
provide authoritative, already-merged freeze and publication metadata.  It
never starts MT5 and never performs market-data or order operations.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess

import numpy

from mss.analysis.fibo_group_forward_activation import (
    REQUIRED_EXECUTION_PATHS,
    build_manifest,
    canonical_bytes,
    verify_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to read {label}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return value


def _git_blob(repository_root: Path, commit: str, relative: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "cat-file", "blob", f"{commit}:{relative}"],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"unable to read frozen Git blob: {relative}") from exc
    return completed.stdout


def execution_identity(
    repository_root: Path,
    *,
    commit: str = "HEAD",
) -> list[dict[str, str]]:
    rows = []
    for relative in sorted(REQUIRED_EXECUTION_PATHS):
        blob = _git_blob(repository_root, commit, relative)
        rows.append(
            {
                "path": relative,
                "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
            }
        )
    return rows


def runtime_versions() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "numpy_version": str(numpy.__version__),
    }


def build_and_verify(
    *,
    repository_root: Path,
    freeze_metadata: dict[str, object],
    publication_metadata: dict[str, object],
    manifest_created_at_utc: str,
    no_forward_outcome_access_verified: bool,
    commit: str = "HEAD",
) -> dict[str, object]:
    if not no_forward_outcome_access_verified:
        raise RuntimeError("explicit no-forward-outcome-access verification is required")
    if publication_metadata.get("state") != "MERGED":
        raise RuntimeError("FIBO manifest publication must be merged")
    if publication_metadata.get("base_branch") != "main":
        raise RuntimeError("FIBO manifest publication must target main")
    merged_at = publication_metadata.get("merged_at_utc")
    if not isinstance(merged_at, str) or not merged_at.endswith("Z"):
        raise RuntimeError("FIBO manifest publication mergedAt is required")
    datetime.fromisoformat(merged_at[:-1] + "+00:00").astimezone(timezone.utc)

    versions = runtime_versions()
    identity = execution_identity(repository_root, commit=commit)
    manifest = build_manifest(
        freeze_metadata=freeze_metadata,
        manifest_created_at_utc=manifest_created_at_utc,
        runtime_versions=versions,
        execution_identity=identity,
    )
    raw = canonical_bytes(manifest)
    publication_for_verification = dict(publication_metadata)
    publication_for_verification["manifest_blob_sha256"] = hashlib.sha256(raw).hexdigest()
    activation = verify_manifest(
        manifest=manifest,
        manifest_bytes=raw,
        freeze_metadata=freeze_metadata,
        publication_metadata=publication_for_verification,
        runtime_versions=versions,
        observed_execution_identity=identity,
        no_forward_outcome_access_verified=True,
    )
    return {
        "manifest": manifest,
        "manifest_sha256": activation.manifest_sha256,
        "first_eligible_epoch": activation.first_eligible_epoch,
        "exclusive_end_epoch": activation.exclusive_end_epoch,
        "verification": {
            "verified": True,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-pr-json", type=Path, required=True)
    parser.add_argument("--publication-json", type=Path, required=True)
    parser.add_argument("--manifest-created-at-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument(
        "--no-forward-outcome-access-verified",
        action="store_true",
    )
    args = parser.parse_args()
    result = build_and_verify(
        repository_root=ROOT,
        freeze_metadata=_load_object(args.freeze_pr_json, "freeze metadata"),
        publication_metadata=_load_object(args.publication_json, "publication metadata"),
        manifest_created_at_utc=args.manifest_created_at_utc,
        no_forward_outcome_access_verified=args.no_forward_outcome_access_verified,
        commit=args.commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(result["manifest"]))
    print("FIBO_FORWARD_ACTIVATION_MANIFEST_VERIFIED")
    print("MANIFEST_SHA256", result["manifest_sha256"])
    print("REAL_ORDER_SEND_ALLOWED", result["verification"]["real_order_send_allowed"])


if __name__ == "__main__":
    main()
