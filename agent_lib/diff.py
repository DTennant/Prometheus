from __future__ import annotations

import difflib
from pathlib import Path


def unified_diff(old: str, new: str, path: str = "file") -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)


def apply_patch(root: Path, patch_text: str) -> list[str]:
    modified: list[str] = []
    current_file: str | None = None
    hunks: list[tuple[int, list[str], list[str]]] = []
    hunk_old: list[str] = []
    hunk_new: list[str] = []
    hunk_start = 0

    for line in patch_text.splitlines():
        if line.startswith("--- a/"):
            continue
        if line.startswith("+++ b/"):
            if current_file and hunks:
                _apply_hunks(root, current_file, hunks)
                modified.append(current_file)
                hunks = []
            current_file = line[6:]
            continue
        if line.startswith("@@"):
            if hunk_old or hunk_new:
                hunks.append((hunk_start, hunk_old, hunk_new))
            parts = line.split()
            old_range = parts[1]
            hunk_start = abs(int(old_range.split(",")[0]))
            hunk_old = []
            hunk_new = []
            continue
        if line.startswith("-"):
            hunk_old.append(line[1:])
        elif line.startswith("+"):
            hunk_new.append(line[1:])
        else:
            ctx = line[1:] if line.startswith(" ") else line
            hunk_old.append(ctx)
            hunk_new.append(ctx)

    if hunk_old or hunk_new:
        hunks.append((hunk_start, hunk_old, hunk_new))
    if current_file and hunks:
        _apply_hunks(root, current_file, hunks)
        modified.append(current_file)

    return modified


def _apply_hunks(
    root: Path,
    path: str,
    hunks: list[tuple[int, list[str], list[str]]],
) -> None:
    fpath = root / path
    if not fpath.exists():
        content_lines: list[str] = []
    else:
        content_lines = fpath.read_text(encoding="utf-8").splitlines()

    offset = 0
    for start, old_lines, new_lines in hunks:
        idx = start - 1 + offset
        del content_lines[idx : idx + len(old_lines)]
        for i, new_line in enumerate(new_lines):
            content_lines.insert(idx + i, new_line)
        offset += len(new_lines) - len(old_lines)

    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
