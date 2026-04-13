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
        f"Working directory: {workspace}\n\n"
        f"{plan_text}\n\n"
        f"Task: {prompt}\n\n"
        f"IMPORTANT REMINDERS:\n"
        f"- If you write any .py files, they must contain ONLY valid Python code.\n"
        f"- Do NOT write English prose, markdown, explanations, or test summaries into .py files.\n"
        f"- Python files must start with valid Python syntax (imports, class/def, comments "
        f"starting with #, etc.) - never with asterisks, sentences, or markdown.\n"
        f"- After writing code to a .py file, use check_syntax to verify it before finishing.\n"
        f"- A solution.py file should contain ONLY the Python implementation, nothing else."
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
            max_tokens=8192,
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
