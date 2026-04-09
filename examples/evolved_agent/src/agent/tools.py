from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file at the given path. "
                "Use this to understand existing code before making "
                "changes. Returns the full file content as text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": ("File path relative to the workspace root"),
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
                "Write content to a file, creating parent directories "
                "if they do not exist. Use this to create new files. "
                "For modifying existing files, prefer edit_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": ("File path relative to the workspace root"),
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
            "name": "edit_file",
            "description": (
                "Edit a file by replacing an exact string match. "
                "Always read_file first to see current content. "
                "The old_text must appear exactly once in the file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": ("File path relative to the workspace root"),
                    },
                    "old_text": {
                        "type": "string",
                        "description": ("Exact text to find — must match uniquely"),
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": (
                "List files and subdirectories at the given path. "
                "Directories are shown with a trailing slash. "
                "Use this to explore project structure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": ("Directory path relative to workspace (default: root)"),
                        "default": ".",
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
                "Search for a regex pattern across files using grep. "
                "Searches .py, .js, .ts, .json, .md, and .yaml files. "
                "Returns matching lines with file paths and numbers."
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
                        "description": ("Directory to search (default: workspace root)"),
                        "default": ".",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Execute a shell command in the workspace directory. "
                "Has a 120-second timeout. Returns stdout, stderr, "
                "and exit code. Use for builds, installs, etc."
            ),
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
                "Run pytest on the workspace or a specific path. "
                "Uses --tb=long for detailed tracebacks and 120s "
                "timeout. Always run after making code changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": ("Test file or directory (default: workspace root)"),
                        "default": ".",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": (
                "Show git diff output for the workspace repository. "
                "Use staged=true to see staged changes only. "
                "Useful for reviewing changes before committing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": ("If true, show only staged changes (git diff --staged)"),
                        "default": False,
                    },
                },
            },
        },
    },
]


def _resolve_safe(workspace: Path, relpath: str) -> Path | None:
    resolved = (workspace / relpath).resolve()
    if not resolved.is_relative_to(workspace.resolve()):
        return None
    return resolved


def execute_tool(name: str, args: dict[str, Any], workspace: Path) -> str:
    try:
        if name == "read_file":
            return _tool_read_file(args, workspace)
        if name == "write_file":
            return _tool_write_file(args, workspace)
        if name == "edit_file":
            return _tool_edit_file(args, workspace)
        if name == "list_directory":
            return _tool_list_directory(args, workspace)
        if name == "search_files":
            return _tool_search_files(args, workspace)
        if name == "execute_command":
            return _tool_execute_command(args, workspace)
        if name == "run_tests":
            return _tool_run_tests(args, workspace)
        if name == "git_diff":
            return _tool_git_diff(args, workspace)
        return f"Error: unknown tool: {name}"
    except subprocess.TimeoutExpired:
        return f"Error: {name} timed out"
    except Exception as exc:
        return f"Error executing {name}: {exc}"


def _tool_read_file(args: dict[str, Any], workspace: Path) -> str:
    target = _resolve_safe(workspace, args["path"])
    if target is None:
        return "Error: path escapes workspace"
    if not target.exists():
        return f"Error: file not found: {args['path']}"
    content: str = target.read_text(encoding="utf-8")
    return content


def _tool_write_file(args: dict[str, Any], workspace: Path) -> str:
    target = _resolve_safe(workspace, args["path"])
    if target is None:
        return "Error: path escapes workspace"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(args["content"], encoding="utf-8")
    return f"Wrote {len(args['content'])} bytes to {args['path']}"


def _tool_edit_file(args: dict[str, Any], workspace: Path) -> str:
    target = _resolve_safe(workspace, args["path"])
    if target is None:
        return "Error: path escapes workspace"
    if not target.exists():
        return f"Error: file not found: {args['path']}"
    content = target.read_text(encoding="utf-8")
    old = args["old_text"]
    new = args["new_text"]
    if old not in content:
        return f"Error: old_text not found in {args['path']}"
    if content.count(old) > 1:
        return (
            f"Error: old_text found {content.count(old)} times "
            f"in {args['path']}. Provide more context."
        )
    content = content.replace(old, new, 1)
    target.write_text(content, encoding="utf-8")
    return f"Edited {args['path']}"


def _tool_list_directory(args: dict[str, Any], workspace: Path) -> str:
    target = _resolve_safe(workspace, args.get("path", "."))
    if target is None:
        return "Error: path escapes workspace"
    if not target.is_dir():
        return f"Error: not a directory: {args.get('path', '.')}"
    entries = sorted(target.iterdir())
    return "\n".join(f"{e.name}/" if e.is_dir() else e.name for e in entries)


def _tool_search_files(args: dict[str, Any], workspace: Path) -> str:
    target = _resolve_safe(workspace, args.get("path", "."))
    if target is None:
        return "Error: path escapes workspace"
    include_flags: list[str] = []
    for ext in ("py", "js", "ts", "json", "md", "yaml"):
        include_flags.extend(["--include", f"*.{ext}"])
    result = subprocess.run(
        ["grep", "-rn", *include_flags, args["pattern"], str(target)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(workspace),
    )
    out = result.stdout.strip()
    if not out:
        return "No matches found."
    lines = out.split("\n")
    if len(lines) > 50:
        return "\n".join(lines[:50]) + f"\n... ({len(lines)} total matches)"
    return out


def _tool_execute_command(args: dict[str, Any], workspace: Path) -> str:
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
        out += f"\nSTDERR:\n{result.stderr}"
    if result.returncode != 0:
        out += f"\nExit code: {result.returncode}"
    return out.strip() or "(no output)"


def _tool_run_tests(args: dict[str, Any], workspace: Path) -> str:
    test_path = args.get("test_path", ".")
    target = _resolve_safe(workspace, test_path)
    if target is None:
        return "Error: path escapes workspace"
    result = subprocess.run(
        ["python", "-m", "pytest", str(target), "-x", "--tb=long", "-q"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = ""
    if result.stdout:
        out += result.stdout
    if result.stderr:
        out += f"\nSTDERR:\n{result.stderr}"
    if result.returncode != 0:
        out += f"\nExit code: {result.returncode}"
    return out.strip() or "(no output)"


def _tool_git_diff(args: dict[str, Any], workspace: Path) -> str:
    staged = args.get("staged", False)
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--staged")
    result = subprocess.run(
        cmd,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "not a git repository" in stderr.lower():
            return "Error: workspace is not a git repository"
        return f"Error: git diff failed: {stderr}"
    out = result.stdout.strip()
    if not out:
        label = "staged " if staged else ""
        return f"No {label}changes detected."
    lines = out.split("\n")
    if len(lines) > 200:
        return "\n".join(lines[:200]) + f"\n... ({len(lines)} total lines, truncated)"
    return out
