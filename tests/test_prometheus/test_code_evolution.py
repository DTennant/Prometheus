from __future__ import annotations

import json
from pathlib import Path

import pytest
from prometheus.code_evolution.builder import DryRunDockerBuilder
from prometheus.code_evolution.history import CodeEvolutionHistory
from prometheus.code_evolution.mutator import (
    DryRunCodeMutator,
    mutate_package,
)
from prometheus.code_evolution.package import AgentPackage
from prometheus.code_evolution.runner import (
    DryRunDockerRunner,
    evaluate_package,
)
from prometheus.code_evolution.seed import create_seed_package
from prometheus.code_evolution.selector import CodeBeamSelector
from prometheus.eval.scorer import EvalReport
from prometheus.eval.task import (
    Task,
    TaskInstance,
    TaskResult,
)


# ── helpers ──────────────────────────────────────────────────


def _make_package(
    pkg_id: str = "test",
    gen: int = 0,
    parent: str | None = None,
) -> AgentPackage:
    pkg = create_seed_package()
    pkg.package_id = pkg_id
    pkg.generation = gen
    pkg.parent_id = parent
    return pkg


def _make_eval_report(
    passed_count: int,
    total: int,
    pkg_id: str = "test",
) -> EvalReport:
    results = []
    for i in range(total):
        results.append(
            TaskResult(
                instance_id=f"task_{i}",
                passed=i < passed_count,
                score=1.0 if i < passed_count else 0.0,
                tokens_used=100,
                wall_time_seconds=1.0,
                raw_output="output",
            )
        )
    return EvalReport(
        results=results,
        scores={
            "accuracy": passed_count / max(total, 1),
            "total_tokens": float(100 * total),
        },
        config_id=pkg_id,
        generation=0,
    )


class StubTask(Task):
    """Minimal Task for evaluate_package tests."""

    name = "stub"
    category = "test"

    def get_instances(self) -> list[TaskInstance]:
        return [
            TaskInstance(
                instance_id="stub_001",
                prompt="Write hello world",
                expected_output="print('hello world')",
                setup_files={"main.py": "# placeholder"},
            ),
        ]

    def score(
        self,
        instance: TaskInstance,
        workspace: Path,
        agent_output: str,
    ) -> TaskResult:
        return TaskResult(
            instance_id=instance.instance_id,
            passed=len(agent_output) > 0,
            score=1.0 if agent_output else 0.0,
            tokens_used=0,
            wall_time_seconds=0.0,
            raw_output=agent_output,
        )


# ── TestAgentPackage ─────────────────────────────────────────


class TestAgentPackage:
    def test_to_directory_creates_files(self, tmp_path: Path) -> None:
        pkg = _make_package()
        pkg.to_directory(tmp_path)
        for relpath in pkg.files:
            assert (tmp_path / relpath).exists()

    def test_from_directory_roundtrip(self, tmp_path: Path) -> None:
        pkg = _make_package(pkg_id="round")
        pkg.to_directory(tmp_path)
        restored = AgentPackage.from_directory(tmp_path, package_id="round", generation=0)
        assert restored.files.keys() == pkg.files.keys()
        for key in pkg.files:
            assert restored.files[key] == pkg.files[key]

    def test_content_hash_deterministic(self) -> None:
        a = _make_package(pkg_id="a")
        b = _make_package(pkg_id="b")
        assert a.content_hash() == b.content_hash()

    def test_content_hash_changes(self) -> None:
        a = _make_package()
        b = _make_package()
        b.files["extra.py"] = "# extra"
        assert a.content_hash() != b.content_hash()

    def test_json_roundtrip(self) -> None:
        pkg = _make_package(pkg_id="json_test", gen=2, parent="p1")
        json_str = pkg.to_json()
        restored = AgentPackage.from_json(json_str)
        assert restored.package_id == "json_test"
        assert restored.generation == 2
        assert restored.parent_id == "p1"
        assert restored.files == pkg.files


# ── TestSeedPackage ──────────────────────────────────────────


class TestSeedPackage:
    def test_create_seed_package(self) -> None:
        pkg = create_seed_package()
        assert pkg.package_id == "seed"
        assert pkg.generation == 0
        assert len(pkg.files) == 9

    def test_seed_files_contain_required_content(
        self,
    ) -> None:
        pkg = create_seed_package()
        assert "entry" in pkg.files["pyproject.toml"] or (
            "[project.scripts]" in pkg.files["pyproject.toml"]
        )
        assert "FROM" in pkg.files["Dockerfile"]
        assert "run_agent" in pkg.files["src/agent/agent.py"]
        assert "src/agent/planner.py" in pkg.files
        assert "src/agent/context.py" in pkg.files
        assert "create_plan" in pkg.files["src/agent/planner.py"]
        assert "should_summarize" in pkg.files["src/agent/context.py"]
        assert "edit_file" in pkg.files["src/agent/tools.py"]
        assert "search_files" in pkg.files["src/agent/tools.py"]
        assert "run_tests" in pkg.files["src/agent/tools.py"]


