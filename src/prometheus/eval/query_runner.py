from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class AgentClient(Protocol):
    async def run_task(
        self, prompt: str, system_prompt: str, max_iterations: int, workspace: Path
    ) -> tuple[str, int]: ...


@dataclass
class QueryResult:
    output: str
    tokens_used: int
    wall_time_seconds: float
    timed_out: bool = False
    error: str | None = None


async def run_eval_query(
    client: AgentClient,
    prompt: str,
    system_prompt: str,
    max_iterations: int = 30,
    timeout: int = 600,
    workspace: Path | None = None,
) -> QueryResult:
    start = time.monotonic()
    ws = workspace or Path(".")
    try:
        async with asyncio.timeout(timeout):
            output, tokens = await client.run_task(prompt, system_prompt, max_iterations, ws)
            elapsed = time.monotonic() - start
            return QueryResult(output=output, tokens_used=tokens, wall_time_seconds=elapsed)
    except TimeoutError:
        elapsed = time.monotonic() - start
        return QueryResult(
            output="",
            tokens_used=0,
            wall_time_seconds=elapsed,
            timed_out=True,
            error=f"Task timed out after {timeout}s",
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return QueryResult(
            output="",
            tokens_used=0,
            wall_time_seconds=elapsed,
            error=str(exc),
        )


class DryRunAgentClient:
    def __init__(self, default_output: str = "# solution placeholder\nresult = 42") -> None:
        self._default_output = default_output

    async def run_task(
        self, prompt: str, system_prompt: str, max_iterations: int, workspace: Path
    ) -> tuple[str, int]:
        await asyncio.sleep(0.01)
        return self._default_output, 150
