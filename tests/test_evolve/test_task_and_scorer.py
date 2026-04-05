from __future__ import annotations
import pytest
from pathlib import Path
from openharness_evolve.eval.task import Task, TaskInstance, TaskResult
from openharness_evolve.eval.scorer import composite_score, EvalReport


class StubTask(Task):
    name = "stub"
    category = "test"

    def get_instances(self) -> list[TaskInstance]:
        return [TaskInstance(instance_id="t1", prompt="do something", expected_output="done")]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        passed = agent_output.strip() == instance.expected_output
        return TaskResult(
            instance_id=instance.instance_id,
            passed=passed,
            score=1.0 if passed else 0.0,
            tokens_used=100,
            wall_time_seconds=1.0,
            raw_output=agent_output,
        )


class TestTaskABC:
    def test_stub_task_instantiates(self):
        task = StubTask()
        assert task.name == "stub"

    def test_get_instances_non_empty(self):
        task = StubTask()
        instances = task.get_instances()
        assert len(instances) > 0

    def test_score_correct(self):
        task = StubTask()
        inst = task.get_instances()[0]
        result = task.score(inst, Path("/tmp"), "done")
        assert result.passed is True
        assert result.score == 1.0

    def test_score_incorrect(self):
        task = StubTask()
        inst = task.get_instances()[0]
        result = task.score(inst, Path("/tmp"), "wrong")
        assert result.passed is False
        assert result.score == 0.0

    def test_aggregate_empty(self):
        task = StubTask()
        agg = task.aggregate([])
        assert agg["accuracy"] == 0.0

    def test_aggregate_mixed(self):
        task = StubTask()
        results = [
            TaskResult("t1", True, 1.0, 100, 1.0, "done"),
            TaskResult("t2", False, 0.0, 200, 2.0, "wrong"),
        ]
        agg = task.aggregate(results)
        assert agg["accuracy"] == 0.5
        assert agg["total_tokens"] == 300.0
        assert agg["avg_tokens"] == 150.0


class TestCompositeScore:
    def test_under_budget(self):
        assert composite_score(1.0, 1000, 2000) == 1.0

    def test_over_budget(self):
        assert composite_score(1.0, 4000, 2000) == 0.5

    def test_half_accuracy(self):
        assert composite_score(0.5, 1000, 2000) == 0.5

    def test_zero_tokens(self):
        assert composite_score(1.0, 0, 2000) == 0.0

    def test_exact_budget(self):
        assert composite_score(1.0, 2000, 2000) == 1.0


class TestEvalReport:
    def test_accuracy(self):
        report = EvalReport(
            results=[
                TaskResult("t1", True, 1.0, 100, 1.0, "ok"),
                TaskResult("t2", False, 0.0, 200, 2.0, "fail"),
            ]
        )
        assert report.accuracy == 0.5

    def test_total_tokens(self):
        report = EvalReport(
            results=[
                TaskResult("t1", True, 1.0, 100, 1.0, "ok"),
                TaskResult("t2", True, 1.0, 200, 2.0, "ok"),
            ]
        )
        assert report.total_tokens == 300

    def test_composite(self):
        report = EvalReport(
            results=[
                TaskResult("t1", True, 1.0, 500, 1.0, "ok"),
            ]
        )
        assert report.compute_composite(1000) == 1.0
