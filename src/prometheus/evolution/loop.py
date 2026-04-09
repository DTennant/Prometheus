from __future__ import annotations

import logging

from prometheus.config.harness_config import HarnessConfig
from prometheus.config.experiment_config import ExperimentConfig
from prometheus.eval.runner import EvalRunner
from prometheus.eval.scorer import EvalReport
from prometheus.evolution.history import EvolutionHistory
from prometheus.evolution.mutator import LLMClient, mutate_config
from prometheus.evolution.selector import BeamSelector
from prometheus.logging.experiment_logger import ExperimentLogger

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

            self._history.add_generation(gen, beam, reports, self._config.token_budget)
            paired = list(zip(beam, reports))
            paired.sort(key=lambda p: p[1].scores.get("composite", p[1].accuracy), reverse=True)
            best_config, best_report = paired[0]
            best_score = best_report.scores.get("composite", best_report.accuracy)

            self._logger.log_generation(
                gen,
                [c.config_id for c in beam],
                best_score,
                {"beam_size": len(beam)},
            )
            self._logger.save_checkpoint(best_config.model_dump(), gen)

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

            candidate_reports: list[EvalReport] = []
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

            all_configs = beam + candidates
            all_reports = reports + candidate_reports
            all_pairs = list(zip(all_configs, all_reports))
            beam = self._selector.select(all_pairs)

            config_to_report = {c.config_id: r for c, r in zip(all_configs, all_reports)}
            reports = [
                config_to_report[c.config_id] for c in beam if c.config_id in config_to_report
            ]

            if not beam:
                log.error("Beam empty after selection, restoring seed")
                beam = [seed_config]
                reports = []

        if not reports:
            return beam[0]
        final_pairs = list(zip(beam, reports[: len(beam)]))
        final_pairs.sort(key=lambda p: p[1].scores.get("composite", p[1].accuracy), reverse=True)
        return final_pairs[0][0]
