import json
import pytest
from pathlib import Path
from prometheus.logging.experiment_logger import ExperimentLogger


class TestExperimentLogger:
    def test_creates_dir_and_config(self, tmp_path: Path):
        run_dir = tmp_path / "run1"
        logger = ExperimentLogger(run_dir, config={"model": "test"})
        assert run_dir.exists()
        config = json.loads((run_dir / "config.json").read_text())
        assert config["model"] == "test"

    def test_jsonl_events_valid(self, tmp_path: Path):
        logger = ExperimentLogger(tmp_path / "run")
        logger.log_generation(0, ["cfg1"], 0.8)
        logger.log_generation(1, ["cfg2"], 0.9)
        events = logger.load_events()
        assert len(events) == 2
        assert all("timestamp" in e for e in events)
        assert events[0]["type"] == "generation"

    def test_checkpoint_roundtrip(self, tmp_path: Path):
        logger = ExperimentLogger(tmp_path / "run")
        data = {"system_prompt": "test", "generation": 5}
        path = logger.save_checkpoint(data, 5)
        restored = logger.load_checkpoint(path)
        assert restored == data

    def test_eval_result_logged(self, tmp_path: Path):
        logger = ExperimentLogger(tmp_path / "run")
        logger.log_eval_result("task1", "cfg1", True, 1.0, 500, 2.5)
        events = logger.load_events()
        assert len(events) == 1
        assert events[0]["type"] == "eval_result"
        assert events[0]["passed"] is True

    def test_failure_case_logged(self, tmp_path: Path):
        logger = ExperimentLogger(tmp_path / "run")
        logger.log_failure_case("task1", "cfg1", "IndexError", "traceback...")
        events = logger.load_events()
        assert events[0]["type"] == "failure_case"

    def test_multiple_generations(self, tmp_path: Path):
        logger = ExperimentLogger(tmp_path / "run")
        for i in range(5):
            logger.log_generation(i, [f"cfg{i}"], i * 0.1)
        events = logger.load_events()
        assert len(events) == 5
