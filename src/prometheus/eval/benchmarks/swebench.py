from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from prometheus.eval.benchmarks.base import BenchmarkAdapter
from prometheus.eval.task import Task, TaskInstance, TaskResult

log = logging.getLogger(__name__)


def _docker_image_tag(instance_id: str) -> str:
    """Convert instance_id to SWE-bench Docker image tag.

    SWE-bench uses: swebench/sweb.eval.x86_64.{id}:latest
    Instance IDs like 'astropy__astropy-12907' become
    'astropy_1776_astropy-12907'.
    """
    docker_id = instance_id.replace("__", "_1776_")
    return f"swebench/sweb.eval.x86_64.{docker_id}:latest".lower()


class SWEBenchAdapter(BenchmarkAdapter):
    name = "swebench"
    description = (
        "SWE-bench Verified — 500 real GitHub issue resolution tasks from popular Python repos"
    )
    requires_docker = True
    pip_package = "datasets"

    def __init__(
        self,
        split: str = "test",
        dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    ) -> None:
        self._split = split
        self._dataset_name = dataset_name

    def is_available(self) -> bool:
        try:
            import datasets  # type: ignore[import-untyped]  # noqa: F401

            return shutil.which("docker") is not None
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
            f"Fix the following GitHub issue in the {repo}"
            f" repository.\n\n"
            f"## Issue\n{problem_statement}\n\n"
        )
        if hints:
            prompt += f"## Hints\n{hints}\n\n"
        prompt += (
            f"The repository is checked out at commit"
            f" {base_commit}.\n"
            f"Make the minimal changes needed to resolve the"
            f" issue.\n"
            f"Output a unified diff (patch) that can be applied"
            f" with `git apply`."
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

    def score(
        self,
        instance: TaskInstance,
        workspace: Path,
        agent_output: str,
    ) -> TaskResult:
        patch_path = workspace / "agent_patch.diff"
        patch_path.write_text(agent_output, encoding="utf-8")

        test_patch = instance.metadata.get("test_patch", "")
        if test_patch:
            test_patch_path = workspace / "test_patch.diff"
            test_patch_path.write_text(test_patch, encoding="utf-8")

        fail_to_pass = instance.metadata.get("fail_to_pass", "")
        image_tag = _docker_image_tag(instance.instance_id)
        test_cmd = _build_test_command(fail_to_pass)

        apply_agent = "git apply --verbose /workspace/agent_patch.diff"
        apply_test = ""
        if test_patch:
            apply_test = " && git apply --verbose /workspace/test_patch.diff"
        docker_script = f"cd /testbed && {apply_agent}{apply_test} && {test_cmd}"

        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{workspace}:/workspace",
            image_tag,
            "bash",
            "-c",
            docker_script,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            passed = result.returncode == 0
            error = result.stderr.strip()[:500] if not passed else None
        except subprocess.TimeoutExpired:
            passed = False
            error = "timeout"
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


def _build_test_command(fail_to_pass: str) -> str:
    if not fail_to_pass:
        return 'echo "NO_TESTS_SPECIFIED"'

    try:
        tests = json.loads(fail_to_pass)
        if isinstance(tests, list) and tests:
            test_args = " ".join(tests)
            return f"python -m pytest {test_args} -x --tb=short"
    except (json.JSONDecodeError, TypeError):
        pass

    return "python -m pytest -x --tb=short"
