from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from prometheus.eval.benchmarks.base import BenchmarkAdapter
from prometheus.eval.task import Task, TaskInstance, TaskResult

log = logging.getLogger(__name__)


class SWEBenchAdapter(BenchmarkAdapter):
    name = "swebench"
    description = (
        "SWE-bench Verified — 500 real GitHub issue resolution tasks from popular Python repos"
    )
    requires_docker = True
    pip_package = "datasets"

    def __init__(
        self, split: str = "test", dataset_name: str = "princeton-nlp/SWE-bench_Verified"
    ) -> None:
        self._split = split
        self._dataset_name = dataset_name

    def is_available(self) -> bool:
        try:
            import datasets

            return True
        except ImportError:
            return False

    def get_tasks(self, limit: int | None = None) -> list[Task]:
        self.check_or_raise()
        from datasets import load_dataset

        ds = load_dataset(self._dataset_name, split=self._split)
        tasks: list[Task] = []

        for item in ds:
            tasks.append(_SWEBenchTask(dict(item)))
            if limit and len(tasks) >= limit:
                break

        return tasks


class _SWEBenchTask(Task):
    category = "swebench"

    def __init__(self, item: dict[str, Any]) -> None:
        self.name = item.get("instance_id", "unknown")
        self._item = item

    def get_instances(self) -> list[TaskInstance]:
        problem_statement = self._item.get("problem_statement", "")
        repo = self._item.get("repo", "")
        base_commit = self._item.get("base_commit", "")
        hints = self._item.get("hints_text", "")

        prompt = (
            f"Fix the following GitHub issue in the {repo} repository.\n\n"
            f"## Issue\n{problem_statement}\n\n"
        )
        if hints:
            prompt += f"## Hints\n{hints}\n\n"
        prompt += (
            f"The repository is checked out at commit {base_commit}.\n"
            f"Make the minimal changes needed to resolve the issue.\n"
            f"Output a unified diff (patch) that can be applied with `git apply`."
        )

        return [
            TaskInstance(
                instance_id=self.name,
                prompt=prompt,
                expected_output=self._item.get("test_patch", ""),
                metadata={
                    "repo": repo,
                    "base_commit": base_commit,
                    "test_patch": self._item.get("test_patch", ""),
                    "patch": self._item.get("patch", ""),
                    "fail_to_pass": self._item.get("FAIL_TO_PASS", ""),
                    "pass_to_pass": self._item.get("PASS_TO_PASS", ""),
                },
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        patch_path = workspace / "agent_patch.diff"
        patch_path.write_text(agent_output, encoding="utf-8")

        repo = instance.metadata.get("repo", "")
        base_commit = instance.metadata.get("base_commit", "")
        fail_to_pass = instance.metadata.get("fail_to_pass", "")

        if not repo or not base_commit:
            return TaskResult(
                instance.instance_id,
                False,
                0.0,
                0,
                0.0,
                agent_output,
                "Missing repo/commit metadata",
            )

        test_script = f"""#!/bin/bash
set -e

if [ ! -d repo ]; then
    git clone https://github.com/{repo}.git repo 2>/dev/null
fi
cd repo
git checkout {base_commit} 2>/dev/null

if git apply ../agent_patch.diff 2>/dev/null; then
    echo "PATCH_APPLIED"
else
    echo "PATCH_FAILED"
    exit 1
fi

{self._build_test_command(fail_to_pass)}
"""
        test_path = workspace / "run_test.sh"
        test_path.write_text(test_script, encoding="utf-8")

        try:
            result = subprocess.run(
                ["bash", str(test_path)],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=300,
            )
            passed = result.returncode == 0 and "PATCH_APPLIED" in result.stdout
            error = result.stderr.strip()[:500] if not passed else None
        except subprocess.TimeoutExpired:
            passed = False
            error = "Evaluation timed out (5 min)"
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

    def _build_test_command(self, fail_to_pass: str) -> str:
        if not fail_to_pass:
            return 'echo "NO_TESTS_SPECIFIED"'

        try:
            tests = json.loads(fail_to_pass)
            if isinstance(tests, list) and tests:
                test_args = " ".join(tests)
                return f"python -m pytest {test_args} -x --timeout=60 2>&1"
        except (json.JSONDecodeError, TypeError):
            pass

        return f"python -m pytest -x --timeout=60 2>&1"
