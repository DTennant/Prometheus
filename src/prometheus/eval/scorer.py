from __future__ import annotations
from dataclasses import dataclass, field
from prometheus.eval.task import TaskResult


def composite_score(accuracy: float, tokens_used: int, budget_limit: int) -> float:
    if tokens_used <= 0:
        return 0.0
    efficiency = min(budget_limit / tokens_used, 1.0)
    return accuracy * efficiency


@dataclass
class EvalReport:
    results: list[TaskResult] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    config_id: str = ""
    generation: int = 0

    @property
    def accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    @property
    def total_tokens(self) -> int:
        return sum(r.tokens_used for r in self.results)

    def compute_composite(self, budget_limit: int) -> float:
        return composite_score(self.accuracy, self.total_tokens, budget_limit)
