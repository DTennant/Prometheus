from __future__ import annotations

import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from openharness_evolve.cli import app

runner = CliRunner()


class TestCLI:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Self-Bootstrapping" in result.output

    def test_run_help(self):
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "--generations" in result.output
        assert "--dry-run" in result.output

    def test_eval_only_help(self):
        result = runner.invoke(app, ["eval-only", "--help"])
        assert result.exit_code == 0
        assert "CONFIG_PATH" in result.output

    def test_compare_help(self):
        result = runner.invoke(app, ["compare", "--help"])
        assert result.exit_code == 0

    def test_show_help(self):
        result = runner.invoke(app, ["show", "--help"])
        assert result.exit_code == 0

    def test_dry_run_completes(self, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "run",
                "--dry-run",
                "--generations",
                "1",
                "--beam-size",
                "1",
                "--mutations-per-parent",
                "1",
                "--output-dir",
                str(tmp_path),
                "--task-suite",
                "code_generation",
            ],
        )
        assert result.exit_code == 0
        assert "Evolution complete" in result.output

    def test_eval_only_dry_run(self, tmp_path: Path):
        config_path = tmp_path / "test_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "system_prompt": "You are a test assistant.",
                    "parameters": {"max_iterations": 10, "timeout_per_task": 60},
                }
            )
        )
        result = runner.invoke(
            app,
            [
                "eval-only",
                str(config_path),
                "--dry-run",
                "--output-dir",
                str(tmp_path / "results"),
                "--task-suite",
                "code_generation",
            ],
        )
        assert result.exit_code == 0
        assert "Accuracy" in result.output

    def test_show_nonexistent_run(self, tmp_path: Path):
        run_dir = tmp_path / "nonexistent"
        run_dir.mkdir()
        result = runner.invoke(app, ["show", str(run_dir)])
        assert result.exit_code == 0
        assert "Generations: 0" in result.output

    def test_compare_runs(self, tmp_path: Path):
        for i in range(2):
            run_dir = tmp_path / f"run{i}"
            run_dir.mkdir()
            (run_dir / "config.json").write_text(json.dumps({"model": {"name": f"model{i}"}}))
            events = [
                json.dumps(
                    {
                        "type": "generation",
                        "generation": 0,
                        "best_score": 0.5 + i * 0.2,
                        "config_ids": [f"c{i}"],
                        "metrics": {},
                        "timestamp": 0,
                    }
                )
            ]
            (run_dir / "events.jsonl").write_text("\n".join(events))

        result = runner.invoke(app, ["compare", str(tmp_path / "run0"), str(tmp_path / "run1")])
        assert result.exit_code == 0
        assert "model0" in result.output
        assert "model1" in result.output
