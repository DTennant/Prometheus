"""Phase-driven seed agent for code evolution stage 2+."""

from __future__ import annotations

_SEED_AGENT_PY = """\
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from agent.tools import TOOL_SCHEMAS, execute_tool
from agent.prompts import SYSTEM_PROMPT, PHASE_HINTS

PHASE_BOUNDARIES: dict[int, str] = {
    5: "locate",
    15: "edit",
    40: "verify",
}


def _build_initial_prompt(prompt: str, workspace: Path) -> str:
    return (
        f"Working directory: {workspace}\\n\\n"
        f"Task:\\n{prompt}\\n\\n"
        "Begin by exploring the workspace to understand "
        "the project structure and relevant files."
    )


def _extract_tool_calls(
    message: Any,
) -> list[tuple[str, str, dict[str, Any]]]:
    results: list[tuple[str, str, dict[str, Any]]] = []
    for tc in message.tool_calls or []:
        fn = getattr(tc, "function", None)
        if fn is None:
            continue
        try:
            args = json.loads(fn.arguments)
        except json.JSONDecodeError:
            args = {}
        results.append((tc.id, fn.name, args))
    return results


def _should_cache_read(
    tool_name: str, result: str
) -> bool:
    if tool_name != "read_file":
        return False
    if result.startswith("Error"):
        return False
    return True


def _get_current_phase(iteration: int) -> str:
    if iteration < 5:
        return "understand"
    if iteration < 15:
        return "locate"
    if iteration < 40:
        return "edit"
    return "verify"


def _build_phase_status(
    iteration: int, max_iterations: int
) -> str:
    phase = _get_current_phase(iteration)
    remaining = max_iterations - iteration
    return (
        f"[Phase: {phase} | "
        f"Iteration: {iteration + 1}/{max_iterations} | "
        f"Remaining: {remaining}]"
    )


async def _call_llm(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 8192,
) -> Any:
    return await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        tools=TOOL_SCHEMAS,
        messages=messages,
    )


def _track_usage(response: Any) -> int:
    if not response.usage:
        return 0
    prompt_tok = response.usage.prompt_tokens or 0
    completion_tok = response.usage.completion_tokens or 0
    return prompt_tok + completion_tok


def _process_tool_results(
    tool_calls: list[tuple[str, str, dict[str, Any]]],
    workspace: Path,
    ctx: ContextManager,
) -> None:
    for call_id, tool_name, args in tool_calls:
        result = execute_tool(tool_name, args, workspace)

        if _should_cache_read(tool_name, result):
            ctx.cache_file(args.get("path", ""), result)

        if tool_name == "write_file" and "path" in args:
            ctx.invalidate_file(args["path"])

        if tool_name == "edit_file" and "path" in args:
            ctx.invalidate_file(args["path"])

        ctx.add_tool_result(call_id, result)


def _inject_phase_hints_if_needed(
    iteration: int, ctx: ContextManager
) -> None:
    if iteration in PHASE_BOUNDARIES:
        phase_key = PHASE_BOUNDARIES[iteration]
        hint = PHASE_HINTS.get(phase_key, "")
        if hint:
            ctx.inject_phase_hint(hint)


def _write_metadata(
    workspace: Path, total_tokens: int
) -> None:
    metadata = {
        "tokens_used": total_tokens,
    }
    meta_path = workspace / "metadata.json"
    meta_path.write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


async def run_agent(
    prompt: str,
    system_prompt: str,
    workspace: Path,
    model: str,
    api_key: str,
    base_url: str | None = None,
    max_iterations: int = 60,
) -> tuple[str, int]:
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = AsyncOpenAI(**kwargs)

    ctx = ContextManager(token_budget=100000)

    full_system = system_prompt or SYSTEM_PROMPT
    ctx.set_system_message(full_system)

    initial_prompt = _build_initial_prompt(prompt, workspace)
    ctx.add_user_message(initial_prompt)

    total_tokens = 0
    output = ""
    last_phase = "understand"

    for iteration in range(max_iterations):
        current_phase = _get_current_phase(iteration)
        if current_phase != last_phase:
            _inject_phase_hints_if_needed(iteration, ctx)
            last_phase = current_phase

        if ctx.should_compact():
            ctx.compact()

        status = _build_phase_status(iteration, max_iterations)
        messages = ctx.get_messages()

        if messages and messages[-1].get("role") == "user":
            last_content = messages[-1].get("content", "")
            if not last_content.startswith("[Phase:"):
                messages[-1] = {
                    "role": "user",
                    "content": f"{status}\\n{last_content}",
                }

        response = await _call_llm(client, model, messages)
        total_tokens += _track_usage(response)

        choice = response.choices[0]
        msg_content = choice.message.content or ""

        if msg_content:
            output = msg_content

        if choice.finish_reason != "tool_calls":
            break

        ctx.add_message(choice.message)

        tool_calls = _extract_tool_calls(choice.message)
        if not tool_calls:
            break

        _process_tool_results(tool_calls, workspace, ctx)

    _write_metadata(workspace, total_tokens)
    return output, total_tokens


class ContextManager:
    def __init__(self, token_budget: int = 100000) -> None:
        self.token_budget = token_budget
        self.messages: list[dict[str, Any]] = []
        self.file_cache: dict[str, str] = {}
        self._system_msg: dict[str, str] | None = None
        self._compaction_count = 0

    def set_system_message(self, content: str) -> None:
        self._system_msg = {
            "role": "system",
            "content": content,
        }

    def add_user_message(self, content: str) -> None:
        self.messages.append(
            {"role": "user", "content": content}
        )

    def add_message(self, msg: Any) -> None:
        if isinstance(msg, dict):
            self.messages.append(msg)
        else:
            entry: dict[str, Any] = {
                "role": getattr(msg, "role", "assistant"),
            }
            content = getattr(msg, "content", None)
            if content:
                entry["content"] = content
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ]
            self.messages.append(entry)

    def add_tool_result(
        self, tool_call_id: str, result: str
    ) -> None:
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
        )

    def inject_phase_hint(self, text: str) -> None:
        self.messages.append(
            {"role": "user", "content": text}
        )

    def cache_file(self, path: str, content: str) -> None:
        self.file_cache[path] = content

    def invalidate_file(self, path: str) -> None:
        self.file_cache.pop(path, None)

    def _estimate_tokens(self) -> int:
        total = 0
        if self._system_msg:
            total += len(self._system_msg["content"]) // 4
        for msg in self.messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for item in content:
                    total += len(str(item)) // 4
            tc = msg.get("tool_calls")
            if tc:
                total += len(str(tc)) // 4
        for cached in self.file_cache.values():
            total += len(cached) // 8
        return total

    def should_compact(self) -> bool:
        estimated = self._estimate_tokens()
        threshold = int(self.token_budget * 0.7)
        return estimated > threshold

    def compact(self) -> None:
        self._compaction_count += 1
        keep_recent = 12

        if len(self.messages) <= keep_recent + 1:
            return

        recent = self.messages[-keep_recent:]
        old = self.messages[:-keep_recent]

        summary_parts: list[str] = []
        for msg in old:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                truncated = content[:300]
                summary_parts.append(
                    f"[{role}]: {truncated}"
                )
            elif role == "tool":
                tool_id = msg.get("tool_call_id", "?")
                truncated = str(content)[:200]
                summary_parts.append(
                    f"[tool {tool_id}]: {truncated}"
                )

        visible = summary_parts[-25:]
        summary_text = (
            f"[Compaction #{self._compaction_count}] "
            "Previous conversation summary "
            f"({len(old)} messages compacted):\\n"
            + "\\n".join(visible)
        )

        cached_info = ""
        if self.file_cache:
            paths = list(self.file_cache.keys())[:20]
            cached_info = (
                "\\n\\nFiles in cache (still available): "
                + ", ".join(paths)
            )

        self.messages = [
            {
                "role": "user",
                "content": summary_text + cached_info,
            }
        ] + recent

    def get_messages(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if self._system_msg:
            result.append(self._system_msg)
        result.extend(self.messages)
        return result

    def get_file_from_cache(
        self, path: str
    ) -> str | None:
        return self.file_cache.get(path)

    def get_stats(self) -> dict[str, Any]:
        return {
            "message_count": len(self.messages),
            "cached_files": len(self.file_cache),
            "estimated_tokens": self._estimate_tokens(),
            "compaction_count": self._compaction_count,
            "token_budget": self.token_budget,
        }
"""
