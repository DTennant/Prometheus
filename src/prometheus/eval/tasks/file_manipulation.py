from __future__ import annotations

import subprocess
from pathlib import Path

from prometheus.eval.task import Task, TaskInstance, TaskResult


class RenameRefactorTask(Task):
    name = "rename_refactor"
    category = "file_manipulation"

    def get_instances(self) -> list[TaskInstance]:
        main_py = """from utils import calculate_total
from models import UserRecord

def process_users(users):
    for user in users:
        record = UserRecord(user["name"], user["age"])
        total = calculate_total(record)
        print(f"{record.name}: {total}")
"""
        utils_py = """def calculate_total(record):
    return record.age * 12

def format_total(total):
    return f"${calculate_total(total):.2f}"
"""
        models_py = """class UserRecord:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def __repr__(self):
        return f"UserRecord({self.name}, {self.age})"
"""
        test_py = """from utils import compute_annual_value
from models import PersonRecord

record = PersonRecord("Alice", 30)
assert compute_annual_value(record) == 360
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="filemanip_rename_refactor",
                prompt=(
                    "Refactor this Python project:\n"
                    "1. Rename `UserRecord` to `PersonRecord` in ALL files\n"
                    "2. Rename `calculate_total` to `compute_annual_value` in ALL files\n"
                    "3. Make sure all imports and references are updated consistently\n"
                    "4. The test in test_check.py must pass after your changes."
                ),
                expected_output=test_py,
                setup_files={
                    "main.py": main_py,
                    "utils.py": utils_py,
                    "models.py": models_py,
                    "test_check.py": test_py,
                },
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_file_test(instance, workspace, agent_output, "test_check.py")


class CSVPipelineTask(Task):
    name = "csv_pipeline"
    category = "file_manipulation"

    def get_instances(self) -> list[TaskInstance]:
        input_csv = "name,department,salary\nAlice,Engineering,95000\nBob,Marketing,72000\nCharlie,Engineering,105000\nDiana,Marketing,68000\nEve,Engineering,110000\nFrank,HR,62000\nGrace,HR,58000\n"
        test_py = """import json

with open("report.json") as f:
    report = json.load(f)

assert report["Engineering"]["count"] == 3
assert report["Engineering"]["average_salary"] == 103333
assert report["Engineering"]["top_earner"] == "Eve"
assert report["Marketing"]["count"] == 2
assert report["Marketing"]["average_salary"] == 70000
assert report["Marketing"]["top_earner"] == "Bob"
assert report["HR"]["count"] == 2
assert report["HR"]["average_salary"] == 60000
assert report["HR"]["top_earner"] == "Frank"
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="filemanip_csv_pipeline",
                prompt=(
                    "Read 'data.csv' and produce 'report.json' with the following structure:\n"
                    "A JSON object where each key is a department name, and the value is an object with:\n"
                    "- 'count': number of employees\n"
                    "- 'average_salary': integer average (floor division)\n"
                    "- 'top_earner': name of the highest-paid employee in that department\n"
                    "Write a Python script 'pipeline.py' that does this transformation."
                ),
                expected_output=test_py,
                setup_files={"data.csv": input_csv, "test_check.py": test_py},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        pipeline = workspace / "pipeline.py"
        if pipeline.exists():
            try:
                subprocess.run(
                    ["python", str(pipeline)],
                    cwd=str(workspace),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception:
                pass
        return _run_file_test(instance, workspace, agent_output, "test_check.py")


class AddTestCoverageTask(Task):
    name = "add_test_coverage"
    category = "file_manipulation"

    def get_instances(self) -> list[TaskInstance]:
        calculator_py = """class Calculator:
    def __init__(self):
        self.history = []

    def add(self, a, b):
        result = a + b
        self.history.append(("add", a, b, result))
        return result

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append(("divide", a, b, result))
        return result

    def power(self, base, exp):
        if exp < 0:
            raise ValueError("Negative exponents not supported")
        result = base ** exp
        self.history.append(("power", base, exp, result))
        return result

    def last_n(self, n):
        return self.history[-n:]

    def clear(self):
        self.history.clear()
"""
        test_py = """import subprocess, sys
result = subprocess.run(
    [sys.executable, "-m", "pytest", "test_calculator.py", "-v", "--tb=short"],
    capture_output=True, text=True, timeout=30,
)
lines = result.stdout + result.stderr
assert "PASSED" in lines or "passed" in lines
assert "FAILED" not in lines and "ERROR" not in lines
test_count = lines.count("PASSED")
assert test_count >= 8, f"Only {test_count} tests passed, need at least 8"
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="filemanip_add_tests",
                prompt=(
                    "Read 'calculator.py' and write a comprehensive test file 'test_calculator.py' "
                    "using pytest. Cover:\n"
                    "- Normal add, divide, power operations\n"
                    "- Edge cases: divide by zero raises ValueError, negative exponent raises ValueError\n"
                    "- History tracking: last_n returns correct entries, clear empties history\n"
                    "- At least 8 test functions\n"
                    "The tests must all pass when run with pytest."
                ),
                expected_output=test_py,
                setup_files={"calculator.py": calculator_py, "test_check.py": test_py},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_file_test(instance, workspace, agent_output, "test_check.py")


def _run_file_test(
    instance: TaskInstance, workspace: Path, agent_output: str, test_file: str
) -> TaskResult:
    test_path = workspace / test_file
    if not test_path.exists():
        return TaskResult(
            instance.instance_id,
            False,
            0.0,
            0,
            0.0,
            agent_output,
            f"{test_file} missing from workspace",
        )
    try:
        result = subprocess.run(
            ["python", str(test_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
        )
        passed = result.returncode == 0 and "PASS" in result.stdout
        error = result.stderr.strip() if not passed else None
        if not passed and not error:
            error = f"stdout: {result.stdout.strip()[:500]}"
    except subprocess.TimeoutExpired:
        passed = False
        error = "Test execution timed out"
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


def get_file_manipulation_tasks() -> list[Task]:
    return [RenameRefactorTask(), CSVPipelineTask(), AddTestCoverageTask()]
