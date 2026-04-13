from __future__ import annotations

import logging
from typing import Any

from prometheus.eval.benchmarks.base import BenchmarkAdapter
from prometheus.eval.task import Task

log = logging.getLogger(__name__)

_REGISTRY: dict[str, type[BenchmarkAdapter]] = {}


def _register_builtin_benchmarks() -> None:
    from prometheus.eval.benchmarks.humaneval_plus import HumanEvalPlusAdapter
    from prometheus.eval.benchmarks.terminal_bench import TerminalBenchAdapter
    from prometheus.eval.benchmarks.swebench import SWEBenchAdapter

    _REGISTRY["humaneval_plus"] = HumanEvalPlusAdapter
    _REGISTRY["terminal_bench"] = TerminalBenchAdapter
    _REGISTRY["swebench"] = SWEBenchAdapter


def get_benchmark(name: str, **kwargs: Any) -> BenchmarkAdapter:
    if not _REGISTRY:
        _register_builtin_benchmarks()

    if name not in _REGISTRY:
        available = ", ".join(_REGISTRY.keys())
        raise ValueError(f"Unknown benchmark: {name}. Available: {available}")

    adapter_cls = _REGISTRY[name]
    return adapter_cls(**kwargs)


def list_benchmarks() -> list[dict[str, Any]]:
    if not _REGISTRY:
        _register_builtin_benchmarks()

    results = []
    for name, cls in _REGISTRY.items():
        adapter = cls()
        results.append(
            {
                "name": name,
                "description": adapter.description,
                "available": adapter.is_available(),
                "requires_docker": adapter.requires_docker,
                "install_hint": adapter.install_hint(),
            }
        )
    return results


def get_benchmark_tasks(name: str, limit: int | None = None, **kwargs: Any) -> list[Task]:
    adapter = get_benchmark(name, **kwargs)
    adapter.check_or_raise()
    return adapter.get_tasks(limit=limit)
