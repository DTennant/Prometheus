_SEED_TOOLS_PY = """\
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-indexed)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (1-indexed)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file, creating parent dirs if needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace",
            "description": (
                "Replace an exact string match in a file. "
                "The old_str must appear exactly once."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "Exact text to find",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Replacement text",
                    },
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insert_line",
            "description": "Insert text before a specific line number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Line number to insert before",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to insert",
                    },
                },
                "required": ["path", "line", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and subdirectories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: .)",
                        "default": ".",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "List recursively",
                        "default": False,
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Max depth for recursive listing",
                        "default": 3,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Search for a pattern in files using ripgrep/grep."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (regex)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search (default: .)",
                        "default": ".",
                    },
                    "include": {
                        "type": "string",
                        "description": "File glob pattern (default: *.py)",
                        "default": "*.py",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_definition",
            "description": "Find where a symbol is defined.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to find",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search (default: .)",
                        "default": ".",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_references",
            "description": "Find all usages of a symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to find",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search (default: .)",
                        "default": ".",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": (
                "Run pytest on the workspace or a specific path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Test file or dir (default: .)",
                        "default": ".",
                    },
                    "extra_args": {
                        "type": "string",
                        "description": "Extra pytest args, e.g. '-x -v'",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show git diff of current changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "Show staged changes only",
                        "default": False,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git status.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def _resolve_safe(workspace: Path, relpath: str) -> Path | None:
    resolved = (workspace / relpath).resolve()
    if not resolved.is_relative_to(workspace.resolve()):
        return None
    return resolved


def _tree(directory: Path, prefix: str, depth: int, max_d: int) -> list[str]:
    if depth >= max_d:
        return []
    try:
        entries = sorted(directory.iterdir())
    except PermissionError:
        return []
    lines: list[str] = []
    dirs = [e for e in entries if e.is_dir() and e.name not in {
        "__pycache__", ".git", "node_modules", ".tox", ".mypy_cache",
    }]
    files = [e for e in entries if not e.is_dir()]
    all_items = files + dirs
    for i, entry in enumerate(all_items):
        connector = "\\u2514\\u2500\\u2500 " if i == len(all_items) - 1 else "\\u251c\\u2500\\u2500 "
        if entry.is_dir():
            lines.append(f"{prefix}{connector}{entry.name}/")
            ext = "    " if i == len(all_items) - 1 else "\\u2502   "
            lines.extend(_tree(entry, prefix + ext, depth + 1, max_d))
        else:
            lines.append(f"{prefix}{connector}{entry.name}")
    return lines


def execute_tool(
    name: str, args: dict[str, Any], workspace: Path
) -> str:
    try:
        if name == "read_file":
            target = _resolve_safe(workspace, args["path"])
            if target is None:
                return "Error: path escapes workspace"
            if not target.exists():
                return f"Error: file not found: {args['path']}"
            text = target.read_text(encoding="utf-8")
            all_lines = text.splitlines()
            start = args.get("start_line")
            end = args.get("end_line")
            if start is not None or end is not None:
                s = max((start or 1) - 1, 0)
                e = min(end or len(all_lines), len(all_lines))
                ctx = 3
                show_s = max(s - ctx, 0)
                show_e = min(e + ctx, len(all_lines))
                selected = all_lines[show_s:show_e]
                width = len(str(show_e))
                numbered = []
                for i, ln in enumerate(selected, show_s + 1):
                    numbered.append(f"{i:>{width}} | {ln}")
                return "\\n".join(numbered)
            width = len(str(len(all_lines)))
            numbered = []
            for i, ln in enumerate(all_lines, 1):
                numbered.append(f"{i:>{width}} | {ln}")
            return "\\n".join(numbered)

        if name == "write_file":
            target = _resolve_safe(workspace, args["path"])
            if target is None:
                return "Error: path escapes workspace"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(args["content"], encoding="utf-8")
            n = len(args["content"])
            return f"Wrote {n} bytes to {args['path']}"

        if name == "str_replace":
            target = _resolve_safe(workspace, args["path"])
            if target is None:
                return "Error: path escapes workspace"
            if not target.exists():
                return f"Error: file not found: {args['path']}"
            content = target.read_text(encoding="utf-8")
            old = args["old_str"]
            new = args["new_str"]
            count = content.count(old)
            if count == 0:
                return f"Error: old_str not found in {args['path']}"
            if count > 1:
                return (
                    f"Error: old_str found {count} times in "
                    f"{args['path']}. Provide more context."
                )
            content = content.replace(old, new, 1)
            target.write_text(content, encoding="utf-8")
            lines = content.splitlines()
            idx = -1
            for i, ln in enumerate(lines):
                if new and new.splitlines()[0] in ln:
                    idx = i
                    break
            if idx >= 0:
                ctx_s = max(idx - 3, 0)
                ctx_e = min(idx + 4, len(lines))
                context_lines = lines[ctx_s:ctx_e]
                preview = "\\n".join(
                    f"  {j} | {cl}"
                    for j, cl in enumerate(context_lines, ctx_s + 1)
                )
                return f"Replaced in {args['path']}:\\n{preview}"
            return f"Replaced in {args['path']}"

        if name == "insert_line":
            target = _resolve_safe(workspace, args["path"])
            if target is None:
                return "Error: path escapes workspace"
            if not target.exists():
                return f"Error: file not found: {args['path']}"
            content = target.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)
            pos = max(args["line"] - 1, 0)
            new_lines = args["text"]
            if not new_lines.endswith("\\n"):
                new_lines += "\\n"
            lines.insert(pos, new_lines)
            target.write_text("".join(lines), encoding="utf-8")
            return f"Inserted at line {args['line']} in {args['path']}"

        if name == "list_directory":
            target = _resolve_safe(workspace, args.get("path", "."))
            if target is None:
                return "Error: path escapes workspace"
            if not target.is_dir():
                p = args.get("path", ".")
                return f"Error: not a directory: {p}"
            recursive = args.get("recursive", False)
            if recursive:
                max_d = args.get("max_depth", 3)
                lines = [f"{target.name}/"]
                lines.extend(_tree(target, "", 0, max_d))
                return "\\n".join(lines)
            entries = sorted(target.iterdir())
            return "\\n".join(
                f"{e.name}/" if e.is_dir() else e.name
                for e in entries
            )

        if name == "search_files":
            target = _resolve_safe(workspace, args.get("path", "."))
            if target is None:
                return "Error: path escapes workspace"
            include = args.get("include", "*.py")
            pattern = args["pattern"]
            try:
                result = subprocess.run(
                    [
                        "rg", "-n", "--glob", include,
                        pattern, str(target),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(workspace),
                )
            except FileNotFoundError:
                result = subprocess.run(
                    [
                        "grep", "-rn",
                        f"--include={include}",
                        pattern, str(target),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(workspace),
                )
            out = result.stdout.strip()
            if not out:
                return "No matches found."
            lines = out.split("\\n")
            if len(lines) > 50:
                return (
                    "\\n".join(lines[:50])
                    + f"\\n... ({len(lines)} total matches)"
                )
            return out

        if name == "find_definition":
            target = _resolve_safe(workspace, args.get("path", "."))
            if target is None:
                return "Error: path escapes workspace"
            sym = args["symbol"]
            pat = f"def {sym}\\\\|class {sym}"
            result = subprocess.run(
                ["grep", "-rn", pat, str(target)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(workspace),
            )
            out = result.stdout.strip()
            if not out:
                return f"No definition found for '{sym}'"
            return out

        if name == "find_references":
            target = _resolve_safe(workspace, args.get("path", "."))
            if target is None:
                return "Error: path escapes workspace"
            sym = args["symbol"]
            result = subprocess.run(
                ["grep", "-rn", sym, str(target)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(workspace),
            )
            out = result.stdout.strip()
            if not out:
                return f"No references found for '{sym}'"
            lines = out.split("\\n")
            refs = [
                ln for ln in lines
                if f"def {sym}" not in ln and f"class {sym}" not in ln
            ]
            if not refs:
                return f"No references found for '{sym}' (only definitions)"
            return "\\n".join(refs)

        if name == "execute_command":
            result = subprocess.run(
                args["command"],
                shell=True,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = ""
            if result.stdout:
                out += result.stdout
            if result.stderr:
                out += f"\\nSTDERR:\\n{result.stderr}"
            if result.returncode != 0:
                out += f"\\nExit code: {result.returncode}"
            return out.strip() or "(no output)"

        if name == "run_tests":
            test_path = args.get("test_path", ".")
            target = _resolve_safe(workspace, test_path)
            if target is None:
                return "Error: path escapes workspace"
            cmd = ["python", "-m", "pytest", str(target)]
            extra = args.get("extra_args", "")
            if extra:
                cmd.extend(extra.split())
            else:
                cmd.extend(["-x", "--tb=short", "-q"])
            result = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = ""
            if result.stdout:
                out += result.stdout
            if result.stderr:
                out += f"\\nSTDERR:\\n{result.stderr}"
            if result.returncode != 0:
                out += f"\\nExit code: {result.returncode}"
            return out.strip() or "(no output)"

        if name == "git_diff":
            cmd = ["git", "diff"]
            if args.get("staged", False):
                cmd.append("--staged")
            result = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = result.stdout.strip()
            return out or "(no changes)"

        if name == "git_status":
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = result.stdout.strip()
            return out or "(clean working tree)"

        return f"Error: unknown tool: {name}"
    except subprocess.TimeoutExpired:
        return f"Error: {name} timed out"
    except Exception as exc:
        return f"Error executing {name}: {exc}"
"""
