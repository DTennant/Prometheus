from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunSummary:
    run_dir: Path
    config: dict[str, Any] = field(default_factory=dict)
    generations: list[dict[str, Any]] = field(default_factory=list)
    best_score: float = 0.0
    total_generations: int = 0


def load_run(run_dir: Path) -> RunSummary:
    summary = RunSummary(run_dir=run_dir)

    config_path = run_dir / "config.json"
    if config_path.exists():
        summary.config = json.loads(config_path.read_text(encoding="utf-8"))

    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            event = json.loads(line)
            if event.get("type") == "generation":
                summary.generations.append(event)

    if summary.generations:
        summary.total_generations = len(summary.generations)
        summary.best_score = max(g.get("best_score", 0.0) for g in summary.generations)

    return summary


@dataclass
class ComparisonRow:
    run_dir: str
    generations: int
    best_score: float
    model: str


def compare_runs(run_dirs: list[Path]) -> list[ComparisonRow]:
    rows: list[ComparisonRow] = []
    for run_dir in run_dirs:
        summary = load_run(run_dir)
        model = summary.config.get("model", {})
        if isinstance(model, dict):
            model_name = model.get("name", "unknown")
        else:
            model_name = str(model)
        rows.append(
            ComparisonRow(
                run_dir=str(run_dir.name),
                generations=summary.total_generations,
                best_score=summary.best_score,
                model=model_name,
            )
        )
    rows.sort(key=lambda r: r.best_score, reverse=True)
    return rows


def format_comparison(rows: list[ComparisonRow]) -> str:
    if not rows:
        return "No runs to compare."
    lines = [
        f"{'Run':<30} {'Model':<30} {'Gens':>5} {'Best Score':>10}",
        "-" * 77,
    ]
    for row in rows:
        lines.append(
            f"{row.run_dir:<30} {row.model:<30} {row.generations:>5} {row.best_score:>10.4f}"
        )
    return "\n".join(lines)
