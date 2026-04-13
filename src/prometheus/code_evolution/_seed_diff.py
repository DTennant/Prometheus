_SEED_DIFF_PY = """\
from __future__ import annotations

import difflib
from pathlib import Path


def generate_patch(workspace: Path) -> str:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.stdout.strip():
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def file_diff(
    old_content: str, new_content: str, path: str
) -> str:
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)
"""
