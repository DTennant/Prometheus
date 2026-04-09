from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus.config.harness_config import HarnessConfig
    from prometheus.eval.scorer import EvalReport


@dataclass
class GenerationRecord:
    generation: int
    configs: list[dict[str, Any]]
    scores: list[float]
    best_score: float
    best_config_id: str


class EvolutionHistory:
    def __init__(self) -> None:
        self._generations: list[GenerationRecord] = []

    def add_generation(
        self,
        gen: int,
        configs: list[HarnessConfig],
        reports: list[EvalReport],
        budget_limit: int = 50_000,
    ) -> None:
        config_dicts = [c.model_dump() for c in configs]
        scores = [r.compute_composite(budget_limit) for r in reports]
        best_idx = max(range(len(scores)), key=lambda i: scores[i]) if scores else 0
        self._generations.append(
            GenerationRecord(
                generation=gen,
                configs=config_dicts,
                scores=scores,
                best_score=max(scores) if scores else 0.0,
                best_config_id=configs[best_idx].config_id if configs else "",
            )
        )

    def get_best(self, n: int = 1) -> list[tuple[dict[str, Any], float]]:
        all_entries: list[tuple[dict[str, Any], float]] = []
        for gen_rec in self._generations:
            for config_dict, score in zip(gen_rec.configs, gen_rec.scores):
                all_entries.append((config_dict, score))
        all_entries.sort(key=lambda x: x[1], reverse=True)
        return all_entries[:n]

    def get_generation(self, gen: int) -> GenerationRecord | None:
        for rec in self._generations:
            if rec.generation == gen:
                return rec
        return None

    @property
    def num_generations(self) -> int:
        return len(self._generations)

    def summary_for_mutation(self) -> str:
        if not self._generations:
            return "No evolution history yet."
        lines = ["Evolution History:"]
        for rec in self._generations[-5:]:
            lines.append(
                f"  Gen {rec.generation}: best_score={rec.best_score:.3f}, "
                f"num_candidates={len(rec.configs)}"
            )
        best = self.get_best(1)
        if best:
            lines.append(f"Overall best score: {best[0][1]:.3f}")
        return "\n".join(lines)

    def to_json(self) -> str:
        records = []
        for rec in self._generations:
            records.append(
                {
                    "generation": rec.generation,
                    "configs": rec.configs,
                    "scores": rec.scores,
                    "best_score": rec.best_score,
                    "best_config_id": rec.best_config_id,
                }
            )
        return json.dumps(records, indent=2)

    @classmethod
    def from_json(cls, data: str) -> EvolutionHistory:
        history = cls()
        records = json.loads(data)
        for rec_data in records:
            history._generations.append(
                GenerationRecord(
                    generation=rec_data["generation"],
                    configs=rec_data["configs"],
                    scores=rec_data["scores"],
                    best_score=rec_data["best_score"],
                    best_config_id=rec_data["best_config_id"],
                )
            )
        return history
