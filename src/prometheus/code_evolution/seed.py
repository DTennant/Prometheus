from __future__ import annotations

from prometheus.code_evolution.package import AgentPackage

_SEED_PYPROJECT_TOML = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "evolved-agent"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "openai>=1.0.0",
    "typer>=0.12.0",
]

[project.scripts]
agent = "agent.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/agent"]
"""

_SEED_DOCKERFILE = """\
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && \\
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
ENTRYPOINT ["python", "-m", "agent"]
"""

_SEED_INIT_PY = ""

_SEED_MAIN_PY = """\
from agent.cli import app

if __name__ == "__main__":
    app()
"""

_SEED_CLI_PY = """\
import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(add_completion=False)


@app.command()
def run(
    prompt: str = typer.Option(..., "--prompt"),
    workspace: Path = typer.Option(..., "--workspace"),
    model: str = typer.Option("gpt-4.1-mini", "--model"),
    api_key: str = typer.Option("", "--api-key", envvar="OPENAI_API_KEY"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    system_prompt: str = typer.Option(
        "You are an expert coding assistant. You solve programming tasks "
        "by reading files, understanding code, making targeted edits, "
        "and running tests to verify your changes. Always read relevant "
        "files before editing. Run tests after making changes. "
        "Work inside the given workspace directory.",
        "--system-prompt",
    ),
    max_iterations: int = typer.Option(40, "--max-iterations"),
) -> None:
    from agent.agent import run_agent

    output, tokens = asyncio.run(
        run_agent(
            prompt=prompt,
            system_prompt=system_prompt,
            workspace=workspace,
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_iterations=max_iterations,
        )
    )
    print(output)
    print(f"tokens_used={tokens}", file=sys.stderr)
"""

_SEED_TOOLS_PY = """\
from __future__ import annotations

import json
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
            "description": "Write content to a file, creating dirs if needed.",
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
                "Search for a pattern in files using grep. "
                "Returns matching lines with file paths."
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
            content: str = target.read_text(encoding="utf-8")
            return content

        if name == "write_file":
            target = _resolve_safe(workspace, args["path"])
            if target is None:
                return "Error: path escapes workspace"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(args["content"], encoding="utf-8")
            return f"Wrote {len(args['content'])} bytes to {args['path']}"

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
            target.write_text(content, encoding="utf-8")
            return f"Edited {args['path']}"

        if name == "list_directory":
            target = _resolve_safe(workspace, args.get("path", "."))
            if target is None:
                return "Error: path escapes workspace"
            if not target.is_dir():
                return f"Error: not a directory: {args.get('path', '.')}"
            entries = sorted(target.iterdir())
            return "\\n".join(
                f"{e.name}/" if e.is_dir() else e.name for e in entries
            )

        if name == "search_files":
            target = _resolve_safe(workspace, args.get("path", "."))
            if target is None:
                return "Error: path escapes workspace"
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py",
                 args["pattern"], str(target)],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(workspace),
            )
            out = result.stdout.strip()
            if not out:
                return "No matches found."
            lines = out.split("\\n")
            if len(lines) > 50:
                return "\\n".join(lines[:50]) + f"\\n... ({len(lines)} total)"
            return out

        if name == "execute_command":
            result = subprocess.run(
                args["command"],
                shell=True,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=60,
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
            result = subprocess.run(
                ["python", "-m", "pytest", str(target),
                 "-x", "--tb=short", "-q"],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=60,
            )
            out = ""
            if result.stdout:
                out += result.stdout
            if result.stderr:
                out += f"\\nSTDERR:\\n{result.stderr}"
            if result.returncode != 0:
                out += f"\\nExit code: {result.returncode}"
            return out.strip() or "(no output)"

        return f"Error: unknown tool: {name}"
    except subprocess.TimeoutExpired:
        return f"Error: {name} timed out"
    except Exception as exc:
        return f"Error executing {name}: {exc}"
"""

_SEED_PLANNER_PY = """\
from __future__ import annotations


def create_plan(prompt: str) -> list[str]:
    steps = []
    steps.append("Read relevant files to understand the codebase")
    if any(kw in prompt.lower() for kw in ["fix", "bug", "error", "fail"]):
        steps.append("Identify the root cause of the issue")
        steps.append("Implement the fix")
        steps.append("Run tests to verify the fix")
    elif any(kw in prompt.lower() for kw in ["write", "create", "add", "implement"]):
        steps.append("Plan the implementation approach")
        steps.append("Write the code")
        steps.append("Run tests to verify correctness")
    elif any(kw in prompt.lower() for kw in ["refactor", "rename", "move", "change"]):
        steps.append("Find all references to the target")
        steps.append("Make the changes across all files")
        steps.append("Run tests to verify nothing broke")
    else:
        steps.append("Analyze what needs to be done")
        steps.append("Implement the solution")
        steps.append("Verify the result")
    return steps


def format_plan(steps: list[str]) -> str:
    lines = ["Plan:"]
    for i, step in enumerate(steps, 1):
        lines.append(f"  {i}. {step}")
    return "\\n".join(lines)
"""

_SEED_CONTEXT_PY = """\
from __future__ import annotations

from typing import Any


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    total += len(str(item)) // 4
    return total


def should_summarize(
    messages: list[dict[str, Any]], max_tokens: int = 80000
) -> bool:
    return estimate_tokens(messages) > max_tokens


def compact_messages(
    messages: list[dict[str, Any]], keep_recent: int = 10
) -> list[dict[str, Any]]:
    if len(messages) <= keep_recent + 1:
        return messages

    system = messages[0] if messages[0].get("role") == "system" else None
    recent = messages[-keep_recent:]
    old = messages[1:-keep_recent] if system else messages[:-keep_recent]

    summary_parts = []
    for msg in old:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            summary_parts.append(f"[{role}]: {content[:200]}")

    summary_text = (
        "Previous conversation summary:\\n"
        + "\\n".join(summary_parts[-20:])
    )
    summary_msg = {"role": "user", "content": summary_text}

    result: list[dict[str, Any]] = []
    if system:
        result.append(system)
    result.append(summary_msg)
    result.extend(recent)
    return result
"""

_SEED_AGENT_PY = """\
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from agent.context import compact_messages, should_summarize
from agent.planner import create_plan, format_plan
from agent.tools import TOOL_SCHEMAS, execute_tool


async def run_agent(
    prompt: str,
    system_prompt: str,
    workspace: Path,
    model: str,
    api_key: str,
    base_url: str | None = None,
    max_iterations: int = 40,
) -> tuple[str, int]:
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = AsyncOpenAI(**kwargs)

    total_tokens = 0

    plan = create_plan(prompt)
    plan_text = format_plan(plan)

    augmented_prompt = (
        f"Working directory: {workspace}\\n\\n"
        f"{plan_text}\\n\\n"
        f"Task: {prompt}"
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": augmented_prompt},
    ]

    output = ""
    for iteration in range(max_iterations):
        if should_summarize(messages):
            messages = compact_messages(messages)

        response = await client.chat.completions.create(
            model=model,
            max_tokens=4096,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        if response.usage:
            total_tokens += (response.usage.prompt_tokens or 0) + (
                response.usage.completion_tokens or 0
            )

        choice = response.choices[0]
        output = choice.message.content or ""

        if choice.finish_reason != "tool_calls":
            break

        messages.append(choice.message)

        for tc in choice.message.tool_calls or []:
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            try:
                args = json.loads(fn.arguments)
            except json.JSONDecodeError:
                args = {}

            result = execute_tool(fn.name, args, workspace)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    metadata = {"tokens_used": total_tokens}
    meta_path = workspace / "metadata.json"
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")

    return output, total_tokens
"""


def create_seed_package() -> AgentPackage:
    return AgentPackage(
        package_id="seed",
        generation=0,
        parent_id=None,
        files={
            "pyproject.toml": _SEED_PYPROJECT_TOML,
            "Dockerfile": _SEED_DOCKERFILE,
            "src/agent/__init__.py": _SEED_INIT_PY,
            "src/agent/__main__.py": _SEED_MAIN_PY,
            "src/agent/cli.py": _SEED_CLI_PY,
            "src/agent/tools.py": _SEED_TOOLS_PY,
            "src/agent/planner.py": _SEED_PLANNER_PY,
            "src/agent/context.py": _SEED_CONTEXT_PY,
            "src/agent/agent.py": _SEED_AGENT_PY,
        },
    )
