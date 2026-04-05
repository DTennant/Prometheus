from __future__ import annotations

import json
import pytest
from pathlib import Path

from openharness_evolve.config.harness_config import HarnessConfig
from openharness_evolve.config.experiment_config import ExperimentConfig
from openharness_evolve.eval.query_runner import DryRunAgentClient
from openharness_evolve.eval.runner import EvalRunner
from openharness_evolve.eval.task import Task, TaskInstance, TaskResult
from openharness_evolve.evolution.loop import EvolutionLoop
from openharness_evolve.evolution.mutator import DryRunLLMClient
from openharness_evolve.logging.experiment_logger import ExperimentLogger


class SimpleTask(Task):
    name = "simple"
    category = "test"

    def get_instances(self) -> list[TaskInstance]:
        return [TaskInstance("s1", "do it", "done")]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return TaskResult("s1", True, 1.0, 0, 0.0, agent_output)


class TestEvolutionLoop:
    @pytest.mark.asyncio
    async def test_completes_n_generations(self, tmp_path: Path):
        config = ExperimentConfig(
            generations=2,
            beam_size=2,
            mutations_per_parent=1,
            output_dir=tmp_path,
        )
        logger = ExperimentLogger(tmp_path / "run", config=config.model_dump())
        eval_runner = EvalRunner([SimpleTask()], DryRunAgentClient())
        llm_client = DryRunLLMClient()

        loop = EvolutionLoop(config, eval_runner, llm_client, logger)
        seed = HarnessConfig(system_prompt="seed prompt", config_id="seed")
        best = await loop.run(seed)

        assert best is not None
        assert loop.history.num_generations == 2

    @pytest.mark.asyncio
    async def test_checkpoint_written(self, tmp_path: Path):
        config = ExperimentConfig(generations=1, beam_size=1, mutations_per_parent=1)
        logger = ExperimentLogger(tmp_path / "run")
        eval_runner = EvalRunner([SimpleTask()], DryRunAgentClient())

        loop = EvolutionLoop(config, eval_runner, DryRunLLMClient(), logger)
        seed = HarnessConfig(system_prompt="test", config_id="seed")
        await loop.run(seed)

        checkpoint = tmp_path / "run" / "checkpoint_gen0000.json"
        assert checkpoint.exists()
        data = json.loads(checkpoint.read_text())
        assert "system_prompt" in data

    @pytest.mark.asyncio
    async def test_events_logged(self, tmp_path: Path):
        config = ExperimentConfig(generations=2, beam_size=1, mutations_per_parent=1)
        logger = ExperimentLogger(tmp_path / "run")
        eval_runner = EvalRunner([SimpleTask()], DryRunAgentClient())

        loop = EvolutionLoop(config, eval_runner, DryRunLLMClient(), logger)
        seed = HarnessConfig(system_prompt="test", config_id="seed")
        await loop.run(seed)

        events = logger.load_events()
        gen_events = [e for e in events if e["type"] == "generation"]
        assert len(gen_events) == 2

    @pytest.mark.asyncio
    async def test_history_populated(self, tmp_path: Path):
        config = ExperimentConfig(generations=3, beam_size=1, mutations_per_parent=1)
        logger = ExperimentLogger(tmp_path / "run")
        eval_runner = EvalRunner([SimpleTask()], DryRunAgentClient())

        loop = EvolutionLoop(config, eval_runner, DryRunLLMClient(), logger)
        seed = HarnessConfig(system_prompt="test")
        await loop.run(seed)

        assert loop.history.num_generations == 3
        best = loop.history.get_best(1)
        assert len(best) == 1
        assert best[0][1] >= 0.0
