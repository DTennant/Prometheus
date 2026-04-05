from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openharness_evolve.config.harness_config import HarnessConfig
    from openharness_evolve.eval.scorer import EvalReport


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
        # Deduplication: skip configs with identical system_prompt + parameters
        seen: set[tuple[str, int, float]] = set()
        result: list[HarnessConfig] = []
        for config, report in sorted_candidates:
            key = (
                config.system_prompt,
                config.parameters.max_iterations,
                config.parameters.temperature,
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(config)
            if len(result) >= self._beam_size:
                break
        return result
