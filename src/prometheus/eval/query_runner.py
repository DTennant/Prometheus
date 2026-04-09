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
    _SOLUTIONS: dict[str, str] = {
        "merge_intervals": (
            "def merge_intervals(intervals):\n"
            "    if not intervals: return []\n"
            "    intervals.sort()\n"
            "    merged = [intervals[0]]\n"
            "    for s, e in intervals[1:]:\n"
            "        if s <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], e)\n"
            "        else: merged.append([s, e])\n"
            "    return merged\n"
        ),
        "top_k_frequent": (
            "from collections import Counter\n"
            "def top_k_frequent(nums, k):\n"
            "    return [x for x, _ in Counter(nums).most_common(k)]\n"
        ),
        "LRUCache": (
            "from collections import OrderedDict\n"
            "class LRUCache:\n"
            "    def __init__(self, capacity):\n"
            "        self.cap = capacity\n"
            "        self.cache = OrderedDict()\n"
            "    def get(self, key):\n"
            "        if key not in self.cache: return -1\n"
            "        self.cache.move_to_end(key)\n"
            "        return self.cache[key]\n"
            "    def put(self, key, value):\n"
            "        if key in self.cache: self.cache.move_to_end(key)\n"
            "        self.cache[key] = value\n"
            "        if len(self.cache) > self.cap:\n"
            "            self.cache.popitem(last=False)\n"
        ),
        "Trie": (
            "class Trie:\n"
            "    def __init__(self): self.root = {}\n"
            "    def insert(self, word):\n"
            "        node = self.root\n"
            "        for c in word: node = node.setdefault(c, {})\n"
            "        node['$'] = True\n"
            "    def search(self, word):\n"
            "        node = self.root\n"
            "        for c in word:\n"
            "            if c not in node: return False\n"
            "            node = node[c]\n"
            "        return '$' in node\n"
            "    def starts_with(self, prefix):\n"
            "        node = self.root\n"
            "        for c in prefix:\n"
            "            if c not in node: return False\n"
            "            node = node[c]\n"
            "        return True\n"
        ),
    }

    def __init__(self, default_output: str = "# solution placeholder\nresult = 42") -> None:
        self._default_output = default_output

    async def run_task(
        self, prompt: str, system_prompt: str, max_iterations: int, workspace: Path
    ) -> tuple[str, int]:
        await asyncio.sleep(0.01)
        prompt_quality = len(system_prompt)
        task_hash = hash(prompt) % 100

        for keyword, solution in self._SOLUTIONS.items():
            if keyword.lower() in prompt.lower():
                if prompt_quality > 120 or task_hash < 30:
                    return solution, 100 + prompt_quality
                break

        return self._default_output, 150
