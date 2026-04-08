from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from prometheus.eval.benchmarks import list_benchmarks, get_benchmark
from prometheus.eval.benchmarks.base import BenchmarkAdapter
from prometheus.eval.benchmarks.humaneval_plus import HumanEvalPlusAdapter, _HumanEvalPlusTask
from prometheus.eval.benchmarks.terminal_bench import TerminalBenchAdapter, _TerminalBenchTask
from prometheus.eval.benchmarks.swebench import SWEBenchAdapter, _SWEBenchTask
from prometheus.eval.task import TaskInstance
from prometheus.eval.sandbox import TaskSandbox


class TestBenchmarkRegistry:
    def test_list_benchmarks_returns_all(self):
        benchmarks = list_benchmarks()
        names = [b["name"] for b in benchmarks]
        assert "humaneval_plus" in names
        assert "terminal_bench" in names
        assert "swebench" in names

    def test_list_benchmarks_has_required_fields(self):
        for bench in list_benchmarks():
            assert "name" in bench
            assert "description" in bench
            assert "available" in bench
            assert "requires_docker" in bench
            assert "install_hint" in bench

    def test_get_unknown_benchmark_raises(self):
        with pytest.raises(ValueError, match="Unknown benchmark"):
            get_benchmark("nonexistent_benchmark_xyz")


class TestHumanEvalPlusAdapter:
    def test_adapter_properties(self):
        adapter = HumanEvalPlusAdapter()
        assert adapter.name == "humaneval_plus"
        assert adapter.pip_package == "evalplus"
        assert not adapter.requires_docker

    def test_install_hint(self):
        adapter = HumanEvalPlusAdapter()
        assert "evalplus" in adapter.install_hint()

    def test_task_from_problem(self):
        problem = {
            "prompt": "def add(a, b):\n    ",
            "entry_point": "add",
            "test": "assert add(1, 2) == 3\nassert add(0, 0) == 0\n",
            "canonical_solution": "    return a + b\n",
        }
        task = _HumanEvalPlusTask("HumanEval/0", problem)
        assert task.name == "HumanEval/0"
        assert task.category == "humaneval_plus"

        instances = task.get_instances()
        assert len(instances) == 1
        assert "add" in instances[0].prompt
        assert instances[0].metadata["entry_point"] == "add"

    def test_task_score_correct(self, tmp_path: Path):
        problem = {
            "prompt": "def add(a, b):\n    ",
            "entry_point": "add",
            "test": "assert add(1, 2) == 3\nassert add(0, 0) == 0\n",
        }
        task = _HumanEvalPlusTask("HumanEval/0", problem)
        inst = task.get_instances()[0]

        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            result = task.score(inst, tmp_path, "def add(a, b):\n    return a + b")
            assert result.passed

    def test_task_score_wrong(self, tmp_path: Path):
        problem = {
            "prompt": "def add(a, b):\n    ",
            "entry_point": "add",
            "test": "assert add(1, 2) == 3\n",
        }
        task = _HumanEvalPlusTask("HumanEval/0", problem)
        inst = task.get_instances()[0]

        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            result = task.score(inst, tmp_path, "def add(a, b):\n    return a - b")
            assert not result.passed


class TestTerminalBenchAdapter:
    def test_adapter_properties(self):
        adapter = TerminalBenchAdapter()
        assert adapter.name == "terminal_bench"
        assert adapter.requires_docker
        assert adapter.pip_package == "terminal-bench"

    def test_task_from_dict(self, tmp_path: Path):
        task_data = {
            "instruction": "Compile the C program and fix any errors.",
        }
        task = _TerminalBenchTask("compile_c", task_data, tmp_path)
        instances = task.get_instances()
        assert len(instances) == 1
        assert "Compile" in instances[0].prompt

    def test_task_loads_setup_files_from_dir(self, tmp_path: Path):
        (tmp_path / "Dockerfile").write_text("FROM ubuntu")
        (tmp_path / "run-tests.sh").write_text("echo PASS")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_it.py").write_text("assert True")

        task_data = {"instruction": "Do the thing."}
        task = _TerminalBenchTask("test_task", task_data, tmp_path)
        inst = task.get_instances()[0]
        assert "Dockerfile" in inst.setup_files
        assert "run-tests.sh" in inst.setup_files
        assert "tests/test_it.py" in inst.setup_files


class TestSWEBenchAdapter:
    def test_adapter_properties(self):
        adapter = SWEBenchAdapter()
        assert adapter.name == "swebench"
        assert adapter.requires_docker
        assert adapter.pip_package == "datasets"

    def test_task_from_item(self):
        item = {
            "instance_id": "django__django-12345",
            "repo": "django/django",
            "base_commit": "abc123",
            "problem_statement": "Fix the ORM query bug",
            "hints_text": "Check the queryset filter",
            "test_patch": "diff --git a/test.py ...",
            "patch": "diff --git a/fix.py ...",
            "FAIL_TO_PASS": '["tests/test_orm.py::TestFilter"]',
            "PASS_TO_PASS": '["tests/test_basic.py"]',
        }
        task = _SWEBenchTask(item)
        assert task.name == "django__django-12345"

        instances = task.get_instances()
        assert len(instances) == 1
        assert "django/django" in instances[0].prompt
        assert "ORM query bug" in instances[0].prompt
        assert instances[0].metadata["repo"] == "django/django"

    def test_task_instance_fresh_each_call(self):
        item = {
            "instance_id": "test-1",
            "repo": "test/repo",
            "base_commit": "abc",
            "problem_statement": "fix it",
        }
        task = _SWEBenchTask(item)
        i1 = task.get_instances()
        i2 = task.get_instances()
        assert i1[0] is not i2[0]


class TestTaskSuiteIntegration:
    def test_builtin_suites_still_work(self):
        from prometheus.eval.tasks import get_task_suite

        assert len(get_task_suite("default")) == 13
        assert len(get_task_suite("code_generation")) == 5
        assert len(get_task_suite("reasoning")) == 2

    def test_limit_parameter(self):
        from prometheus.eval.tasks import get_task_suite

        tasks = get_task_suite("default", limit=3)
        assert len(tasks) == 3

    def test_unknown_suite_raises(self):
        from prometheus.eval.tasks import get_task_suite

        with pytest.raises(ValueError, match="Unknown task suite"):
            get_task_suite("totally_fake_suite_12345")
