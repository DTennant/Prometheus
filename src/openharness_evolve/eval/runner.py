from __future__ import annotations

import logging
from typing import Any

from openharness_evolve.config.harness_config import HarnessConfig
from openharness_evolve.eval.query_runner import AgentClient, QueryResult, run_eval_query
from openharness_evolve.eval.sandbox import TaskSandbox
from openharness_evolve.eval.scorer import EvalReport
from openharness_evolve.eval.task import Task, TaskResult
from openharness_evolve.logging.experiment_logger import ExperimentLogger

log = logging.getLogger(__name__)


class EvalRunner:
    def __init__(
        self,
        tasks: list[Task],
        client: AgentClient,
        logger: ExperimentLogger | None = None,
    ) -> None:
        self._tasks = tasks
        self._client = client
        self._logger = logger

    async def evaluate(self, config: HarnessConfig) -> EvalReport:
        all_results: list[TaskResult] = []

        for task in self._tasks:
            for instance in task.get_instances():
                with TaskSandbox() as sandbox:
                    workspace = sandbox.setup(instance)

                    full_prompt = ""
                    if config.workflow_prompts.pre_task:
                        full_prompt += config.workflow_prompts.pre_task + "\n\n"
                    full_prompt += instance.prompt
                    if config.workflow_prompts.post_task:
                        full_prompt += "\n\n" + config.workflow_prompts.post_task

                    query_result = await run_eval_query(
                        client=self._client,
                        prompt=full_prompt,
                        system_prompt=config.system_prompt,
                        max_iterations=config.parameters.max_iterations,
                        timeout=config.parameters.timeout_per_task,
                    )

                    if query_result.error:
                        result = TaskResult(
                            instance_id=instance.instance_id,
                            passed=False,
                            score=0.0,
                            tokens_used=query_result.tokens_used,
                            wall_time_seconds=query_result.wall_time_seconds,
                            raw_output=query_result.output,
                            error=query_result.error,
                        )
                    else:
                        result = task.score(instance, workspace, query_result.output)
                        result = TaskResult(
                            instance_id=result.instance_id,
                            passed=result.passed,
                            score=result.score,
                            tokens_used=query_result.tokens_used,
                            wall_time_seconds=query_result.wall_time_seconds,
                            raw_output=query_result.output,
                            error=result.error,
                        )

                    all_results.append(result)

                    if self._logger:
                        self._logger.log_eval_result(
                            task_id=instance.instance_id,
                            config_id=config.config_id,
                            passed=result.passed,
                            score=result.score,
                            tokens_used=result.tokens_used,
                            wall_time=result.wall_time_seconds,
                            error=result.error,
                        )
                        if not result.passed and self._logger:
                            self._logger.log_failure_case(
                                task_id=instance.instance_id,
                                config_id=config.config_id,
                                error_details=result.error or "incorrect output",
                                agent_output=result.raw_output,
                            )

        scores: dict[str, float] = {}
        if all_results:
            accuracy = sum(1 for r in all_results if r.passed) / len(all_results)
            total_tokens = sum(r.tokens_used for r in all_results)
            scores = {"accuracy": accuracy, "total_tokens": float(total_tokens)}

        return EvalReport(
            results=all_results,
            scores=scores,
            config_id=config.config_id,
            generation=config.generation,
        )