# ── TestDryRunCodeMutator ────────────────────────────────────


def _build_prompt_with_files() -> str:
    from prometheus.code_evolution.mutator import (
        _build_code_mutation_prompt,
    )

    pkg = _make_package()
    report = _make_eval_report(3, 5, pkg.package_id)
    history = CodeEvolutionHistory()
    return _build_code_mutation_prompt(pkg, report, history)


class TestDryRunCodeMutator:
    @pytest.mark.asyncio
    async def test_diverse_mutations(self) -> None:
        mutator = DryRunCodeMutator()
        prompt = _build_prompt_with_files()
        results: list[str] = []
        for _ in range(4):
            raw = await mutator.generate(prompt)
            results.append(raw)
        distinct = {r for r in results}
        assert len(distinct) >= 3

    @pytest.mark.asyncio
    async def test_mutation_returns_valid_json(
        self,
    ) -> None:
        mutator = DryRunCodeMutator()
        prompt = _build_prompt_with_files()
        for _ in range(4):
            raw = await mutator.generate(prompt)
            parsed = json.loads(raw)
            assert isinstance(parsed, list)


# ── TestCodeMutator (mutate_package) ─────────────────────────


class FakeValidCodeClient:
    """Returns a valid file-ops JSON array."""

    async def generate(self, prompt: str) -> str:
        return json.dumps(
            [
                {
                    "op": "modify",
                    "path": "src/agent/agent.py",
                    "content": "# mutated agent\n",
                }
            ]
        )


