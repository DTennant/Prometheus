from __future__ import annotations

import json
import logging
from typing import Any, Protocol
from uuid import uuid4

from prometheus.config.harness_config import HarnessConfig
from prometheus.config.schema_validator import validate_harness_config
from prometheus.eval.scorer import EvalReport
from prometheus.eval.task import TaskResult
from prometheus.evolution.history import EvolutionHistory

log = logging.getLogger(__name__)

MAX_MUTATION_RETRIES = 3


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> str: ...


def _build_mutation_prompt(
    config: HarnessConfig,
    report: EvalReport,
    history: EvolutionHistory,
) -> str:
    failed_cases = [r for r in report.results if not r.passed]
    failed_summary = ""
    for r in failed_cases[:10]:
        failed_summary += f"\n- Task {r.instance_id}: error={r.error or 'incorrect output'}, tokens={r.tokens_used}"

    return f"""You are an AI harness optimizer. Your job is to modify an agent harness configuration to improve its performance on coding tasks.

## Current Harness Config
```json
{config.model_dump_json(indent=2)}
```

## Evaluation Results
- Accuracy: {report.accuracy:.1%}
- Total tokens used: {report.total_tokens}
- Tasks passed: {sum(1 for r in report.results if r.passed)}/{len(report.results)}

## Failed Tasks{failed_summary}

## Evolution History
{history.summary_for_mutation()}

## Your Task
Modify the harness config to improve performance. You can change:
- system_prompt: The instructions given to the agent
- tool_descriptions: How tools are described (name + description pairs)
- workflow_prompts: pre_task and post_task prompts for reflection
- parameters: max_iterations (1-200), temperature (0.0-2.0), timeout_per_task (30-3600), retry_on_error, scratchpad_enabled
- custom_tools: Composite tools built from base tools (read_file, write_file, execute, list_directory)
- few_shot_examples: Example task/solution pairs (max 20)

Output ONLY a valid JSON object matching the HarnessConfig schema. No markdown, no explanation, just JSON."""


async def mutate_config(
    client: LLMClient,
    config: HarnessConfig,
    report: EvalReport,
    history: EvolutionHistory,
) -> HarnessConfig:
    prompt = _build_mutation_prompt(config, report, history)

    for attempt in range(MAX_MUTATION_RETRIES):
        try:
            raw_response = await client.generate(prompt)
            # Strip markdown fences if present
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            parsed = json.loads(cleaned)
            # Override metadata fields
            parsed["generation"] = config.generation + 1
            parsed["parent_id"] = config.config_id
            parsed["config_id"] = uuid4().hex[:8]

            new_config = HarnessConfig.model_validate(parsed)
            errors = validate_harness_config(new_config)
            if errors:
                log.warning("Mutation validation failed (attempt %d): %s", attempt + 1, errors)
                continue
            return new_config
        except (json.JSONDecodeError, Exception) as exc:
            log.warning("Mutation parse failed (attempt %d): %s", attempt + 1, exc)
            continue

    raise RuntimeError(f"Failed to produce valid mutation after {MAX_MUTATION_RETRIES} attempts")


class DryRunLLMClient:
    """Returns slightly modified configs for testing without real API calls."""

    async def generate(self, prompt: str) -> str:
        import re

        match = re.search(r"```json\n(.*?)```", prompt, re.DOTALL)
        if match:
            try:
                config_data = json.loads(match.group(1))
                config_data["system_prompt"] = (
                    config_data.get("system_prompt", "") + "\nBe more careful and systematic."
                )
                config_data["parameters"]["max_iterations"] = min(
                    config_data.get("parameters", {}).get("max_iterations", 30) + 5, 200
                )
                return json.dumps(config_data)
            except (json.JSONDecodeError, KeyError):
                pass
        return json.dumps(
            {
                "system_prompt": "You are a coding assistant. Be systematic and thorough.",
                "parameters": {"max_iterations": 35},
            }
        )
