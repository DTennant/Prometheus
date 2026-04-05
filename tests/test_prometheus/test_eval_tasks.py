import pytest
from pathlib import Path
from prometheus.eval.tasks.code_generation import get_code_generation_tasks, IntervalMergeTask
from prometheus.eval.tasks.file_manipulation import get_file_manipulation_tasks, RenameRefactorTask
from prometheus.eval.tasks.debugging import get_debugging_tasks, SilentDataCorruptionTask
from prometheus.eval.tasks.reasoning import get_reasoning_tasks, BuildDependencyOrderTask
from prometheus.eval.tasks import get_all_tasks, get_task_suite
from prometheus.eval.sandbox import TaskSandbox


class TestCodeGenerationTasks:
    def test_all_tasks_have_instances(self):
        for task in get_code_generation_tasks():
            instances = task.get_instances()
            assert len(instances) > 0, f"{task.name} has no instances"

    def test_interval_merge_correct(self, tmp_path: Path):
        task = IntervalMergeTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            correct_code = (
                "def merge_intervals(intervals):\n"
                "    if not intervals: return []\n"
                "    intervals.sort()\n"
                "    merged = [intervals[0]]\n"
                "    for start, end in intervals[1:]:\n"
                "        if start <= merged[-1][1]:\n"
                "            merged[-1][1] = max(merged[-1][1], end)\n"
                "        else:\n"
                "            merged.append([start, end])\n"
                "    return merged\n"
            )
            result = task.score(inst, tmp_path, correct_code)
            assert result.passed

    def test_interval_merge_wrong(self, tmp_path: Path):
        task = IntervalMergeTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            result = task.score(inst, tmp_path, "def merge_intervals(x): return x")
            assert not result.passed


class TestFileManipulationTasks:
    def test_all_tasks_have_instances(self):
        for task in get_file_manipulation_tasks():
            assert len(task.get_instances()) > 0

    def test_rename_refactor_correct(self, tmp_path: Path):
        task = RenameRefactorTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            ws = sb.setup(inst)
            (ws / "models.py").write_text(
                "class PersonRecord:\n"
                "    def __init__(self, name, age):\n"
                "        self.name = name\n"
                "        self.age = age\n"
            )
            (ws / "utils.py").write_text(
                "def compute_annual_value(record):\n    return record.age * 12\n"
            )
            result = task.score(inst, ws, "refactored")
            assert result.passed


class TestDebuggingTasks:
    def test_all_tasks_have_instances(self):
        for task in get_debugging_tasks():
            assert len(task.get_instances()) > 0

    def test_silent_corruption_buggy_fails(self, tmp_path: Path):
        task = SilentDataCorruptionTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            sb.setup(inst)
            result = task.score(inst, tmp_path, "no fix")
            assert not result.passed

    def test_silent_corruption_fixed(self, tmp_path: Path):
        task = SilentDataCorruptionTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            ws = sb.setup(inst)
            fixed = """import json, copy

def update_config(config, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and key in config:
            update_config(config[key], value)
        else:
            config[key] = value
    return config

def load_and_merge(base_path, override_path, output_path):
    with open(base_path) as f:
        base = json.load(f)
    with open(override_path) as f:
        overrides = json.load(f)

    defaults = copy.deepcopy(base)
    merged = update_config(defaults, overrides)

    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2)

    return base, merged
"""
            (ws / "config_merger.py").write_text(fixed)
            result = task.score(inst, ws, "fixed")
            assert result.passed


class TestReasoningTasks:
    def test_all_tasks_have_instances(self):
        for task in get_reasoning_tasks():
            assert len(task.get_instances()) > 0

    def test_build_order_correct(self, tmp_path: Path):
        task = BuildDependencyOrderTask()
        inst = task.get_instances()[0]
        with TaskSandbox(workspace=tmp_path) as sb:
            ws = sb.setup(inst)
            solution = """import json

def compute_build_order(deps):
    visited = set()
    order = []
    visiting = set()
    def dfs(node):
        if node in visiting:
            raise ValueError("Cycle detected")
        if node in visited:
            return
        visiting.add(node)
        for dep in deps.get(node, []):
            dfs(dep)
        visiting.remove(node)
        visited.add(node)
        order.append(node)
    for node in deps:
        dfs(node)
    return order
"""
            (ws / "build_order.py").write_text(solution)
            result = task.score(inst, ws, "solved")
            assert result.passed


class TestTaskSuite:
    def test_all_tasks(self):
        tasks = get_all_tasks()
        assert len(tasks) == 13

    def test_suite_by_name(self):
        assert len(get_task_suite("code_generation")) == 5
        assert len(get_task_suite("debugging")) == 3
        assert len(get_task_suite("file_manipulation")) == 3
        assert len(get_task_suite("reasoning")) == 2

    def test_invalid_suite(self):
        with pytest.raises(ValueError):
            get_task_suite("nonexistent")
