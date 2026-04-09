from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prometheus.code_evolution.package import AgentPackage
    from prometheus.eval.scorer import EvalReport


@dataclass
class CodeGenerationRecord:
    generation: int
    package_ids: list[str]
    scores: list[float]
    best_score: float
    best_package_id: str


class CodeEvolutionHistory:
    def __init__(self) -> None:
        self._generations: list[CodeGenerationRecord] = []

    def add_generation(
        self,
        gen: int,
        packages: list[AgentPackage],
        reports: list[EvalReport],
        budget_limit: int = 50_000,
    ) -> None:
        scores = [r.compute_composite(budget_limit) for r in reports]
        best_idx = scores.index(max(scores)) if scores else 0
        record = CodeGenerationRecord(
            generation=gen,
            package_ids=[p.package_id for p in packages],
            scores=scores,
            best_score=scores[best_idx] if scores else 0.0,
            best_package_id=(packages[best_idx].package_id if packages else ""),
        )
        self._generations.append(record)

    def get_generation(self, gen: int) -> CodeGenerationRecord | None:
        for record in self._generations:
            if record.generation == gen:
                return record
        return None

    def get_best(self, n: int = 1) -> list[tuple[str, float]]:
        all_entries: list[tuple[str, float]] = []
        for record in self._generations:
            all_entries.append((record.best_package_id, record.best_score))
        all_entries.sort(key=lambda x: x[1], reverse=True)
        return all_entries[:n]

    def summary_for_mutation(self) -> str:
        if not self._generations:
            return "No prior generations."
        lines: list[str] = []
        recent = self._generations[-5:]
        for record in recent:
            lines.append(
                f"Gen {record.generation}: "
                f"best={record.best_score:.4f}, "
                f"candidates={len(record.package_ids)}"
            )
        return "\n".join(lines)

    def to_json(self) -> str:
        data: list[dict[str, Any]] = []
        for record in self._generations:
            data.append(
                {
                    "generation": record.generation,
                    "package_ids": record.package_ids,
                    "scores": record.scores,
                    "best_score": record.best_score,
                    "best_package_id": record.best_package_id,
                }
            )
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, data: str) -> CodeEvolutionHistory:
        parsed = json.loads(data)
        history = cls()
        for item in parsed:
            record = CodeGenerationRecord(
                generation=item["generation"],
                package_ids=item["package_ids"],
                scores=item["scores"],
                best_score=item["best_score"],
                best_package_id=item["best_package_id"],
            )
            history._generations.append(record)
        return history
