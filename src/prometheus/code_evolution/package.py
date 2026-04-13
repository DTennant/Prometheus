from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4


@dataclass
class AgentPackage:
    package_id: str = field(default_factory=lambda: uuid4().hex[:8])
    generation: int = 0
    parent_id: str | None = None
    files: dict[str, str] = field(default_factory=dict)

    def to_directory(self, path: Path) -> None:
        for relpath, content in self.files.items():
            target = path / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    @classmethod
    def from_directory(
        cls,
        path: Path,
        *,
        package_id: str = "",
        generation: int = 0,
        parent_id: str | None = None,
    ) -> AgentPackage:
        files: dict[str, str] = {}
        for fpath in sorted(path.rglob("*")):
            if fpath.is_file() and not fpath.name.startswith("."):
                relpath = str(fpath.relative_to(path))
                try:
                    files[relpath] = fpath.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
        pid = package_id or uuid4().hex[:8]
        return cls(
            package_id=pid,
            generation=generation,
            parent_id=parent_id,
            files=files,
        )

    def content_hash(self) -> str:
        items = sorted(self.files.items())
        blob = json.dumps(items, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def to_json(self) -> str:
        return json.dumps(
            {
                "package_id": self.package_id,
                "generation": self.generation,
                "parent_id": self.parent_id,
                "files": self.files,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, data: str) -> AgentPackage:
        parsed = json.loads(data)
        return cls(
            package_id=parsed["package_id"],
            generation=parsed["generation"],
            parent_id=parsed.get("parent_id"),
            files=parsed["files"],
        )
