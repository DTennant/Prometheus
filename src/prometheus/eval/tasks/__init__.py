from __future__ import annotations

import logging
from typing import Any

from prometheus.eval.tasks.code_generation import get_code_generation_tasks
from prometheus.eval.tasks.file_manipulation import get_file_manipulation_tasks
from prometheus.eval.tasks.debugging import get_debugging_tasks
from prometheus.eval.tasks.reasoning import get_reasoning_tasks

log = logging.getLogger(__name__)


def get_all_tasks():
    return (
        get_code_generation_tasks()
        + get_file_manipulation_tasks()
        + get_debugging_tasks()
        + get_reasoning_tasks()
    )


def get_task_suite(name: str = "default", limit: int | None = None):
    builtin_suites: dict[str, Any] = {
        "default": get_all_tasks,
        "code_generation": get_code_generation_tasks,
        "file_manipulation": get_file_manipulation_tasks,
        "debugging": get_debugging_tasks,
        "reasoning": get_reasoning_tasks,
    }

    if name in builtin_suites:
        tasks = builtin_suites[name]()
        if limit:
            tasks = tasks[:limit]
        return tasks

    try:
        from prometheus.eval.benchmarks import get_benchmark_tasks

        return get_benchmark_tasks(name, limit=limit)
    except (ValueError, RuntimeError) as exc:
        all_names = list(builtin_suites.keys())
        try:
            from prometheus.eval.benchmarks import list_benchmarks

            all_names.extend(b["name"] for b in list_benchmarks())
        except Exception:
            pass
        raise ValueError(f"Unknown task suite: {name}. Available: {', '.join(all_names)}") from exc
