import pytest
import json
from prometheus.config.harness_config import HarnessConfig
from prometheus.eval.scorer import EvalReport
from prometheus.eval.task import TaskResult
from prometheus.evolution.history import EvolutionHistory
from prometheus.evolution.mutator import (
    mutate_config,
    DryRunLLMClient,
    _build_mutation_prompt,
)


def _make_report(passed_list: list[bool]) -> EvalReport:
    results = [
        TaskResult(f"t{i}", p, 1.0 if p else 0.0, 100, 1.0, "out", None if p else "error")
        for i, p in enumerate(passed_list)
    ]
    return EvalReport(results=results, config_id="test")


class FakeValidClient:
    async def generate(self, prompt: str) -> str:
        return json.dumps(
            {
                "system_prompt": "Improved prompt",
                "parameters": {"max_iterations": 40, "temperature": 0.8, "timeout_per_task": 600},
            }
        )


class FakeInvalidClient:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.calls < 3:
            return "not json at all"
        return json.dumps({"system_prompt": "valid after retries"})


class TestMutator:
    @pytest.mark.asyncio
    async def test_valid_mutation(self):
        config = HarnessConfig(system_prompt="original", config_id="parent1")
        report = _make_report([True, False])
        history = EvolutionHistory()

        result = await mutate_config(FakeValidClient(), config, report, history)
        assert result.system_prompt == "Improved prompt"
        assert result.generation == 1
        assert result.parent_id == "parent1"

    @pytest.mark.asyncio
    async def test_retries_on_invalid_json(self):
        config = HarnessConfig(system_prompt="test")
        report = _make_report([False])
        history = EvolutionHistory()

        result = await mutate_config(FakeInvalidClient(), config, report, history)
        assert result.system_prompt == "valid after retries"

    @pytest.mark.asyncio
    async def test_dry_run_client(self):
        config = HarnessConfig(system_prompt="original", config_id="p1")
        report = _make_report([True, False])
        history = EvolutionHistory()

        client = DryRunLLMClient()
        result = await mutate_config(client, config, report, history)
        assert result.generation == 1
        assert result.parent_id == "p1"

    def test_prompt_includes_failures(self):
        config = HarnessConfig(system_prompt="test")
        report = _make_report([True, False, False])
        history = EvolutionHistory()
        prompt = _build_mutation_prompt(config, report, history)
        assert "Failed Tasks" in prompt
        assert "t1" in prompt  # first failed task
        assert "66.7%" in prompt or "33.3%" in prompt  # accuracy shown