class FakeInvalidThenValidClient:
    """Returns invalid JSON twice, then valid."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.calls < 3:
            return "NOT JSON"
        return json.dumps(
            [
                {
                    "op": "modify",
                    "path": "src/agent/agent.py",
                    "content": "# finally valid\n",
                }
            ]
        )


class TestCodeMutator:
    @pytest.mark.asyncio
    async def test_mutate_package_valid(self) -> None:
        pkg = _make_package(pkg_id="parent1", gen=1)
        report = _make_eval_report(3, 5, "parent1")
        history = CodeEvolutionHistory()
        result = await mutate_package(FakeValidCodeClient(), pkg, report, history)
        assert result.generation == 2
        assert result.parent_id == "parent1"
        assert "mutated agent" in result.files["src/agent/agent.py"]

    @pytest.mark.asyncio
    async def test_mutate_package_retry_on_invalid(
        self,
    ) -> None:
        pkg = _make_package(pkg_id="retry_parent")
        report = _make_eval_report(1, 3, "retry_parent")
        history = CodeEvolutionHistory()
        client = FakeInvalidThenValidClient()
        result = await mutate_package(client, pkg, report, history)
        assert client.calls == 3
        assert "finally valid" in result.files["src/agent/agent.py"]


# ── TestDryRunDockerBuilder ──────────────────────────────────


class TestDryRunDockerBuilder:
    def test_build_returns_tag(self) -> None:
        builder = DryRunDockerBuilder()
        pkg = _make_package(pkg_id="build_test")
        tag = builder.build(pkg)
        assert "build_test" in tag

    def test_cleanup_noop(self) -> None:
        builder = DryRunDockerBuilder()
        builder.cleanup("some-tag")


# ── TestCodeBeamSelector ─────────────────────────────────────


class TestCodeBeamSelector:
    def test_selects_top_k(self) -> None:
        selector = CodeBeamSelector(beam_size=3)
        candidates = []
        for i in range(5):
            pkg = _make_package(pkg_id=f"c{i}", gen=1)
            pkg.files["marker.txt"] = f"variant_{i}"
            report = _make_eval_report(i, 5, f"c{i}")
            candidates.append((pkg, report))
        selected = selector.select(candidates)
        assert len(selected) == 3
        assert selected[0].package_id == "c4"

    def test_deduplicates(self) -> None:
        selector = CodeBeamSelector(beam_size=3)
        p1 = _make_package(pkg_id="dup1")
        p2 = _make_package(pkg_id="dup2")
        assert p1.content_hash() == p2.content_hash()
        candidates = [
            (p1, _make_eval_report(5, 5, "dup1")),
            (p2, _make_eval_report(4, 5, "dup2")),
        ]
        selected = selector.select(candidates)
        assert len(selected) == 1

    def test_empty_candidates(self) -> None:
        selector = CodeBeamSelector(beam_size=3)
        assert selector.select([]) == []


# ── TestCodeEvolutionHistory ─────────────────────────────────


class TestCodeEvolutionHistory:
    def test_add_and_get_generation(self) -> None:
        history = CodeEvolutionHistory()
        pkg = _make_package(pkg_id="h1")
        report = _make_eval_report(3, 5, "h1")
        history.add_generation(0, [pkg], [report])
        rec = history.get_generation(0)
        assert rec is not None
        assert rec.best_package_id == "h1"
        assert rec.best_score > 0

    def test_get_best(self) -> None:
        history = CodeEvolutionHistory()
        p1 = _make_package(pkg_id="low")
        r1 = _make_eval_report(1, 5, "low")
        history.add_generation(0, [p1], [r1])
        p2 = _make_package(pkg_id="high")
        r2 = _make_eval_report(5, 5, "high")
        history.add_generation(1, [p2], [r2])
        best = history.get_best(1)
        assert len(best) == 1
        assert best[0][0] == "high"

    def test_summary_for_mutation(self) -> None:
        history = CodeEvolutionHistory()
        pkg = _make_package(pkg_id="s1")
        report = _make_eval_report(2, 5, "s1")
        history.add_generation(0, [pkg], [report])
        summary = history.summary_for_mutation()
        assert "Gen 0" in summary
        assert len(summary) > 0

    def test_json_roundtrip(self) -> None:
        history = CodeEvolutionHistory()
        p1 = _make_package(pkg_id="j1")
        r1 = _make_eval_report(3, 5, "j1")
        history.add_generation(0, [p1], [r1])
        p2 = _make_package(pkg_id="j2")
        r2 = _make_eval_report(4, 5, "j2")
        history.add_generation(1, [p2], [r2])
        json_str = history.to_json()
        restored = CodeEvolutionHistory.from_json(json_str)
        assert restored.get_generation(0) is not None
        assert restored.get_generation(1) is not None
        orig_best = history.get_best(1)
        rest_best = restored.get_best(1)
        assert orig_best[0][0] == rest_best[0][0]


# ── TestDryRunDockerRunner ───────────────────────────────────


class TestDryRunDockerRunner:
    def test_run_task_returns_tuple(self, tmp_path: Path) -> None:
        runner = DryRunDockerRunner()
        instance = TaskInstance(
            instance_id="run_001",
            prompt="do something",
            expected_output="done",
            setup_files={},
        )
        result = runner.run_task("dry-run:test", instance, tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 3
        output, tokens, wall_time = result
        assert isinstance(output, str)
        assert isinstance(tokens, int)
        assert isinstance(wall_time, float)


# ── TestEvaluatePackage ──────────────────────────────────────


class TestEvaluatePackage:
    def test_evaluate_with_dry_run(self) -> None:
        pkg = _make_package(pkg_id="eval_pkg")
        builder = DryRunDockerBuilder()
        runner = DryRunDockerRunner()
        tasks: list[Task] = [StubTask()]
        report = evaluate_package(pkg, tasks, builder, runner)
        assert isinstance(report, EvalReport)
        assert len(report.results) > 0
        assert report.config_id == "eval_pkg"


# ── TestCodeEvolutionLoop ────────────────────────────────────


class TestCodeEvolutionLoop:
    @pytest.mark.asyncio
    async def test_dry_run_completes(self, tmp_path: Path) -> None:
        from prometheus.code_evolution.loop import (
            CodeEvolutionLoop,
        )
        from prometheus.config.experiment_config import (
            ExperimentConfig,
        )
        from prometheus.logging.experiment_logger import (
            ExperimentLogger,
        )

        config = ExperimentConfig(
            generations=2,
            beam_size=2,
            mutations_per_parent=1,
            output_dir=tmp_path,
            dry_run=True,
        )
        logger = ExperimentLogger(tmp_path / "run_test")
        builder = DryRunDockerBuilder()
        runner = DryRunDockerRunner()
        mutator = DryRunCodeMutator()
        tasks: list[Task] = [StubTask()]
        seed = create_seed_package()

        loop = CodeEvolutionLoop(
            config=config,
            llm_client=mutator,
            builder=builder,
            runner=runner,
            tasks=tasks,
            logger=logger,
        )
        best = await loop.run(seed)

        assert isinstance(best, AgentPackage)
        best_dir = tmp_path / "run_test" / "best_agent"
        assert best_dir.exists()
        assert loop.history.get_generation(0) is not None
        assert loop.history.get_generation(1) is not None
