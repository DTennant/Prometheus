from __future__ import annotations

import subprocess
from pathlib import Path

from openharness_evolve.eval.task import Task, TaskInstance, TaskResult


class OffByOneTask(Task):
    name = "off_by_one"
    category = "debugging"

    def get_instances(self) -> list[TaskInstance]:
        buggy_code = '''def get_last_n(items, n):
    """Return the last n items from the list."""
    return items[len(items) - n - 1:]
'''
        test_code = """from buggy import get_last_n
assert get_last_n([1, 2, 3, 4, 5], 3) == [3, 4, 5]
assert get_last_n([1, 2, 3], 1) == [3]
assert get_last_n([1], 1) == [1]
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="debug_off_by_one",
                prompt="The file 'buggy.py' has a bug in the get_last_n function. Fix it so that test.py passes. Only modify buggy.py.",
                expected_output=test_code,
                setup_files={"buggy.py": buggy_code, "test.py": test_code},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_debug_test(instance, workspace, agent_output)


class ImportErrorTask(Task):
    name = "import_error"
    category = "debugging"

    def get_instances(self) -> list[TaskInstance]:
        module_a = """from module_b import helper_b

def func_a():
    return helper_b() + " from a"
"""
        module_b = """from module_a import func_a

def helper_b():
    return "hello"

def func_b():
    return func_a()
"""
        test_code = """from module_b import helper_b
assert helper_b() == "hello"
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="debug_import_error",
                prompt="The files module_a.py and module_b.py have a circular import. Fix it so that test.py passes. You may restructure the imports but must keep all functions working.",
                expected_output=test_code,
                setup_files={
                    "module_a.py": module_a,
                    "module_b.py": module_b,
                    "test.py": test_code,
                },
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_debug_test(instance, workspace, agent_output)


def _run_debug_test(instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
    test_path = workspace / "test.py"
    if not test_path.exists():
        return TaskResult(instance.instance_id, False, 0.0, 0, 0.0, agent_output, "test.py missing")
    try:
        result = subprocess.run(
            ["python", str(test_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=10,
        )
        passed = result.returncode == 0
        error = result.stderr.strip() if not passed else None
    except subprocess.TimeoutExpired:
        passed = False
        error = "Test timed out"
    except Exception as exc:
        passed = False
        error = str(exc)

    return TaskResult(
        instance_id=instance.instance_id,
        passed=passed,
        score=1.0 if passed else 0.0,
        tokens_used=0,
        wall_time_seconds=0.0,
        raw_output=agent_output,
        error=error,
    )


def get_debugging_tasks() -> list[Task]:
    return [OffByOneTask(), ImportErrorTask()]
