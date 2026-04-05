from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class AnthropicAgentClient:
    def __init__(self, api_key: str, model: str, *, base_url: str | None = None) -> None:
        from anthropic import AsyncAnthropic

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)
        self._model = model

    async def run_task(
        self, prompt: str, system_prompt: str, max_iterations: int, workspace: Path
    ) -> tuple[str, int]:
        total_tokens = 0
        augmented_prompt = f"Working directory: {workspace}\n\n{prompt}"
        messages: list[dict[str, str]] = [{"role": "user", "content": augmented_prompt}]

        for _ in range(max_iterations):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            )
            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)

            output = "".join(text_parts)

            if response.stop_reason != "tool_use":
                return output, total_tokens

            messages.append({"role": "assistant", "content": output})
            messages.append({"role": "user", "content": "Continue."})

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
        self, prompt: str, system_prompt: str, max_iterations: int, workspace: Path
    ) -> tuple[str, int]:
        total_tokens = 0
        augmented_prompt = f"Working directory: {workspace}\n\n{prompt}"
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": augmented_prompt},
        ]

        for _ in range(max_iterations):
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=4096,
                messages=messages,
            )
            if response.usage:
                total_tokens += (response.usage.prompt_tokens or 0) + (
                    response.usage.completion_tokens or 0
                )

            choice = response.choices[0]
            output = choice.message.content or ""

            if choice.finish_reason != "tool_calls":
                return output, total_tokens

            messages.append({"role": "assistant", "content": output})
            messages.append({"role": "user", "content": "Continue."})

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
