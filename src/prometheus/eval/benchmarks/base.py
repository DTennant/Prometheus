from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from prometheus.eval.task import Task

log = logging.getLogger(__name__)


class BenchmarkAdapter(ABC):
    name: str
    description: str
    requires_docker: bool = False
    pip_package: str | None = None

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_tasks(self, limit: int | None = None) -> list[Task]: ...

    def install_hint(self) -> str:
        if self.pip_package:
            return f"pip install {self.pip_package}"
        return "See documentation for installation instructions."

    def check_or_raise(self) -> None:
        if not self.is_available():
            raise RuntimeError(
                f"Benchmark '{self.name}' is not available. Install with: {self.install_hint()}"
            )
