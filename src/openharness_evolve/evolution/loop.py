from __future__ import annotations

import logging
from typing import Any

from openharness_evolve.config.harness_config import HarnessConfig
from openharness_evolve.config.experiment_config import ExperimentConfig
from openharness_evolve.eval.runner import EvalRunner
from openharness_evolve.eval.scorer import EvalReport
from openharness_evolve.evolution.history import EvolutionHistory
from openharness_evolve.evolution.mutator import LLMClient, mutate_config
from openharness_evolve.evolution.selector import BeamSelector
from openharness_evolve.logging.experiment_logger import ExperimentLogger

log = logging.getLogger(__name__)


class EvolutionLoop:
    def __init__(
        self,
        experiment_config: ExperimentConfig,
        eval_runner: EvalRunner,
        llm_client: LLMClient,
        logger: ExperimentLogger,
    ) -> None:
        self._config = experiment_config
        self._eval_runner = eval_runner
        self._llm_client = llm_client
        self._logger = logger
        self._selector = BeamSelector(beam_size=experiment_config.beam_size)
        self._history = EvolutionHistory()

    @property
    def history(self) -> EvolutionHistory:
        return self._history

    async def run(self, seed_config: HarnessConfig) -> HarnessConfig:
        beam = [seed_config]
        reports: list[EvalReport] = []

        for gen in range(self._config.generations):
            log.info("Generation %d: evaluating %d configs", gen, len(beam))

            reports = []
            for config in beam:
                report = await self._eval_runner.evaluate(config)
                report = EvalReport(
                    results=report.results,
                    scores={
                        **report.scores,
                        "composite": report.compute_composite(self._config.token_budget),
                    },
                    config_id=config.config_id,
                    generation=gen,
                )
                reports.append(report)

            self._history.add_generation(gen, beam, reports)
            best_score = max(r.scores.get("composite", r.accuracy) for r in reports)
            self._logger.log_generation(
                gen,
                [c.config_id for c in beam],
                best_score,
                {"beam_size": len(beam)},
            )
            self._logger.save_checkpoint(beam[0].model_dump(), gen)

            log.info("Generation %d: best_score=%.3f", gen, best_score)

            if gen == self._config.generations - 1:
                break

            candidates: list[HarnessConfig] = []
            for config, report in zip(beam, reports):
                for _ in range(self._config.mutations_per_parent):
                    try:
                        mutant = await mutate_config(
                            self._llm_client,
                            config,
                            report,
                            self._history,
                        )
                        candidates.append(mutant)
                    except RuntimeError:
                        log.warning("Mutation failed for config %s, skipping", config.config_id)

            if not candidates:
                log.warning("No valid mutations produced, keeping current beam")
                continue

            candidate_reports = []
            for candidate in candidates:
                report = await self._eval_runner.evaluate(candidate)
                report = EvalReport(
                    results=report.results,
                    scores={
                        **report.scores,
                        "composite": report.compute_composite(self._config.token_budget),
                    },
                    config_id=candidate.config_id,
                    generation=gen + 1,
                )
                candidate_reports.append(report)

            all_pairs = list(zip(beam + candidates, reports + candidate_reports))
            beam = self._selector.select(all_pairs)

            if not beam:
                log.error("Beam empty after selection, restoring seed")
                beam = [seed_config]

        if not reports:
            return beam[0]
        best_pairs = list(zip(beam, reports[: len(beam)]))
        best_pairs.sort(key=lambda p: p[1].scores.get("composite", p[1].accuracy), reverse=True)
        return best_pairs[0][0]
