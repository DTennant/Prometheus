from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_lib.ast_tools import find_classes, find_functions


@dataclass
class FileInfo:
    path: str
    size: int
    lines: int
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)


def build_file_index(
    root: Path,
    extensions: set[str] | None = None,
    max_depth: int = 10,
) -> dict[str, FileInfo]:
    if extensions is None:
        extensions = {".py"}
    index: dict[str, FileInfo] = {}
    root = root.resolve()
    for fpath in sorted(root.rglob("*")):
        if not fpath.is_file():
            continue
        if fpath.suffix not in extensions:
            continue
        rel = str(fpath.relative_to(root))
        if rel.count("/") > max_depth:
            continue
        skip = False
        for part in fpath.parts:
            if part.startswith(".") or part in (
                "__pycache__",
                "node_modules",
                ".git",
                "venv",
                ".venv",
            ):
                skip = True
                break
        if skip:
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        classes = [c.name for c in find_classes(content)]
        functions = [f.name for f in find_functions(content)]
        info = FileInfo(
            path=rel,
            size=len(content),
            lines=content.count("\n") + 1,
            classes=classes,
            functions=functions,
        )
        index[rel] = info
    return index


def format_index(index: dict[str, FileInfo]) -> str:
    lines: list[str] = []
    for path in sorted(index):
        info = index[path]
        parts = [f"{path} ({info.lines} lines)"]
        if info.classes:
            parts.append(f"  classes: {', '.join(info.classes)}")
        if info.functions:
            fns = info.functions[:10]
            if len(info.functions) > 10:
                fns.append(f"... +{len(info.functions) - 10}")
            parts.append(f"  functions: {', '.join(fns)}")
        lines.append("\n".join(parts))
    return "\n".join(lines)
