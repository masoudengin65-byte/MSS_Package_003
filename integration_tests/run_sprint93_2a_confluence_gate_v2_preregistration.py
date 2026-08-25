"""Write or verify canonical Sprint 93.2A V2 preregistration."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

from mss.analysis.sprint93_confluence_gate_v2_preregistration import (
    Sprint93ConfluenceGateV2Preregistration as C,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/MSS_Sprint93_2A_Confluence_Gate_V2_Preregistration.json"


def git_bytes(path: str, *, commit: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:{path}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def resolve_baseline_commit() -> str:
    resolved = subprocess.run(
        ["git", "rev-parse", f"{C.BASELINE_COMMIT}^{{commit}}"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    C._validate_component_identity(resolved, C.EXPECTED_STRATEGY_COMPONENT_IDENTITY)
    return resolved


def git_blob_sha256(path: str, *, commit: str) -> str:
    return hashlib.sha256(git_bytes(path, commit=commit)).hexdigest()


def verify_opaque_blob(raw_blob: bytes, expected_sha256: str, *, label: str) -> None:
    if hashlib.sha256(raw_blob).hexdigest() != expected_sha256:
        raise RuntimeError(f"{label} frozen Git blob SHA256 mismatch")


def transitive_closure(*, commit: str) -> tuple[str, ...]:
    pending = list(C.STRATEGY_COMPONENT_ROOTS)
    found: set[str] = set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        tree = ast.parse(git_bytes(path, commit=commit).decode("utf-8-sig"))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
        for module in modules:
            candidate = "src/" + module.replace(".", "/") + ".py"
            if not module.startswith("mss.") or candidate in found:
                continue
            exists = subprocess.run(
                ["git", "cat-file", "-e", f"{commit}:{candidate}"],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0
            if exists:
                pending.append(candidate)
    return tuple(sorted(found))


def component_identity(*, commit: str) -> tuple[tuple[str, str], ...]:
    transitive_paths = transitive_closure(commit=commit)
    if transitive_paths != C.TRANSITIVE_STRATEGY_COMPONENT_FILES:
        raise RuntimeError("40-file transitive internal mss closure differs from frozen universe")
    paths = tuple(sorted(transitive_paths + C.PACKAGE_INITIALIZER_FILES))
    if paths != C.REQUIRED_STRATEGY_COMPONENT_FILES:
        raise RuntimeError("42-file component identity differs from closure plus package initializers")
    identity = tuple((path, git_blob_sha256(path, commit=commit)) for path in paths)
    C._validate_component_identity(commit, identity)
    return identity


def verify_protected_source_artifacts(*, commit: str) -> None:
    for path, _schema_identifier, expected_sha256 in C.PROTECTED_SOURCE_ARTIFACTS:
        raw_blob = git_bytes(path, commit=commit)
        verify_opaque_blob(raw_blob, expected_sha256, label=path)


def rebuild() -> dict[str, object]:
    commit = resolve_baseline_commit()
    identity = component_identity(commit=commit)
    verify_protected_source_artifacts(commit=commit)
    return C().build(baseline_commit=commit, component_identity=identity)


def canonical(payload: object) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def deterministic_rebuild() -> bytes:
    first = rebuild()
    second = rebuild()
    if first is second or first != second:
        raise RuntimeError("two independent in-memory artifacts differ")
    first_preproof = canonical(first)
    second_preproof = canonical(second)
    if first_preproof != second_preproof:
        raise RuntimeError("two independent canonical serialized artifacts differ")
    if first.get("audit", {}).get("deterministic_rebuild") is not False or second.get("audit", {}).get("deterministic_rebuild") is not False:
        raise RuntimeError("deterministic rebuild was claimed before proof")
    first["audit"]["deterministic_rebuild"] = True
    second["audit"]["deterministic_rebuild"] = True
    if first != second:
        raise RuntimeError("proved artifacts diverged while recording determinism")
    first_final = canonical(first)
    second_final = canonical(second)
    if first_final != second_final:
        raise RuntimeError("proved canonical artifacts differ")
    return first_final


def report_snapshot() -> dict[str, object]:
    raw = OUTPUT.read_bytes()
    stat = OUTPUT.stat()
    return {
        "raw": raw,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def checkout_representation_matches(checkout: bytes, canonical_lf: bytes) -> bool:
    return checkout == canonical_lf or checkout == canonical_lf.replace(b"\n", b"\r\n")


def verify_committed_report(before: dict[str, object], rendered: bytes) -> None:
    if not checkout_representation_matches(before["raw"], rendered):
        raise RuntimeError("committed report is not the complete canonical LF/CRLF artifact")
    after = report_snapshot()
    fingerprint_fields = ("sha256", "size", "mtime_ns")
    if any(before[field] != after[field] for field in fingerprint_fields):
        raise RuntimeError("verification changed committed report SHA256, size, or mtime")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    if args.verify:
        before = report_snapshot()
        rendered = deterministic_rebuild()
        verify_committed_report(before, rendered)
        print("PREREGISTRATION_VERIFY_PASS")
        return

    rendered = deterministic_rebuild()
    try:
        with OUTPUT.open("xb") as stream:
            stream.write(rendered)
    except FileExistsError as exc:
        raise RuntimeError(f"refusing to overwrite existing report: {OUTPUT}") from exc


if __name__ == "__main__":
    main()
