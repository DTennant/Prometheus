from __future__ import annotations

import pytest
from openharness_evolve.config.harness_config import HarnessConfig
from openharness_evolve.eval.task import TaskInstance, TaskResult


@pytest.fixture
def seed_config() -> HarnessConfig:
    from openharness_evolve.evolution.seed import create_seed_harness

    return create_seed_harness()


@pytest.fixture
def sample_task_instance() -> TaskInstance:
    return TaskInstance(
        instance_id="test_001",
        prompt="Write a function that adds two numbers",
        expected_output="def add(a, b): return a + b",
        setup_files={"main.py": "# placeholder"},
    )


@pytest.fixture
def sample_passing_result() -> TaskResult:
    return TaskResult(
        instance_id="test_001",
        passed=True,
        score=1.0,
        tokens_used=150,
        wall_time_seconds=2.5,
        raw_output="def add(a, b): return a + b",
    )


@pytest.fixture
def sample_failing_result() -> TaskResult:
    return TaskResult(
        instance_id="test_002",
        passed=False,
        score=0.0,
        tokens_used=300,
        wall_time_seconds=5.0,
        raw_output="invalid output",
        error="Test assertion failed",
    )
