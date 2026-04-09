import pytest
from prometheus.config.harness_config import HarnessConfig, WorkflowConfig, WorkflowPhase
from prometheus.eval.scorer import EvalReport
from prometheus.eval.task import TaskResult
from prometheus.evolution.selector import BeamSelector
from prometheus.evolution.history import EvolutionHistory


def _make_config(prompt: str, config_id: str = "test") -> HarnessConfig:
    return HarnessConfig(system_prompt=prompt, config_id=config_id)


def _make_report(accuracy_results: list[bool], config_id: str = "test") -> EvalReport:
    results = [
        TaskResult(f"t{i}", passed, 1.0 if passed else 0.0, 100, 1.0, "output")
        for i, passed in enumerate(accuracy_results)
    ]
    return EvalReport(results=results, config_id=config_id)


class TestBeamSelector:
    def test_selects_top_k(self):
        selector = BeamSelector(beam_size=2)
        candidates = [
            (_make_config("low", "c1"), _make_report([False, False], "c1")),
            (_make_config("mid", "c2"), _make_report([True, False], "c2")),
            (_make_config("high", "c3"), _make_report([True, True], "c3")),
        ]
        selected = selector.select(candidates)
        assert len(selected) == 2
        assert selected[0].system_prompt == "high"
        assert selected[1].system_prompt == "mid"

    def test_deduplicates(self):
        selector = BeamSelector(beam_size=3)
        candidates = [
            (_make_config("same", "c1"), _make_report([True, True], "c1")),
            (_make_config("same", "c2"), _make_report([True, False], "c2")),
            (_make_config("different", "c3"), _make_report([True, False], "c3")),
        ]
        selected = selector.select(candidates)
        assert len(selected) == 2  # "same" deduplicated

    def test_empty_candidates(self):
        selector = BeamSelector(beam_size=3)
        assert selector.select([]) == []

    def test_dedup_preserves_workflow_diversity(self) -> None:
        selector = BeamSelector(beam_size=3)
        c1 = HarnessConfig(system_prompt="same prompt", config_id="c1")
        c2 = HarnessConfig(
            system_prompt="same prompt",
            config_id="c2",
            workflow=WorkflowConfig(
                phases=[
                    WorkflowPhase(
                        name="planning",
                        prompt_template="Plan: $task",
                        max_iterations=5,
                    ),
                    WorkflowPhase(name="execution", prompt_template="$task"),
                ],
            ),
        )
        candidates = [
            (c1, _make_report([True, True], "c1")),
            (c2, _make_report([True, False], "c2")),
        ]
        selected = selector.select(candidates)
        assert len(selected) == 2


class TestEvolutionHistory:
    def test_add_and_get_generation(self):
        history = EvolutionHistory()
        configs = [_make_config("test", "c1")]
        reports = [_make_report([True], "c1")]
        history.add_generation(0, configs, reports)
        assert history.num_generations == 1
        rec = history.get_generation(0)
        assert rec is not None
        assert rec.best_score == 1.0

    def test_get_best(self):
        history = EvolutionHistory()
        history.add_generation(0, [_make_config("low", "c1")], [_make_report([False], "c1")])
        history.add_generation(1, [_make_config("high", "c2")], [_make_report([True], "c2")])
        best = history.get_best(1)
        assert len(best) == 1
        assert best[0][1] == 1.0

    def test_summary_for_mutation(self):
        history = EvolutionHistory()
        history.add_generation(0, [_make_config("t", "c1")], [_make_report([True], "c1")])
        summary = history.summary_for_mutation()
        assert "Gen 0" in summary

    def test_json_roundtrip(self):
        history = EvolutionHistory()
        history.add_generation(0, [_make_config("test", "c1")], [_make_report([True], "c1")])
        history.add_generation(1, [_make_config("test2", "c2")], [_make_report([False], "c2")])
        json_str = history.to_json()
        restored = EvolutionHistory.from_json(json_str)
        assert restored.num_generations == 2
        assert restored.get_best(1)[0][1] == 1.0

    def test_nonexistent_generation(self):
        history = EvolutionHistory()
        assert history.get_generation(999) is None
