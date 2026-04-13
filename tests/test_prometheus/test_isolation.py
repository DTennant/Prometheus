from __future__ import annotations

import pytest
from pathlib import Path

from prometheus.config.harness_config import HarnessConfig
from prometheus.eval.query_runner import DryRunAgentClient
from prometheus.eval.runner import EvalRunner
from prometheus.eval.sandbox import TaskSandbox
from prometheus.eval.task import Task, TaskInstance, TaskResult


class FileWritingTask(Task):
    name = "file_writer"
    category = "test"

    def get_instances(self) -> list[TaskInstance]:
        return [
            TaskInstance(
                instance_id="iso_1",
                prompt="write a file",
                expected_output="original",
                setup_files={"data.txt": "original"},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        content = (workspace / "data.txt").read_text()
        return TaskResult(instance.instance_id, content == "original", 1.0, 0, 0.0, agent_output)


class TestSandboxIsolation:
    def test_tmpdir_is_unique_per_setup(self):
        sandbox1 = TaskSandbox()
        sandbox2 = TaskSandbox()
        inst = TaskInstance("t1", "p", "o", {"f.txt": "hello"})

        ws1 = sandbox1.setup(inst)
        ws2 = sandbox2.setup(inst)

        assert ws1 != ws2
        assert (ws1 / "f.txt").read_text() == "hello"
        assert (ws2 / "f.txt").read_text() == "hello"

        (ws1 / "f.txt").write_text("modified")
        assert (ws2 / "f.txt").read_text() == "hello"

        sandbox1.cleanup()
        sandbox2.cleanup()

    def test_context_manager_cleans_up(self):
        with TaskSandbox() as sb:
            ws = sb.setup(TaskInstance("t1", "p", "o", {"f.txt": "data"}))
            assert ws.exists()
            ws_path = ws
        assert not ws_path.exists()

    def test_setup_files_are_copies_not_references(self):
        original_files = {"a.txt": "content_a", "b.txt": "content_b"}
        inst = TaskInstance("t1", "p", "o", dict(original_files))

        with TaskSandbox() as sb:
            ws = sb.setup(inst)
            (ws / "a.txt").write_text("MODIFIED")

        assert inst.setup_files["a.txt"] == "content_a"

    def test_get_instances_returns_fresh_objects(self):
        task = FileWritingTask()
        instances_1 = task.get_instances()
        instances_2 = task.get_instances()
        assert instances_1[0] is not instances_2[0]
        instances_1[0].setup_files["data.txt"] = "CORRUPTED"
        assert instances_2[0].setup_files["data.txt"] == "original"

    @pytest.mark.asyncio
    async def test_multiple_evals_dont_share_state(self):
        task = FileWritingTask()
        client = DryRunAgentClient()
        runner = EvalRunner([task], client)

        config1 = HarnessConfig(system_prompt="config 1", config_id="c1")
        config2 = HarnessConfig(system_prompt="config 2", config_id="c2")

        report1 = await runner.evaluate(config1)
        report2 = await runner.evaluate(config2)

        assert len(report1.results) == 1
        assert len(report2.results) == 1
        assert report1.results[0].passed == report2.results[0].passed

    @pytest.mark.asyncio
    async def test_harness_config_unchanged_after_eval(self):
        config = HarnessConfig(system_prompt="test prompt", config_id="original")
        original_prompt = config.system_prompt
        original_id = config.config_id

        runner = EvalRunner([FileWritingTask()], DryRunAgentClient())
        await runner.evaluate(config)

        assert config.system_prompt == original_prompt
        assert config.config_id == original_id

    def test_sandbox_workspace_isolated_from_cwd(self):
        import os

        cwd = os.getcwd()
        with TaskSandbox() as sb:
            ws = sb.setup(TaskInstance("t1", "p", "o", {"test.txt": "data"}))
            assert str(ws) != cwd
            assert not (Path(cwd) / "test.txt").exists()
