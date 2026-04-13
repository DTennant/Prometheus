from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from prometheus.code_evolution.package import AgentPackage

log = logging.getLogger(__name__)


class DockerBuilder:
    def __init__(self) -> None:
        import docker  # type: ignore[import-untyped]

        self._client = docker.from_env()
        self._built: dict[str, str] = {}

    def build(self, package: AgentPackage) -> str:
        h = package.content_hash()
        if h in self._built:
            log.debug("Cache hit for %s", package.package_id)
            return self._built[h]

        tag = f"prometheus-agent:{package.package_id}"
        with tempfile.TemporaryDirectory() as tmpdir:
            package.to_directory(Path(tmpdir))
            self._client.images.build(path=tmpdir, tag=tag, rm=True, forcerm=True)
        self._built[h] = tag
        log.info("Built image %s for %s", tag, package.package_id)
        return tag

    def cleanup(self, tag: str) -> None:
        try:
            self._client.images.remove(tag, force=True)
        except Exception:
            pass


class DryRunDockerBuilder:
    def build(self, package: AgentPackage) -> str:
        return f"dry-run:{package.package_id}"

    def cleanup(self, tag: str) -> None:
        pass
