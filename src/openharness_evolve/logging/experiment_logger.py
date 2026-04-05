from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any


class ExperimentLogger:
    def __init__(self, run_dir: Path, config: dict[str, Any] | None = None) -> None:
        self._run_dir = run_dir
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = run_dir / "events.jsonl"
        if config is not None:
            (run_dir / "config.json").write_text(
                json.dumps(config, indent=2, default=str), encoding="utf-8"
            )

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def _append_event(self, event: dict[str, Any]) -> None:
        event["timestamp"] = time.time()
        with self._events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def log_generation(
        self,
        generation: int,
        config_ids: list[str],
        best_score: float,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        self._append_event(
            {
                "type": "generation",
                "generation": generation,
                "config_ids": config_ids,
                "best_score": best_score,
                "metrics": metrics or {},
            }
        )

    def log_eval_result(
        self,
        task_id: str,
        config_id: str,
        passed: bool,
        score: float,
        tokens_used: int,
        wall_time: float,
        error: str | None = None,
    ) -> None:
        self._append_event(
            {
                "type": "eval_result",
                "task_id": task_id,
                "config_id": config_id,
                "passed": passed,
                "score": score,
                "tokens_used": tokens_used,
                "wall_time": wall_time,
                "error": error,
            }
        )

    def log_failure_case(
        self,
        task_id: str,
        config_id: str,
        error_details: str,
        agent_output: str = "",
    ) -> None:
        self._append_event(
            {
                "type": "failure_case",
                "task_id": task_id,
                "config_id": config_id,
                "error_details": error_details,
                "agent_output": agent_output[:2000],
            }
        )

    def save_checkpoint(self, config_data: dict[str, Any], generation: int) -> Path:
        path = self._run_dir / f"checkpoint_gen{generation:04d}.json"
        path.write_text(json.dumps(config_data, indent=2, default=str), encoding="utf-8")
        return path

    def load_checkpoint(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def load_events(self) -> list[dict[str, Any]]:
        if not self._events_path.exists():
            return []
        events = []
        for line in self._events_path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                events.append(json.loads(line))
        return events
