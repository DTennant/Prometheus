from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from prometheus.code_evolution.builder import DockerBuilder, DryRunDockerBuilder
from prometheus.code_evolution.history import CodeEvolutionHistory
from prometheus.code_evolution.mutator import mutate_package
from prometheus.code_evolution.package import AgentPackage
from prometheus.code_evolution.runner import (
    DockerRunner,
    DryRunDockerRunner,
    evaluate_package,
)
from prometheus.code_evolution.selector import CodeBeamSelector
from prometheus.eval.task import Task

if TYPE_CHECKING:
    from prometheus.config.experiment_config import ExperimentConfig
    from prometheus.evolution.mutator import LLMClient
    from prometheus.logging.experiment_logger import ExperimentLogger

log = logging.getLogger(__name__)


class CodeEvolutionLoop:
    def __init__(
        self,
        config: ExperimentConfig,
        llm_client: LLMClient,
        builder: DockerBuilder | DryRunDockerBuilder,
        runner: DockerRunner | DryRunDockerRunner,
        tasks: list[Task],
        logger: ExperimentLogger,
    ) -> None:
        self._config = config
        self._llm_client = llm_client
        self._builder = builder
        self._runner = runner
        self._tasks = tasks
        self._logger = logger
        self._selector = CodeBeamSelector(config.beam_size)
        self._history = CodeEvolutionHistory()

    @property
    def history(self) -> CodeEvolutionHistory:
        return self._history

    async def run(self, seed: AgentPackage) -> AgentPackage:
        beam = [seed]
        best_pkg = seed

        for gen in range(self._config.generations):
            log.info(
                "Generation %d: evaluating %d candidates",
                gen,
                len(beam),
            )

            reports = [
                evaluate_package(
                    pkg,
                    self._tasks,
                    self._builder,
                    self._runner,
                    self._logger,
                    self._config.token_budget,
                )
                for pkg in beam
            ]

            self._history.add_generation(gen, beam, reports, self._config.token_budget)

            best_score = 0.0
            for pkg, report in zip(beam, reports):
                composite = report.compute_composite(self._config.token_budget)
                if composite >= best_score:
                    best_score = composite
                    best_pkg = pkg

            self._logger.log_generation(
                generation=gen,
                config_ids=[p.package_id for p in beam],
                best_score=best_score,
                metrics={"beam_size": len(beam)},
            )

            self._save_checkpoint(best_pkg, gen)

            log.info(
                "Generation %d: best_score=%.4f (%s)",
                gen,
                best_score,
                best_pkg.package_id,
            )

            if gen == self._config.generations - 1:
                break

            candidates: list[AgentPackage] = []
            for pkg, report in zip(beam, reports):
                for _ in range(self._config.mutations_per_parent):
                    try:
                        mutant = await mutate_package(
                            self._llm_client,
                            pkg,
                            report,
                            self._history,
                        )
                        candidates.append(mutant)
                    except RuntimeError:
                        log.warning(
                            "Mutation failed for %s",
                            pkg.package_id,
                        )

            if not candidates:
                log.warning("No mutations succeeded, keeping beam")
                continue

            candidate_reports = [
                evaluate_package(
                    c,
                    self._tasks,
                    self._builder,
                    self._runner,
                    self._logger,
                    self._config.token_budget,
                )
                for c in candidates
            ]

            all_pairs = list(zip(beam + candidates, reports + candidate_reports))
            beam = self._selector.select(all_pairs)

            if not beam:
                log.warning("Empty beam, resetting to seed")
                beam = [seed]

        best_dir = self._logger.run_dir / "best_agent"
        best_pkg.to_directory(best_dir)

        return best_pkg

    def _save_checkpoint(self, package: AgentPackage, generation: int) -> None:
        checkpoint = json.loads(package.to_json())
        self._logger.save_checkpoint(checkpoint, generation)
