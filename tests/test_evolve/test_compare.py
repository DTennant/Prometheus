from __future__ import annotations

import json
import pytest
from pathlib import Path

from openharness_evolve.analysis.compare import load_run, compare_runs, format_comparison


class TestAnalysis:
    def test_load_run_empty(self, tmp_path: Path):
        run_dir = tmp_path / "empty_run"
        run_dir.mkdir()
        summary = load_run(run_dir)
        assert summary.total_generations == 0
        assert summary.best_score == 0.0

    def test_load_run_with_data(self, tmp_path: Path):
        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        (run_dir / "config.json").write_text(json.dumps({"model": {"name": "test-model"}}))
        events = [
            json.dumps(
                {
                    "type": "generation",
                    "generation": 0,
                    "best_score": 0.5,
                    "config_ids": ["c1"],
                    "metrics": {},
                    "timestamp": 0,
                }
            ),
            json.dumps(
                {
                    "type": "generation",
                    "generation": 1,
                    "best_score": 0.8,
                    "config_ids": ["c2"],
                    "metrics": {},
                    "timestamp": 1,
                }
            ),
        ]
        (run_dir / "events.jsonl").write_text("\n".join(events))

        summary = load_run(run_dir)
        assert summary.total_generations == 2
        assert summary.best_score == 0.8

    def test_compare_runs_sorted(self, tmp_path: Path):
        for i, score in enumerate([0.3, 0.9, 0.6]):
            d = tmp_path / f"run{i}"
            d.mkdir()
            (d / "config.json").write_text(json.dumps({"model": {"name": f"m{i}"}}))
            (d / "events.jsonl").write_text(
                json.dumps(
                    {
                        "type": "generation",
                        "generation": 0,
                        "best_score": score,
                        "config_ids": ["c"],
                        "metrics": {},
                        "timestamp": 0,
                    }
                )
            )

        rows = compare_runs([tmp_path / f"run{i}" for i in range(3)])
        assert len(rows) == 3
        assert rows[0].best_score == 0.9
        assert rows[2].best_score == 0.3

    def test_format_comparison(self):
        from openharness_evolve.analysis.compare import ComparisonRow

        rows = [
            ComparisonRow("run1", 10, 0.9, "claude"),
            ComparisonRow("run2", 5, 0.7, "gpt4o"),
        ]
        output = format_comparison(rows)
        assert "run1" in output
        assert "claude" in output
        assert "0.9000" in output

    def test_format_empty(self):
        assert "No runs" in format_comparison([])
