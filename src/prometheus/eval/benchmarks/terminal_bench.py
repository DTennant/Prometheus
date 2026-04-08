from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from prometheus.eval.benchmarks.base import BenchmarkAdapter
from prometheus.eval.task import Task, TaskInstance, TaskResult

log = logging.getLogger(__name__)


class TerminalBenchAdapter(BenchmarkAdapter):
    name = "terminal_bench"
    description = "TerminalBench — 80 real terminal tasks (compiling, servers, data processing) with Docker sandboxing"
    requires_docker = True
    pip_package = "terminal-bench"

    def __init__(
        self,
        dataset_name: str = "terminal-bench-core",
        dataset_version: str = "0.1.1",
    ) -> None:
        self._dataset_name = dataset_name
        self._dataset_version = dataset_version

    def is_available(self) -> bool:
        try:
            from terminal_bench.dataset.dataset import Dataset

            return True
        except ImportError:
            return False

    def get_tasks(self, limit: int | None = None) -> list[Task]:
        self.check_or_raise()
        from terminal_bench.dataset.dataset import Dataset

        ds = Dataset(name=self._dataset_name, version=self._dataset_version)
        task_paths = list(ds.tasks)
        tasks: list[Task] = []

        for task_path in task_paths:
            task_yaml = task_path / "task.yaml"
            if not task_yaml.exists():
                continue

            try:
                task_data = yaml.safe_load(task_yaml.read_text(encoding="utf-8"))
            except Exception:
                continue

            task_id = task_path.name
            tasks.append(_TerminalBenchTask(task_id, task_data, task_path))
            if limit and len(tasks) >= limit:
                break

        return tasks


class _TerminalBenchTask(Task):
    category = "terminal_bench"

    def __init__(self, task_id: str, task_data: dict[str, Any], task_dir: Path) -> None:
        self.name = task_id
        self._task_data = task_data
        self._task_dir = task_dir

    def get_instances(self) -> list[TaskInstance]:
        instruction = self._task_data.get("instruction", "")

        setup_files: dict[str, str] = {}
        dockerfile = self._task_dir / "Dockerfile"
        if dockerfile.exists():
            setup_files["Dockerfile"] = dockerfile.read_text(encoding="utf-8")

        compose = self._task_dir / "docker-compose.yaml"
        if compose.exists():
            setup_files["docker-compose.yaml"] = compose.read_text(encoding="utf-8")

        run_tests = self._task_dir / "run-tests.sh"
        if run_tests.exists():
            setup_files["run-tests.sh"] = run_tests.read_text(encoding="utf-8")

        tests_dir = self._task_dir / "tests"
        if tests_dir.exists():
            for test_file in tests_dir.rglob("*"):
                if test_file.is_file():
                    rel = test_file.relative_to(self._task_dir)
                    try:
                        setup_files[str(rel)] = test_file.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        pass

        return [
            TaskInstance(
                instance_id=self.name,
                prompt=instruction,
                expected_output=None,
                setup_files=setup_files,
                metadata={
                    "source": "terminal_bench",
                    "task_dir": str(self._task_dir),
                    "has_dockerfile": "Dockerfile" in setup_files,
                },
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        run_tests = workspace / "run-tests.sh"
        if run_tests.exists():
            try:
                result = subprocess.run(
                    ["bash", str(run_tests)],
                    cwd=str(workspace),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                passed = result.returncode == 0
                error = (
                    (result.stderr.strip() or result.stdout.strip())[:500] if not passed else None
                )
            except subprocess.TimeoutExpired:
                passed = False
                error = "Test timed out (120s)"
            except Exception as exc:
                passed = False
                error = str(exc)
        else:
            passed = False
            error = "No run-tests.sh in workspace"

        return TaskResult(
            instance_id=instance.instance_id,
            passed=passed,
            score=1.0 if passed else 0.0,
            tokens_used=0,
            wall_time_seconds=0.0,
            raw_output=agent_output,
            error=error,
        )
