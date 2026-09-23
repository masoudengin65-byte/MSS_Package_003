"""Start the verified FIBO forward-shadow supervisor on a demo MT5 terminal."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform

import numpy

from mss.analysis.fibo_group_forward_activation import (
    REQUIRED_EXECUTION_PATHS,
    canonical_bytes,
    verify_manifest,
)
from mss.analysis.fibo_group_forward_supervisor import run_fibo_forward_supervisor


def _load(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to read {label}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return value


def _identity(root: Path) -> list[dict[str, str]]:
    rows = []
    for relative in sorted(REQUIRED_EXECUTION_PATHS):
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"frozen execution file is missing: {relative}")
        rows.append(
            {
                "path": relative,
                "git_blob_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--freeze-pr-json", type=Path, required=True)
    parser.add_argument("--publication-pr-json", type=Path, required=True)
    parser.add_argument("--terminal-path", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument(
        "--strict-preactivation",
        action="store_true",
        help="reject a launch after the first eligible boundary (legacy mode)",
    )
    args = parser.parse_args()

    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("manifest must be a JSON object")
    freeze = _load(args.freeze_pr_json, "freeze metadata")
    publication = _load(args.publication_pr_json, "publication metadata")
    publication["manifest_blob_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    versions = {"python_version": platform.python_version(), "numpy_version": str(numpy.__version__)}
    activation = verify_manifest(
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        freeze_metadata=freeze,
        publication_metadata=publication,
        runtime_versions=versions,
        observed_execution_identity=_identity(Path(__file__).resolve().parents[1]),
        no_forward_outcome_access_verified=True,
    )
    result = run_fibo_forward_supervisor(
        activation=activation,
        journal_path=args.journal,
        terminal_path=args.terminal_path,
        allow_late_arm=not args.strict_preactivation,
    )
    print("FIBO_FORWARD_SUPERVISOR_STARTED_AND_FINISHED")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
