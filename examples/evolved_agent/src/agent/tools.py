from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace",
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
                "Write content to a file, creating dirs if needed. "
                "CRITICAL: For Python (.py) files, content must be valid Python code ONLY. "
                "NEVER write prose, markdown, asterisks, explanations, or test summaries into .py files. "
                "Python files must start with valid Python syntax (import, def, class, #, etc.). "
                "If you try to write invalid Python, the write will be REJECTED and you must retry with valid Python code."
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
                        "description": "Full file content to write. For .py files, must be valid Python code only - no markdown, no prose, no test summaries.",
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
                "Use read_file first to see the current content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Exact text to find and replace",
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
            "description": "List files and subdirectories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: .)",
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
                "Search for a pattern in files using grep. Returns matching lines with file paths."
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
                        "description": "File glob pattern to include (default: *.py)",
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
                "Run pytest on the workspace or a specific test file. "
                "Returns test output with pass/fail results."
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
                        "description": "Extra pytest arguments (e.g. '-v' for verbose)",
                        "default": "",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_syntax",
            "description": (
                "Check if a Python file has valid syntax. "
                "Use this after writing .py files to verify they are valid Python."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Python file path relative to workspace",
                    },
                },
                "required": ["path"],
            },
        },
    },
]


def _resolve_safe(workspace: Path, relpath: str) -> Path | None:
    resolved = (workspace / relpath).resolve()
    if not resolved.is_relative_to(workspace.resolve()):
        return None
    return resolved


def _validate_python_content(path: str, content: str) -> str | None:
    """Validate Python content before writing. Returns error message or None if OK."""
    if not path.endswith(".py"):
        return None
    stripped = content.strip()
    if not stripped:
        return None

    # Check for obvious non-Python content
    first_line = stripped.split("\n")[0].strip()

    # Markdown indicators at start
    if stripped[0] == "*":
        return f"REJECTED: Python file '{path}' cannot start with '*' (markdown detected). Write ONLY valid Python code."

    # Check for common prose patterns
    prose_starters = [
        "here is",
        "here's",
        "the following",
        "this file",
        "this code",
        "below is",
        "i have",
        "i've",
        "the solution",
        "the code",
        "all tests",
        "tests pass",
        "test pass",
    ]
    first_line_lower = first_line.lower()
    for starter in prose_starters:
        if first_line_lower.startswith(starter):
            return f"REJECTED: Python file '{path}' appears to start with prose/explanation ('{first_line[:50]}'). Write ONLY valid Python code."

    # Try to compile
    try:
        compile(content, path, "exec")
    except SyntaxError as e:
        return f"REJECTED: Python syntax error in '{path}': {e}. Fix the syntax before writing."
    return None


def execute_tool(name: str, args: dict[str, Any], workspace: Path) -> str:
    try:
        if name == "read_file":
            target = _resolve_safe(workspace, args["path"])
            if target is None:
                return "Error: path escapes workspace"
            if not target.exists():
                return f"Error: file not found: {args['path']}"
            content: str = target.read_text(encoding="utf-8")
            return content

        if name == "write_file":
            target = _resolve_safe(workspace, args["path"])
            if target is None:
                return "Error: path escapes workspace"
            file_content = args["content"]
            # Validate Python files
            validation_error = _validate_python_content(args["path"], file_content)
            if validation_error:
                return validation_error
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file_content, encoding="utf-8")
            return f"Wrote {len(file_content)} bytes to {args['path']}"

        if name == "edit_file":
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
            # Validate if Python file
            if args["path"].endswith(".py"):
                try:
                    compile(content, args["path"], "exec")
                except SyntaxError as e:
                    return f"REJECTED edit: would create syntax error in {args['path']}: {e}"
            target.write_text(content, encoding="utf-8")
            return f"Edited {args['path']}"

        if name == "list_directory":
            target = _resolve_safe(workspace, args.get("path", "."))
            if target is None:
                return "Error: path escapes workspace"
            if not target.is_dir():
                return f"Error: not a directory: {args.get('path', '.')}"
            entries = sorted(target.iterdir())
            return "\n".join(f"{e.name}/" if e.is_dir() else e.name for e in entries)

        if name == "search_files":
            target = _resolve_safe(workspace, args.get("path", "."))
            if target is None:
                return "Error: path escapes workspace"
            include_pattern = args.get("include", "*.py")
            result = subprocess.run(
                ["grep", "-rn", f"--include={include_pattern}", args["pattern"], str(target)],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(workspace),
            )
            out = result.stdout.strip()
            if not out:
                return "No matches found."
            lines = out.split("\n")
            if len(lines) > 50:
                return "\n".join(lines[:50]) + f"\n... ({len(lines)} total)"
            return out

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
                out += f"\nSTDERR:\n{result.stderr}"
            if result.returncode != 0:
                out += f"\nExit code: {result.returncode}"
            return out.strip() or "(no output)"

        if name == "run_tests":
            test_path = args.get("test_path", ".")
            target = _resolve_safe(workspace, test_path)
            if target is None:
                return "Error: path escapes workspace"
            extra_args = args.get("extra_args", "")
            cmd = ["python", "-m", "pytest", str(target), "--tb=short", "-v"]
            if extra_args:
                cmd.extend(extra_args.split())
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
                out += f"\nSTDERR:\n{result.stderr}"
            if result.returncode != 0:
                out += f"\nExit code: {result.returncode}"
            return out.strip() or "(no output)"

        if name == "check_syntax":
            target = _resolve_safe(workspace, args["path"])
            if target is None:
                return "Error: path escapes workspace"
            if not target.exists():
                return f"Error: file not found: {args['path']}"
            content = target.read_text(encoding="utf-8")
            try:
                compile(content, args["path"], "exec")
                return f"Syntax OK: {args['path']} is valid Python."
            except SyntaxError as e:
                return f"Syntax Error in {args['path']}: {e}\nLine {e.lineno}: {e.text}"

        return f"Error: unknown tool: {name}"
    except subprocess.TimeoutExpired:
        return f"Error: {name} timed out"
    except Exception as exc:
        return f"Error executing {name}: {exc}"
