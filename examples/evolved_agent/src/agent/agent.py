from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from agent.context import ContextManager
from agent.planner import TaskPlanner
from agent.tools import TOOL_SCHEMAS, execute_tool

_EXPLORATION_TOOLS = {"list_directory", "read_file", "search_files"}
_MUTATION_TOOLS = {"write_file", "edit_file"}
_TEST_TOOLS = {"run_tests"}
_REVIEW_TOOLS = {"git_diff"}

MAX_TOOL_RETRIES = 2


async def run_agent(
    prompt: str,
    system_prompt: str,
    workspace: Path,
    model: str,
    api_key: str,
    base_url: str | None = None,
    max_iterations: int = 40,
) -> tuple[str, int]:
    """Run the three-phase agent loop: plan, execute, verify."""
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = AsyncOpenAI(**kwargs)

    planner = TaskPlanner()
    ctx = ContextManager(token_budget=80000, keep_recent=12)

    steps = planner.decompose(prompt)
    plan_text = planner.format_plan()

    augmented_prompt = f"Working directory: {workspace}\n\n{plan_text}\n\nTask: {prompt}"
    ctx.add_message({"role": "system", "content": system_prompt})
    ctx.add_message({"role": "user", "content": augmented_prompt})

    output = ""
    tools_used: set[str] = set()
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        if ctx.should_compact():
            ctx.compact()

        response = await client.chat.completions.create(
            model=model,
            max_tokens=4096,
            tools=TOOL_SCHEMAS,
            messages=ctx.get_messages(),
        )

        if response.usage:
            tokens = (response.usage.prompt_tokens or 0) + (response.usage.completion_tokens or 0)
            ctx.record_tokens(tokens)

        choice = response.choices[0]
        output = choice.message.content or ""

        if choice.finish_reason != "tool_calls":
            break

        ctx.add_message(choice.message)

        for tc in choice.message.tool_calls or []:
            fn = getattr(tc, "function", None)
            if fn is None:
                continue

            tool_name = fn.name
            try:
                args = json.loads(fn.arguments)
            except json.JSONDecodeError:
                args = {}

            result = _execute_with_retry(tool_name, args, workspace)
            tools_used.add(tool_name)

            ctx.add_message(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

        _update_plan_progress(planner, tools_used, steps)

    output, verify_tokens = await _verify_completion(
        client=client,
        model=model,
        ctx=ctx,
        workspace=workspace,
        max_extra_iterations=max(5, max_iterations - iteration),
    )
    ctx.record_tokens(verify_tokens)

    metadata = {
        "tokens_used": ctx.total_tokens_used,
        "iterations": iteration,
        "tools_used": sorted(tools_used),
        "plan_completion": planner.format_plan(),
    }
    meta_path = workspace / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return output, ctx.total_tokens_used


def _execute_with_retry(
    name: str,
    args: dict[str, Any],
    workspace: Path,
) -> str:
    result = execute_tool(name, args, workspace)

    retries = 0
    while result.startswith("Error") and retries < MAX_TOOL_RETRIES:
        retries += 1
        result = execute_tool(name, args, workspace)

    return result


def _update_plan_progress(
    planner: TaskPlanner,
    tools_used: set[str],
    steps: list[Any],
) -> None:
    for i, step in enumerate(steps):
        if step.completed:
            continue
        needed = set(step.tools_needed)
        if needed and needed.issubset(tools_used):
            planner.mark_complete(i)


async def _verify_completion(
    client: AsyncOpenAI,
    model: str,
    ctx: ContextManager,
    workspace: Path,
    max_extra_iterations: int = 5,
) -> tuple[str, int]:
    verify_prompt = (
        "Review your work. Have you completed the task fully? "
        "If yes, provide a brief summary of what was done. "
        "If not, explain what remains and continue working."
    )
    ctx.add_message({"role": "user", "content": verify_prompt})

    total_tokens = 0

    for _ in range(max_extra_iterations):
        if ctx.should_compact():
            ctx.compact()

        response = await client.chat.completions.create(
            model=model,
            max_tokens=4096,
            tools=TOOL_SCHEMAS,
            messages=ctx.get_messages(),
        )

        if response.usage:
            total_tokens += (response.usage.prompt_tokens or 0) + (
                response.usage.completion_tokens or 0
            )

        choice = response.choices[0]
        output = choice.message.content or ""

        if choice.finish_reason != "tool_calls":
            return output, total_tokens

        ctx.add_message(choice.message)

        for tc in choice.message.tool_calls or []:
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            try:
                args = json.loads(fn.arguments)
            except json.JSONDecodeError:
                args = {}

            result = _execute_with_retry(fn.name, args, workspace)
            ctx.add_message(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    return output, total_tokens
