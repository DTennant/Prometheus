import pytest
import asyncio
from pathlib import Path
from prometheus.config.harness_config import HarnessConfig, WorkflowConfig, WorkflowPhase
from prometheus.eval.sandbox import TaskSandbox
from prometheus.eval.query_runner import run_eval_query, DryRunAgentClient
from prometheus.eval.runner import EvalRunner
from prometheus.eval.task import Task, TaskInstance, TaskResult


class AlwaysPassTask(Task):
    name = "always_pass"
    category = "test"

    def get_instances(self) -> list[TaskInstance]:
        return [TaskInstance("p1", "do something", "done", {"test.txt": "hello"})]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return TaskResult("p1", True, 1.0, 0, 0.0, agent_output)


class AlwaysFailTask(Task):
    name = "always_fail"
    category = "test"

    def get_instances(self) -> list[TaskInstance]:
        return [TaskInstance("f1", "do something", "done")]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return TaskResult("f1", False, 0.0, 0, 0.0, agent_output, error="wrong")


class TestSandbox:
    def test_setup_creates_files(self, tmp_path: Path):
        sandbox = TaskSandbox(workspace=tmp_path / "work")
        instance = TaskInstance(
            "t1", "prompt", "out", {"a.txt": "content_a", "sub/b.txt": "content_b"}
        )
        ws = sandbox.setup(instance)
        assert (ws / "a.txt").read_text() == "content_a"
        assert (ws / "sub" / "b.txt").read_text() == "content_b"

    def test_cleanup(self):
        sandbox = TaskSandbox()
        instance = TaskInstance("t1", "prompt", "out", {"a.txt": "x"})
        ws = sandbox.setup(instance)
        assert ws.exists()
        sandbox.cleanup()

    def test_context_manager(self):
        with TaskSandbox() as sandbox:
            ws = sandbox.setup(TaskInstance("t1", "p", "o", {"f.txt": "data"}))
            assert (ws / "f.txt").exists()

    def test_run_command(self, tmp_path: Path):
        sandbox = TaskSandbox(workspace=tmp_path / "work")
        sandbox.setup(TaskInstance("t1", "p", "o", {"hello.txt": "world"}))
        result = sandbox.run_command(["cat", "hello.txt"])
        assert result.stdout.strip() == "world"


class TestQueryRunner:
    @pytest.mark.asyncio
    async def test_successful_run(self):
        client = DryRunAgentClient(default_output="result = 42")
        result = await run_eval_query(client, "prompt", "system", max_iterations=10, timeout=5)
        assert result.output == "result = 42"
        assert result.tokens_used == 150
        assert not result.timed_out
        assert result.error is None

    @pytest.mark.asyncio
    async def test_timeout(self):
        class SlowClient:
            async def run_task(self, prompt, system_prompt, max_iterations, workspace):
                await asyncio.sleep(10)
                return "late", 0

        result = await run_eval_query(SlowClient(), "p", "s", timeout=1)
        assert result.timed_out
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        class ErrorClient:
            async def run_task(self, prompt, system_prompt, max_iterations, workspace):
                raise ValueError("API error")

        result = await run_eval_query(ErrorClient(), "p", "s")
        assert result.error == "API error"


class TestEvalRunner:
    @pytest.mark.asyncio
    async def test_all_pass(self):
        runner = EvalRunner([AlwaysPassTask()], DryRunAgentClient())
        config = HarnessConfig(system_prompt="test", config_id="c1")
        report = await runner.evaluate(config)
        assert report.accuracy == 1.0
        assert len(report.results) == 1

    @pytest.mark.asyncio
    async def test_mixed_results(self):
        runner = EvalRunner([AlwaysPassTask(), AlwaysFailTask()], DryRunAgentClient())
        config = HarnessConfig(system_prompt="test")
        report = await runner.evaluate(config)
        assert report.accuracy == 0.5
        assert len(report.results) == 2

    @pytest.mark.asyncio
    async def test_workflow_phases_executed(self):
        class CaptureClient:
            prompts: list[str] = []

            async def run_task(self, prompt, system_prompt, max_iterations, workspace):
                CaptureClient.prompts.append(prompt)
                return "phase output", 100

        CaptureClient.prompts = []
        config = HarnessConfig(
            system_prompt="sys",
            workflow=WorkflowConfig(
                phases=[
                    WorkflowPhase(name="planning", prompt_template="PLAN: $task", max_iterations=5),
                    WorkflowPhase(
                        name="execution", prompt_template="DO: $task\nPLAN: $previous_output"
                    ),
                ],
            ),
        )
        runner = EvalRunner([AlwaysPassTask()], CaptureClient())
        await runner.evaluate(config)
        assert len(CaptureClient.prompts) == 2
        assert "PLAN:" in CaptureClient.prompts[0]
        assert "DO:" in CaptureClient.prompts[1]
        assert "phase output" in CaptureClient.prompts[1]

    @pytest.mark.asyncio
    async def test_few_shot_injected(self):
        class CaptureClient:
            last_prompt: str = ""

            async def run_task(self, prompt, system_prompt, max_iterations, workspace):
                CaptureClient.last_prompt = prompt
                return "ok", 100

        from prometheus.config.harness_config import FewShotExample

        config = HarnessConfig(
            system_prompt="sys",
            few_shot_examples=[FewShotExample(task="add 1+1", solution="2")],
        )
        runner = EvalRunner([AlwaysPassTask()], CaptureClient())
        await runner.evaluate(config)
        assert "add 1+1" in CaptureClient.last_prompt
        assert "2" in CaptureClient.last_prompt

    @pytest.mark.asyncio
    async def test_custom_tools_in_system_prompt(self):
        class CaptureClient:
            last_system: str = ""

            async def run_task(self, prompt, system_prompt, max_iterations, workspace):
                CaptureClient.last_system = system_prompt
                return "ok", 100

        from prometheus.config.harness_config import CustomToolDef

        config = HarnessConfig(
            system_prompt="base",
            custom_tools=[
                CustomToolDef(
                    name="search_and_read",
                    description="grep then read",
                    sub_tools=["execute", "read_file"],
                ),
            ],
        )
        runner = EvalRunner([AlwaysPassTask()], CaptureClient())
        await runner.evaluate(config)
        assert "search_and_read" in CaptureClient.last_system
        assert "grep then read" in CaptureClient.last_system

    @pytest.mark.asyncio
    async def test_backward_compat_workflow_prompts(self):
        config = HarnessConfig.model_validate(
            {
                "system_prompt": "test",
                "workflow_prompts": {"pre_task": "BEFORE", "post_task": "AFTER"},
            }
        )
        assert len(config.workflow.phases) == 1
        assert "BEFORE" in config.workflow.phases[0].prompt_template
        assert "AFTER" in config.workflow.phases[0].prompt_template
        assert "$task" in config.workflow.phases[0].prompt_template
