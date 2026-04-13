from __future__ import annotations

import logging
from pathlib import Path

from prometheus.config.harness_config import HarnessConfig, WorkflowPhase
from prometheus.eval.query_runner import AgentClient, run_eval_query
from prometheus.eval.sandbox import TaskSandbox
from prometheus.eval.scorer import EvalReport
from prometheus.eval.task import Task, TaskInstance, TaskResult
from prometheus.logging.experiment_logger import ExperimentLogger

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

        system_prompt = self._build_system_prompt(config)

        for task in self._tasks:
            for instance in task.get_instances():
                with TaskSandbox() as sandbox:
                    workspace = sandbox.setup(instance)

                    task_prompt = self._build_task_prompt(config, instance)
                    output, total_tokens, wall_time, error = await self._run_workflow(
                        config,
                        task_prompt,
                        system_prompt,
                        workspace,
                    )

                    if error:
                        result = TaskResult(
                            instance_id=instance.instance_id,
                            passed=False,
                            score=0.0,
                            tokens_used=total_tokens,
                            wall_time_seconds=wall_time,
                            raw_output=output,
                            error=error,
                        )
                    else:
                        result = task.score(instance, workspace, output)
                        result = TaskResult(
                            instance_id=result.instance_id,
                            passed=result.passed,
                            score=result.score,
                            tokens_used=total_tokens,
                            wall_time_seconds=wall_time,
                            raw_output=output,
                            error=result.error,
                        )

                    all_results.append(result)
                    self._log_result(result, config.config_id)

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

    def _build_system_prompt(self, config: HarnessConfig) -> str:
        parts = [config.system_prompt]

        if config.custom_tools:
            tool_lines = []
            for ct in config.custom_tools:
                tool_lines.append(
                    f"- {ct.name}: {ct.description} "
                    f"(uses: {', '.join(ct.sub_tools)}, strategy: {ct.strategy})"
                )
            parts.append("\n## Composite Tools\n" + "\n".join(tool_lines))

        if config.tool_descriptions:
            desc_lines = [f"- {td.name}: {td.description}" for td in config.tool_descriptions]
            parts.append("\n## Available Tools\n" + "\n".join(desc_lines))

        return "\n".join(parts)

    def _build_task_prompt(self, config: HarnessConfig, instance: TaskInstance) -> str:
        parts: list[str] = []

        if config.few_shot_examples:
            examples = config.few_shot_examples[:5]
            example_text = "\n\n".join(
                f"### Example {i + 1}\n**Task:** {ex.task}\n**Solution:** {ex.solution}"
                for i, ex in enumerate(examples)
            )
            parts.append(f"## Examples\n{example_text}")

        parts.append(instance.prompt)
        return "\n\n".join(parts)

    async def _run_workflow(
        self,
        config: HarnessConfig,
        task_prompt: str,
        system_prompt: str,
        workspace: Path,
    ) -> tuple[str, int, float, str | None]:
        phases = [p for p in config.workflow.phases if p.enabled]
        if not phases:
            phases = [
                WorkflowPhase(
                    name="execution",
                    prompt_template="$task",
                    max_iterations=config.parameters.max_iterations,
                )
            ]

        scratchpad = ""
        previous_output = ""
        total_tokens = 0
        total_time = 0.0
        last_error: str | None = None

        for phase in phases:
            prompt = phase.render(
                task=task_prompt,
                scratchpad=scratchpad,
                previous_output=previous_output,
            )

            query_result = await run_eval_query(
                client=self._client,
                prompt=prompt,
                system_prompt=system_prompt,
                max_iterations=phase.max_iterations,
                timeout=config.parameters.timeout_per_task,
                workspace=workspace,
            )

            total_tokens += query_result.tokens_used
            total_time += query_result.wall_time_seconds

            if query_result.error:
                last_error = f"Phase '{phase.name}': {query_result.error}"
                break

            previous_output = query_result.output

            if phase.pass_output_as == "scratchpad" and config.workflow.scratchpad_enabled:
                scratchpad += f"\n## {phase.name}\n{query_result.output}"

        return previous_output, total_tokens, total_time, last_error

    def _log_result(self, result: TaskResult, config_id: str) -> None:
        if not self._logger:
            return
        self._logger.log_eval_result(
            task_id=result.instance_id,
            config_id=config_id,
            passed=result.passed,
            score=result.score,
            tokens_used=result.tokens_used,
            wall_time=result.wall_time_seconds,
            error=result.error,
        )
        if not result.passed:
            self._logger.log_failure_case(
                task_id=result.instance_id,
                config_id=config_id,
                error_details=result.error or "incorrect output",
                agent_output=result.raw_output,
            )
