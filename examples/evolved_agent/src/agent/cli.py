import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(add_completion=False)

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert coding assistant with 8 tools: "
    "read_file, write_file, edit_file, list_directory, "
    "search_files, execute_command, run_tests, git_diff. "
    "Follow this workflow: (1) understand the codebase by "
    "reading files, (2) plan your approach, (3) implement "
    "changes with targeted edits, (4) run tests to verify, "
    "(5) check git diff to review your changes. "
    "Always work inside the given workspace directory."
)


@app.command()
def run(
    prompt: str = typer.Option(..., "--prompt"),
    workspace: Path = typer.Option(..., "--workspace"),
    model: str = typer.Option("gpt-4.1-mini", "--model"),
    api_key: str = typer.Option("", "--api-key", envvar="OPENAI_API_KEY"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    system_prompt: str = typer.Option(_DEFAULT_SYSTEM_PROMPT, "--system-prompt"),
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
