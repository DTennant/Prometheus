import pytest
from pathlib import Path
from openharness_evolve.eval.tasks.code_generation import get_code_generation_tasks, FibonacciTask
from openharness_evolve.eval.tasks.file_manipulation import (
    get_file_manipulation_tasks,
    FindAndReplaceTask,
)
from openharness_evolve.eval.tasks.debugging import get_debugging_tasks, OffByOneTask
from openharness_evolve.eval.tasks import get_all_tasks, get_task_suite
from openharness_evolve.eval.sandbox import TaskSandbox


class TestCodeGenerationTasks:
    def test_all_tasks_have_instances(self):
        for task in get_code_generation_tasks():
            instances = task.get_instances()
            assert len(instances) > 0, f"{task.name} has no instances"

    def test_fibonacci_correct_solution(self, tmp_path: Path):
        task = FibonacciTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            correct_code = "def fibonacci(n):\n    if n <= 1: return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b"
            result = task.score(inst, tmp_path, correct_code)
            assert result.passed

    def test_fibonacci_wrong_solution(self, tmp_path: Path):
        task = FibonacciTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            result = task.score(inst, tmp_path, "def fibonacci(n): return -1")
            assert not result.passed

    def test_fibonacci_syntax_error(self, tmp_path: Path):
        task = FibonacciTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            result = task.score(inst, tmp_path, "def fibonacci(n) return oops")
            assert not result.passed
            assert result.error is not None


class TestFileManipulationTasks:
    def test_all_tasks_have_instances(self):
        for task in get_file_manipulation_tasks():
            assert len(task.get_instances()) > 0

    def test_find_replace_correct(self, tmp_path: Path):
        task = FindAndReplaceTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            ws = sb.setup(inst)
            # Simulate correct agent: replace foo with bar
            for f in ws.glob("*.txt"):
                content = f.read_text()
                f.write_text(content.replace("foo", "bar"))
            result = task.score(inst, ws, "replaced all")
            assert result.passed


class TestDebuggingTasks:
    def test_all_tasks_have_instances(self):
        for task in get_debugging_tasks():
            assert len(task.get_instances()) > 0

    def test_off_by_one_buggy_fails(self, tmp_path: Path):
        task = OffByOneTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            # Don't fix the bug — test should fail
            result = task.score(inst, tmp_path, "no fix applied")
            assert not result.passed

    def test_off_by_one_fixed(self, tmp_path: Path):
        task = OffByOneTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            ws = sb.setup(inst)
            # Fix the bug
            fixed = "def get_last_n(items, n):\n    return items[len(items) - n:]\n"
            (ws / "buggy.py").write_text(fixed)
            result = task.score(inst, ws, "fixed")
            assert result.passed


class TestTaskSuite:
    def test_all_tasks(self):
        tasks = get_all_tasks()
        assert len(tasks) == 10

    def test_suite_by_name(self):
        assert len(get_task_suite("code_generation")) == 5
        assert len(get_task_suite("debugging")) == 2

    def test_invalid_suite(self):
        with pytest.raises(ValueError):
            get_task_suite("nonexistent")
