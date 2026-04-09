from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus.config.harness_config import HarnessConfig
    from prometheus.eval.scorer import EvalReport


class BeamSelector:
    def __init__(self, beam_size: int) -> None:
        self._beam_size = beam_size

    def select(self, candidates: list[tuple[HarnessConfig, EvalReport]]) -> list[HarnessConfig]:
        if not candidates:
            return []
        # Sort by composite score descending (use accuracy as proxy if scores dict empty)
        sorted_candidates = sorted(
            candidates,
            key=lambda pair: pair[1].scores.get("composite", pair[1].accuracy),
            reverse=True,
        )
        # Deduplication: skip configs with identical meaningful dimensions
        seen: set[tuple[object, ...]] = set()
        result: list[HarnessConfig] = []
        for config, report in sorted_candidates:
            key = (
                config.system_prompt,
                config.parameters.max_iterations,
                config.parameters.temperature,
                config.parameters.timeout_per_task,
                config.parameters.retry_on_error,
                tuple((td.name, td.description) for td in config.tool_descriptions),
                tuple(
                    (p.name, p.enabled, p.prompt_template, p.max_iterations, p.pass_output_as)
                    for p in config.workflow.phases
                ),
                config.workflow.scratchpad_enabled,
                tuple(
                    (ct.name, ct.description, tuple(ct.sub_tools), ct.strategy)
                    for ct in config.custom_tools
                ),
                tuple((fs.task, fs.solution) for fs in config.few_shot_examples),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(config)
            if len(result) >= self._beam_size:
                break
        return result
