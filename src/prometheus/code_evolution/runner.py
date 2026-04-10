from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from prometheus.code_evolution.builder import DockerBuilder, DryRunDockerBuilder
from prometheus.code_evolution.package import AgentPackage
from prometheus.eval.scorer import EvalReport
from prometheus.eval.task import Task, TaskInstance, TaskResult

log = logging.getLogger(__name__)


class DockerRunner:
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        system_prompt: str = "",
        timeout: int = 600,
        max_iterations: int = 30,
    ) -> None:
        import docker  # type: ignore[import-untyped]

        self._docker = docker.from_env()
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._system_prompt = system_prompt
        self._timeout = timeout
        self._max_iterations = max_iterations

    def run_task(
        self,
        image_tag: str,
        instance: TaskInstance,
        workspace: Path,
    ) -> tuple[str, int, float]:
        start = time.monotonic()

        cmd = [
            "--prompt",
            instance.prompt,
            "--workspace",
            "/workspace",
            "--model",
            self._model,
            "--api-key",
            self._api_key,
            "--max-iterations",
            str(self._max_iterations),
        ]
        if self._base_url:
            cmd.extend(["--base-url", self._base_url])
        if self._system_prompt:
            cmd.extend(["--system-prompt", self._system_prompt])

        docker_sock = Path("/var/run/docker.sock")
        extra_volumes: dict[str, dict[str, str]] = {}
        if docker_sock.exists():
            extra_volumes[str(docker_sock)] = {
                "bind": "/var/run/docker.sock",
                "mode": "rw",
            }

        try:
            import io
            import tarfile

            container = self._docker.containers.create(
                image_tag,
                command=cmd,
                volumes=extra_volumes,
                mem_limit="2g",
                cpu_count=2,
                network_mode="host",
            )

            tar_buf = io.BytesIO()
            with tarfile.open(fileobj=tar_buf, mode="w") as tar:
                for fpath in workspace.rglob("*"):
                    if fpath.is_file():
                        rel = str(fpath.relative_to(workspace))
                        tar.add(str(fpath), arcname=rel)
            tar_buf.seek(0)
            container.put_archive("/workspace", tar_buf)

            container.start()
            result = container.wait(timeout=self._timeout)
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            try:
                archive, _ = container.get_archive("/workspace")
                out_buf = io.BytesIO()
                for chunk in archive:
                    out_buf.write(chunk)
                out_buf.seek(0)
                with tarfile.open(fileobj=out_buf, mode="r") as tar:
                    for member in tar.getmembers():
                        if member.isfile():
                            name = member.name
                            if name.startswith("workspace/"):
                                name = name[len("workspace/") :]
                            dest = workspace / name
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            f = tar.extractfile(member)
                            if f:
                                dest.write_bytes(f.read())
            except Exception:
                pass

            container.remove(force=True)

            if result.get("StatusCode", 1) != 0 and stderr:
                log.debug(
                    "Agent stderr for %s: %s",
                    image_tag,
                    stderr[:500],
                )
        except Exception as exc:
            elapsed = time.monotonic() - start
            log.warning(
                "Container execution failed for %s: %s",
                image_tag,
                exc,
            )
            return "", 0, elapsed

        elapsed = time.monotonic() - start
        exit_code = result.get("StatusCode", 1)

        if exit_code != 0:
            log.warning("Container %s exited with code %d", image_tag, exit_code)

        tokens_used = 0
        meta_path = workspace / "metadata.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                tokens_used = int(meta.get("tokens_used", 0))
            except (json.JSONDecodeError, ValueError):
                pass

        return stdout.strip(), tokens_used, elapsed


class DryRunDockerRunner:
    def run_task(
        self,
        image_tag: str,
        instance: TaskInstance,
        workspace: Path,
    ) -> tuple[str, int, float]:
        prompt_hash = hash(instance.prompt) % 100
        if prompt_hash < 70:
            return "# solution placeholder\nresult = 42", 150, 0.01
        return instance.expected_output or "PASS", 200, 0.01


def evaluate_package(
    package: AgentPackage,
    tasks: list[Task],
    builder: DockerBuilder | DryRunDockerBuilder,
    runner: DockerRunner | DryRunDockerRunner,
    logger: Any = None,
    token_budget: int = 50_000,
) -> EvalReport:
    image_tag = builder.build(package)
    all_results: list[TaskResult] = []

    for task in tasks:
        for instance in task.get_instances():
            with tempfile.TemporaryDirectory() as tmpdir:
                workspace = Path(tmpdir)
                for fname, content in instance.setup_files.items():
                    fpath = workspace / fname
                    fpath.parent.mkdir(parents=True, exist_ok=True)
                    fpath.write_text(content, encoding="utf-8")

                output, tokens, wall_time = runner.run_task(image_tag, instance, workspace)

                try:
                    result = task.score(instance, workspace, output)
                    result = TaskResult(
                        instance_id=result.instance_id,
                        passed=result.passed,
                        score=result.score,
                        tokens_used=tokens,
                        wall_time_seconds=wall_time,
                        raw_output=output,
                        error=result.error,
                    )
                except Exception as exc:
                    result = TaskResult(
                        instance_id=instance.instance_id,
                        passed=False,
                        score=0.0,
                        tokens_used=tokens,
                        wall_time_seconds=wall_time,
                        raw_output=output,
                        error=str(exc),
                    )

                all_results.append(result)

                if logger is not None:
                    logger.log_eval_result(
                        task_id=result.instance_id,
                        config_id=package.package_id,
                        passed=result.passed,
                        score=result.score,
                        tokens_used=result.tokens_used,
                        wall_time=result.wall_time_seconds,
                        error=result.error,
                    )
                    if not result.passed:
                        logger.log_failure_case(
                            task_id=result.instance_id,
                            config_id=package.package_id,
                            error_details=result.error or "incorrect",
                            agent_output=result.raw_output,
                        )

    scores: dict[str, float] = {}
    if all_results:
        accuracy = sum(1 for r in all_results if r.passed) / len(all_results)
        total_tokens = sum(r.tokens_used for r in all_results)
        scores = {
            "accuracy": accuracy,
            "total_tokens": float(total_tokens),
        }

    return EvalReport(
        results=all_results,
        scores=scores,
        config_id=package.package_id,
        generation=package.generation,
    )
