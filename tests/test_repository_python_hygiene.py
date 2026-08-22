import os
from pathlib import Path
import subprocess

import mss


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGE = (ROOT / "src" / "mss").resolve()


def _tracked_paths():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )

    return tuple(
        Path(os.fsdecode(raw_path))
        for raw_path in result.stdout.split(b"\0")
        if raw_path
    )


def test_pytest_imports_mss_from_current_worktree():
    imported_package = Path(mss.__file__).resolve().parent

    assert imported_package == LOCAL_PACKAGE


def test_repository_tracks_no_python_bytecode():
    tracked_bytecode = [
        path
        for path in _tracked_paths()
        if "__pycache__" in path.parts
        or path.suffix.lower() in {".pyc", ".pyo"}
    ]

    assert tracked_bytecode == []


def test_python_bytecode_is_ignored():
    ignore_rules = (ROOT / ".gitignore").read_text(
        encoding="utf-8"
    ).splitlines()

    assert "__pycache__/" in ignore_rules
    assert "*.pyc" in ignore_rules
    assert "*.pyo" in ignore_rules
