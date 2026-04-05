from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from openharness_evolve.eval.task import TaskInstance


class TaskSandbox:
    def __init__(self, workspace: Path | None = None) -> None:
        self._provided_workspace = workspace
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._workspace: Path | None = None

    @property
    def workspace(self) -> Path:
        if self._workspace is None:
            raise RuntimeError("Sandbox not entered")
        return self._workspace

    def setup(self, instance: TaskInstance) -> Path:
        if self._provided_workspace:
            self._workspace = self._provided_workspace
            self._workspace.mkdir(parents=True, exist_ok=True)
        else:
            self._tmpdir = tempfile.TemporaryDirectory()
            self._workspace = Path(self._tmpdir.name)

        for filename, content in instance.setup_files.items():
            filepath = self._workspace / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")

        return self._workspace

    def run_command(self, cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=str(self._workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def cleanup(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
        self._workspace = None

    def __enter__(self) -> TaskSandbox:
        return self

    def __exit__(self, *args: Any) -> None:
        self.cleanup()
