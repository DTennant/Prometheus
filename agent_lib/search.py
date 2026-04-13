from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SearchResult:
    file: str
    line: int
    content: str
    context_before: list[str]
    context_after: list[str]


def ranked_search(
    root: Path,
    query: str,
    *,
    context_lines: int = 2,
    max_results: int = 30,
    include: str = "*.py",
) -> list[SearchResult]:
    results = _rg_search(root, query, context_lines, max_results, include)
    if results is not None:
        return results
    return _grep_search(root, query, context_lines, max_results, include)


def _rg_search(
    root: Path,
    query: str,
    context_lines: int,
    max_results: int,
    include: str,
) -> list[SearchResult] | None:
    try:
        result = subprocess.run(
            [
                "rg",
                "--json",
                f"-C{context_lines}",
                f"--max-count={max_results}",
                f"--glob={include}",
                query,
                str(root),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    import json

    results: list[SearchResult] = []
    pending_context: list[str] = []

    for line in result.stdout.strip().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "match":
            data = entry["data"]
            path = data["path"]["text"]
            try:
                rel = str(Path(path).relative_to(root))
            except ValueError:
                rel = path
            lineno = data["line_number"]
            text = data["lines"]["text"].rstrip("\n")
            results.append(
                SearchResult(
                    file=rel,
                    line=lineno,
                    content=text,
                    context_before=list(pending_context),
                    context_after=[],
                )
            )
            pending_context = []
            if len(results) >= max_results:
                break
        elif entry.get("type") == "context":
            data = entry["data"]
            text = data["lines"]["text"].rstrip("\n")
            if results and not results[-1].context_after:
                results[-1].context_after.append(text)
            else:
                pending_context.append(text)

    return results


def _grep_search(
    root: Path,
    query: str,
    context_lines: int,
    max_results: int,
    include: str,
) -> list[SearchResult]:
    try:
        result = subprocess.run(
            [
                "grep",
                "-rn",
                f"--include={include}",
                f"-C{context_lines}",
                query,
                str(root),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return []

    results: list[SearchResult] = []
    for line in result.stdout.strip().splitlines():
        match = re.match(r"^(.+?):(\d+):(.*)", line)
        if match:
            path, lineno_str, content = match.groups()
            try:
                rel = str(Path(path).relative_to(root))
            except ValueError:
                rel = path
            results.append(
                SearchResult(
                    file=rel,
                    line=int(lineno_str),
                    content=content,
                    context_before=[],
                    context_after=[],
                )
            )
            if len(results) >= max_results:
                break
    return results


def format_results(results: list[SearchResult]) -> str:
    if not results:
        return "No matches found."
    lines: list[str] = []
    for r in results:
        lines.append(f"{r.file}:{r.line}: {r.content}")
    return "\n".join(lines)
