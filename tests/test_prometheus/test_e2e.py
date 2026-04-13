from __future__ import annotations

import json
import pytest
from pathlib import Path

from prometheus.config.experiment_config import ExperimentConfig
from prometheus.config.harness_config import HarnessConfig
from prometheus.eval.query_runner import DryRunAgentClient
from prometheus.eval.runner import EvalRunner
from prometheus.eval.task import Task, TaskInstance, TaskResult
from prometheus.evolution.loop import EvolutionLoop
from prometheus.evolution.mutator import DryRunLLMClient
from prometheus.evolution.seed import create_seed_harness
from prometheus.logging.experiment_logger import ExperimentLogger


class StubPassTask(Task):
    name = "stub_pass"
    category = "test"

    def get_instances(self) -> list[TaskInstance]:
        return [
            TaskInstance("sp1", "task 1", "expected"),
            TaskInstance("sp2", "task 2", "expected"),
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return TaskResult(instance.instance_id, True, 1.0, 0, 0.0, agent_output)


class StubMixedTask(Task):
    name = "stub_mixed"
    category = "test"

    def get_instances(self) -> list[TaskInstance]:
        return [
            TaskInstance("sm1", "pass this", "ok"),
            TaskInstance("sm2", "fail this", "nope"),
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        passed = instance.instance_id == "sm1"
        return TaskResult(
            instance.instance_id, passed, 1.0 if passed else 0.0, 0, 0.0, agent_output
        )


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_evolution_loop(self, tmp_path: Path):
        experiment_config = ExperimentConfig(
            generations=3,
            beam_size=2,
            mutations_per_parent=2,
            output_dir=tmp_path,
            token_budget=10000,
        )

        run_dir = tmp_path / experiment_config.run_id
        logger = ExperimentLogger(run_dir, config=experiment_config.model_dump())

        tasks = [StubPassTask(), StubMixedTask()]
        eval_runner = EvalRunner(tasks, DryRunAgentClient(), logger)
        llm_client = DryRunLLMClient()

        seed = create_seed_harness()
        loop = EvolutionLoop(experiment_config, eval_runner, llm_client, logger)
        best = await loop.run(seed)

        assert best is not None
        assert isinstance(best, HarnessConfig)
        assert loop.history.num_generations == 3

        assert (run_dir / "config.json").exists()
        config_data = json.loads((run_dir / "config.json").read_text())
        assert "generations" in config_data

        events = logger.load_events()
        gen_events = [e for e in events if e["type"] == "generation"]
        assert len(gen_events) == 3

        assert (run_dir / "checkpoint_gen0000.json").exists()
        assert (run_dir / "checkpoint_gen0001.json").exists()
        assert (run_dir / "checkpoint_gen0002.json").exists()

        history = loop.history
        best_entries = history.get_best(1)
        assert len(best_entries) == 1
        assert best_entries[0][1] >= 0.0

    @pytest.mark.asyncio
    async def test_single_generation(self, tmp_path: Path):
        experiment_config = ExperimentConfig(
            generations=1,
            beam_size=1,
            mutations_per_parent=1,
        )

        logger = ExperimentLogger(tmp_path / "run")
        eval_runner = EvalRunner([StubPassTask()], DryRunAgentClient(), logger)

        seed = create_seed_harness()
        loop = EvolutionLoop(experiment_config, eval_runner, DryRunLLMClient(), logger)
        best = await loop.run(seed)

        assert best is not None
        assert loop.history.num_generations == 1

    @pytest.mark.asyncio
    async def test_seed_harness_validates(self):
        from prometheus.config.schema_validator import validate_harness_config
        from prometheus.evolution.seed import (
            create_human_baseline_harness,
            create_seed_harness,
        )

        seed = create_seed_harness()
        assert validate_harness_config(seed) == []

        baseline = create_human_baseline_harness()
        assert validate_harness_config(baseline) == []
