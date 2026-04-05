from __future__ import annotations

import subprocess
from pathlib import Path

from prometheus.eval.task import Task, TaskInstance, TaskResult


class FibonacciTask(Task):
    name = "fibonacci"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import fibonacci
assert fibonacci(0) == 0
assert fibonacci(1) == 1
assert fibonacci(5) == 5
assert fibonacci(10) == 55
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_fibonacci",
                prompt="Write a Python function called `fibonacci(n)` that returns the nth Fibonacci number. F(0)=0, F(1)=1.",
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


class IsPalindromeTask(Task):
    name = "is_palindrome"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import is_palindrome
assert is_palindrome("racecar") == True
assert is_palindrome("hello") == False
assert is_palindrome("") == True
assert is_palindrome("a") == True
assert is_palindrome("abba") == True
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_palindrome",
                prompt="Write a Python function called `is_palindrome(s)` that returns True if the string s is a palindrome, False otherwise.",
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


class FlattenListTask(Task):
    name = "flatten_list"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import flatten_list
assert flatten_list([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]
assert flatten_list([]) == []
assert flatten_list([1, 2, 3]) == [1, 2, 3]
assert flatten_list([[[[1]]]]) == [1]
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_flatten",
                prompt="Write a Python function called `flatten_list(nested)` that takes a nested list and returns a flat list of all elements.",
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


class MergeSortedTask(Task):
    name = "merge_sorted"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import merge_sorted
assert merge_sorted([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]
assert merge_sorted([], [1, 2]) == [1, 2]
assert merge_sorted([1], []) == [1]
assert merge_sorted([], []) == []
assert merge_sorted([1, 1], [1, 1]) == [1, 1, 1, 1]
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_merge_sorted",
                prompt="Write a Python function called `merge_sorted(a, b)` that merges two sorted lists into one sorted list.",
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


class CountWordsTask(Task):
    name = "count_words"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import count_words
result = count_words("the cat sat on the mat")
assert result["the"] == 2
assert result["cat"] == 1
assert result["sat"] == 1
assert count_words("") == {}
assert count_words("hello") == {"hello": 1}
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_count_words",
                prompt="Write a Python function called `count_words(text)` that returns a dictionary mapping each word to its count in the text.",
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


def _run_code_test(instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
    solution_path = workspace / "solution.py"
    test_path = workspace / "test_solution.py"

    # Extract code from agent output (handle markdown fences)
    code = agent_output.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        code = "\n".join(lines)

    solution_path.write_text(code, encoding="utf-8")
    test_path.write_text(instance.expected_output, encoding="utf-8")

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


def get_code_generation_tasks() -> list[Task]:
    return [
        FibonacciTask(),
        IsPalindromeTask(),
        FlattenListTask(),
        MergeSortedTask(),
        CountWordsTask(),
    ]
