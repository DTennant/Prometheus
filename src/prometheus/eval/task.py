from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskInstance:
    instance_id: str
    prompt: str
    expected_output: Any
    setup_files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    instance_id: str
    passed: bool
    score: float  # [0.0, 1.0]
    tokens_used: int
    wall_time_seconds: float
    raw_output: str
    error: str | None = None


class Task(ABC):
    name: str
    category: str

    @abstractmethod
    def get_instances(self) -> list[TaskInstance]: ...

    @abstractmethod
    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult: ...

    def aggregate(self, results: list[TaskResult]) -> dict[str, float]:
        if not results:
            return {"accuracy": 0.0, "total_tokens": 0, "avg_tokens": 0, "avg_time": 0}
        passed = sum(1 for r in results if r.passed)
        total_tokens = sum(r.tokens_used for r in results)
        return {
            "accuracy": passed / len(results),
            "total_tokens": float(total_tokens),
            "avg_tokens": total_tokens / len(results),
            "avg_time": sum(r.wall_time_seconds for r in results) / len(results),
        }
