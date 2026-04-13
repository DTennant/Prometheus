from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

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
            from terminal_bench.dataset.dataset import Dataset  # type: ignore[import-not-found]  # noqa: F401

            return shutil.which("docker") is not None
        except ImportError:
            return False

    def get_tasks(self, limit: int | None = None) -> list[Task]:
        self.check_or_raise()
        import yaml  # type: ignore[import-untyped]
        from terminal_bench.dataset.dataset import Dataset

        ds = Dataset(
            name=self._dataset_name,
            version=self._dataset_version,
        )
        task_paths = list(ds.tasks)
        tasks: list[Task] = []

        for task_path in task_paths:
            task_yaml = task_path / "task.yaml"
            if not task_yaml.exists():
                continue

            try:
                raw = task_yaml.read_text(encoding="utf-8")
                task_data = yaml.safe_load(raw)
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

    def score(
        self,
        instance: TaskInstance,
        workspace: Path,
        agent_output: str,
    ) -> TaskResult:
        dockerfile = workspace / "Dockerfile"
        if not dockerfile.exists():
            return TaskResult(
                instance_id=instance.instance_id,
                passed=False,
                score=0.0,
                tokens_used=0,
                wall_time_seconds=0.0,
                raw_output=agent_output,
                error="No Dockerfile in workspace",
            )

        image_tag = f"tb-eval-{instance.instance_id}".lower()
        error: str | None = None
        passed = False

        try:
            subprocess.run(
                ["docker", "build", "-t", image_tag, "."],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )

            compose = workspace / "docker-compose.yaml"
            if compose.exists():
                subprocess.run(
                    ["docker", "compose", "up", "-d"],
                    cwd=str(workspace),
                    capture_output=True,
                    timeout=60,
                    check=True,
                )

            run_tests = workspace / "run-tests.sh"
            if run_tests.exists():
                result = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-v",
                        f"{workspace}:/workspace",
                        image_tag,
                        "bash",
                        "/workspace/run-tests.sh",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                passed = result.returncode == 0
                if not passed:
                    out = result.stderr or result.stdout
                    error = out.strip()[:500]
            else:
                error = "No run-tests.sh in workspace"
        except subprocess.TimeoutExpired:
            error = "Docker execution timed out"
        except subprocess.CalledProcessError as exc:
            error = f"Docker build/compose failed: {exc}"
        except Exception as exc:
            error = str(exc)
        finally:
            subprocess.run(
                ["docker", "compose", "down", "--remove-orphans"],
                cwd=str(workspace),
                capture_output=True,
                timeout=30,
            ) if (workspace / "docker-compose.yaml").exists() else None
            subprocess.run(
                ["docker", "rmi", "-f", image_tag],
                capture_output=True,
                timeout=30,
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
