from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_AGENT_TOOLS_ANTHROPIC: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating it if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and subdirectories in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (default: working directory)",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "execute_command",
        "description": "Execute a shell command in the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command"},
            },
            "required": ["command"],
        },
    },
]

_AGENT_TOOLS_OPENAI: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in _AGENT_TOOLS_ANTHROPIC
]


def _resolve_safe(workspace: Path, relpath: str) -> Path | None:
    resolved = (workspace / relpath).resolve()
    if not resolved.is_relative_to(workspace.resolve()):
        return None
    return resolved


def _execute_tool(name: str, args: dict[str, Any], workspace: Path) -> str:
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
            return "\n".join(f"{e.name}/" if e.is_dir() else e.name for e in entries)

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
                out += f"\nSTDERR:\n{result.stderr}"
            if result.returncode != 0:
                out += f"\nExit code: {result.returncode}"
            return out.strip() or "(no output)"

        return f"Error: unknown tool: {name}"
    except Exception as exc:
        return f"Error executing {name}: {exc}"


class AnthropicAgentClient:
    def __init__(self, api_key: str, model: str, *, base_url: str | None = None) -> None:
        from anthropic import AsyncAnthropic

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)
        self._model = model

    async def run_task(
        self,
        prompt: str,
        system_prompt: str,
        max_iterations: int,
        workspace: Path,
    ) -> tuple[str, int]:
        total_tokens = 0
        augmented_prompt = f"Working directory: {workspace}\n\n{prompt}"
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": augmented_prompt},
        ]

        output = ""
        for _ in range(max_iterations):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                tools=_AGENT_TOOLS_ANTHROPIC,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )
            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
            output = "".join(text_parts)

            if response.stop_reason != "tool_use":
                return output, total_tokens

            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_input: dict[str, Any] = block.input
                    result = _execute_tool(block.name, tool_input, workspace)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})

        return output, total_tokens


class OpenAIAgentClient:
    def __init__(self, api_key: str, model: str, *, base_url: str | None = None) -> None:
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model

    async def run_task(
        self,
        prompt: str,
        system_prompt: str,
        max_iterations: int,
        workspace: Path,
    ) -> tuple[str, int]:
        total_tokens = 0
        augmented_prompt = f"Working directory: {workspace}\n\n{prompt}"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": augmented_prompt},
        ]

        output = ""
        for _ in range(max_iterations):
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=4096,
                tools=_AGENT_TOOLS_OPENAI,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )
            if response.usage:
                total_tokens += (response.usage.prompt_tokens or 0) + (
                    response.usage.completion_tokens or 0
                )

            choice = response.choices[0]
            output = choice.message.content or ""

            if choice.finish_reason != "tool_calls":
                return output, total_tokens

            messages.append(choice.message)  # type: ignore[arg-type]

            for tc in choice.message.tool_calls or []:
                fn = getattr(tc, "function", None)
                if fn is None:
                    continue
                try:
                    args = json.loads(fn.arguments)
                except json.JSONDecodeError:
                    args = {}
                result = _execute_tool(fn.name, args, workspace)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

        return output, total_tokens


class AnthropicLLMClient:
    def __init__(self, api_key: str, model: str, *, base_url: str | None = None) -> None:
        from anthropic import AsyncAnthropic

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)
        self._model = model

    async def generate(self, prompt: str) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "".join(parts)


class OpenAILLMClient:
    def __init__(self, api_key: str, model: str, *, base_url: str | None = None) -> None:
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model

    async def generate(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
