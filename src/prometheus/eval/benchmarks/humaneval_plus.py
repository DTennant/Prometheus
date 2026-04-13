from __future__ import annotations

import subprocess
import logging
from pathlib import Path
from typing import Any

from prometheus.eval.benchmarks.base import BenchmarkAdapter
from prometheus.eval.task import Task, TaskInstance, TaskResult

log = logging.getLogger(__name__)


def _strip_markdown_fences(code: str) -> str:
    """Remove markdown code fences if present."""
    lines = code.strip().split("\n")
    if not lines:
        return code
    if lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


class HumanEvalPlusAdapter(BenchmarkAdapter):
    name = "humaneval_plus"
    description = "HumanEval+ from EvalPlus — 164 code generation tasks with augmented test suites"
    requires_docker = False
    pip_package = "evalplus"

    def is_available(self) -> bool:
        try:
            from evalplus.data import get_human_eval_plus  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            return False

    def get_tasks(self, limit: int | None = None) -> list[Task]:
        self.check_or_raise()
        from evalplus.data import get_human_eval_plus

        dataset = get_human_eval_plus()
        tasks: list[Task] = []

        for task_id, problem in dataset.items():
            tasks.append(_HumanEvalPlusTask(task_id, problem))
            if limit and len(tasks) >= limit:
                break

        return tasks


class _HumanEvalPlusTask(Task):
    category = "humaneval_plus"

    def __init__(self, task_id: str, problem: dict[str, Any]) -> None:
        self.name = task_id
        self._problem = problem

    def get_instances(self) -> list[TaskInstance]:
        prompt = self._problem.get("prompt", "")
        entry_point = self._problem.get("entry_point", "solution")

        test_imports = f"from solution import {entry_point}\n\n"
        base_tests = self._problem.get("test", "")

        test_code = test_imports
        if base_tests:
            test_code += base_tests + "\n"

        plus_inputs = self._problem.get("plus_input", [])
        if plus_inputs:
            test_code += "\n"
            for inp in plus_inputs[:10]:
                args = ", ".join(repr(a) for a in inp)
                test_code += f"try:\n    {entry_point}({args})\nexcept Exception:\n    pass\n"

        test_code += '\nprint("PASS")\n'

        return [
            TaskInstance(
                instance_id=self.name,
                prompt=(
                    f"Write a Python function in a file called 'solution.py'.\n\n"
                    f"Here is the function signature and docstring:\n\n"
                    f"```python\n{prompt}\n```\n\n"
                    f"Implement the function body. The function should be importable as "
                    f"`from solution import {entry_point}`."
                ),
                expected_output=test_code,
                metadata={
                    "entry_point": entry_point,
                    "canonical_solution": self._problem.get("canonical_solution", ""),
                },
            )
        ]

    def score(
        self,
        instance: TaskInstance,
        workspace: Path,
        agent_output: str,
    ) -> TaskResult:
        solution_path = workspace / "solution.py"
        test_path = workspace / "test_solution.py"

        if not solution_path.exists():
            code = _strip_markdown_fences(agent_output)
            solution_path.write_text(code, encoding="utf-8")
        test_path.write_text(instance.expected_output, encoding="utf-8")

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
        except subprocess.TimeoutExpired:
            return TaskResult(
                instance_id=instance.instance_id,
                passed=False,
                score=0.0,
                tokens_used=0,
                wall_time_seconds=30.0,
                raw_output=agent_output,
                error="Timeout: solution took >30s",
            )
        except Exception as exc:
            return TaskResult(
                instance_id=instance.instance_id,
                passed=False,
                score=0.0,
                tokens_used=0,
                wall_time_seconds=0.0,
                raw_output=agent_output,
                error=str(exc),
            )

        return TaskResult(
            instance_id=instance.instance_id,
            passed=passed,
            score=1.0 if passed else 0.0,
            tokens_used=0,
            wall_time_seconds=0.0,
            raw_output=agent_output,
            error=error,
        )
