_SEED_CONTEXT_PY = """\
from __future__ import annotations

from typing import Any


class ContextManager:
    def __init__(self, token_budget: int = 100000) -> None:
        self._messages: list[Any] = []
        self._token_budget = token_budget
        self._file_cache: dict[str, str] = {}
        self._total_tokens = 0

    def set_system(self, content: str) -> None:
        if self._messages and _get(self._messages[0], "role") == "system":
            self._messages[0] = {"role": "system", "content": content}
        else:
            self._messages.insert(0, {"role": "system", "content": content})

    def add_message(self, msg: Any) -> None:
        self._messages.append(msg)

    def add_tool_result(self, tool_call_id: str, result: str) -> None:
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        })

    def inject_phase_hint(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def cache_file(self, path: str, content: str) -> None:
        self._file_cache[path] = content

    def get_messages(self) -> list[Any]:
        return list(self._messages)

    def should_compact(self) -> bool:
        return _estimate_tokens(self._messages) > int(
            self._token_budget * 0.7
        )

    def compact(self, keep_recent: int = 15) -> None:
        if len(self._messages) <= keep_recent + 1:
            return

        system = None
        if self._messages and _get(self._messages[0], "role") == "system":
            system = self._messages[0]

        recent = self._messages[-keep_recent:]
        old = (
            self._messages[1:-keep_recent]
            if system
            else self._messages[:-keep_recent]
        )

        summary_parts: list[str] = []
        for msg in old:
            role = _get(msg, "role", "unknown")
            content = _get(msg, "content", "")
            if isinstance(content, str) and content.strip():
                summary_parts.append(f"[{role}]: {content[:150]}")

        summary_text = "Previous conversation summary:\\n"
        summary_text += "\\n".join(summary_parts[-25:])

        if self._file_cache:
            summary_text += "\\n\\nCached files you have read:\\n"
            for path in sorted(self._file_cache)[:20]:
                lines = self._file_cache[path].count("\\n") + 1
                summary_text += f"  {path} ({lines} lines)\\n"

        summary_msg = {"role": "user", "content": summary_text}

        result: list[Any] = []
        if system:
            result.append(system)
        result.append(summary_msg)
        result.extend(recent)
        self._messages = result


def _get(msg: Any, field: str, default: Any = "") -> Any:
    if isinstance(msg, dict):
        return msg.get(field, default)
    return getattr(msg, field, default)


def _estimate_tokens(messages: list[Any]) -> int:
    total = 0
    for msg in messages:
        content = _get(msg, "content", "")
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for item in content:
                total += len(str(item)) // 4
        else:
            total += len(str(content or "")) // 4
    return total
"""
