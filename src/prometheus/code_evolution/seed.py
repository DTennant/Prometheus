from __future__ import annotations

from prometheus.code_evolution._seed_agent import _SEED_AGENT_PY
from prometheus.code_evolution._seed_context import _SEED_CONTEXT_PY
from prometheus.code_evolution._seed_diff import _SEED_DIFF_PY
from prometheus.code_evolution._seed_prompts import _SEED_PROMPTS_PY
from prometheus.code_evolution._seed_tools import _SEED_TOOLS_PY
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
RUN apt-get update && \\
    apt-get install -y --no-install-recommends git ripgrep && \\
    rm -rf /var/lib/apt/lists/*
RUN mkdir -p /workspace
COPY agent_lib/ /opt/agent_lib/
RUN pip install --no-cache-dir -e /opt/agent_lib/
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
    api_key: str = typer.Option(
        "", "--api-key", envvar="OPENAI_API_KEY"
    ),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    system_prompt: str = typer.Option("", "--system-prompt"),
    max_iterations: int = typer.Option(60, "--max-iterations"),
) -> None:
    from agent.agent import run_agent

    output, tokens = asyncio.run(
        run_agent(
            prompt=prompt,
            system_prompt=system_prompt or "",
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
            "src/agent/prompts.py": _SEED_PROMPTS_PY,
            "src/agent/context.py": _SEED_CONTEXT_PY,
            "src/agent/diff.py": _SEED_DIFF_PY,
            "src/agent/agent.py": _SEED_AGENT_PY,
        },
    )
