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
        "You are a coding assistant. You can read files, write files, "
        "list directories, and execute shell commands to solve tasks. "
        "Work inside the given workspace directory.",
        "--system-prompt",
    ),
    max_iterations: int = typer.Option(30, "--max-iterations"),
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
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, creating it if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                },
                "required": ["path", "content"],
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
                        "description": "Directory path",
                        "default": ".",
                    },
                },
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
                        "description": "Shell command",
                    },
                },
                "required": ["command"],
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

        if name == "execute_command":
            result = subprocess.run(
                args["command"],
                shell=True,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=30,
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
    except Exception as exc:
        return f"Error executing {name}: {exc}"
"""

_SEED_AGENT_PY = """\
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from agent.tools import TOOL_SCHEMAS, execute_tool


async def run_agent(
    prompt: str,
    system_prompt: str,
    workspace: Path,
    model: str,
    api_key: str,
    base_url: str | None = None,
    max_iterations: int = 30,
) -> tuple[str, int]:
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = AsyncOpenAI(**kwargs)

    total_tokens = 0
    augmented_prompt = f"Working directory: {workspace}\\n\\n{prompt}"
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": augmented_prompt},
    ]

    output = ""
    for _ in range(max_iterations):
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
            "src/agent/agent.py": _SEED_AGENT_PY,
        },
    )
