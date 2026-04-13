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
        "and running tests to verify your changes.\n\n"
        "CRITICAL RULES - READ CAREFULLY:\n"
        "1. PYTHON FILES MUST CONTAIN ONLY VALID PYTHON CODE. "
        "When you write a solution.py or any .py file, write ONLY the Python source code. "
        "NEVER write explanations, test summaries, markdown, asterisks, or prose into .py files. "
        "If you do, the write_file tool will REJECT it with an error.\n"
        "2. The ONLY content allowed in a .py file is: imports, class definitions, "
        "function definitions, comments starting with #, and Python statements. "
        "NOTHING ELSE.\n"
        "3. After completing a task (e.g. writing solution.py), do NOT write a summary "
        "or explanation into the .py file. The .py file is the code itself.\n"
        "4. Never start a .py file with *, **, or any English sentence. "
        "The first token must be valid Python.\n"
        "5. Always read relevant files before editing.\n"
        "6. Run tests after making changes to verify correctness.\n"
        "7. Work inside the given workspace directory.\n"
        "8. When asked to add tests, write them to the correct test file and "
        "ensure they can be discovered and run by pytest.\n"
        "9. When writing test files, make sure they follow the existing test structure "
        "and import from the correct modules.\n"
        "10. After writing any .py file, use check_syntax to verify it is valid Python before proceeding.",
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
