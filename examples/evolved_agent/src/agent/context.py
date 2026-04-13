from __future__ import annotations

from typing import Any


def _get_field(msg: Any, field: str, default: Any = "") -> Any:
    if isinstance(msg, dict):
        return msg.get(field, default)
    return getattr(msg, field, default)


def estimate_tokens(messages: list[Any]) -> int:
    total = 0
    for msg in messages:
        content = _get_field(msg, "content", "")
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for item in content:
                total += len(str(item)) // 4
        else:
            total += len(str(content or "")) // 4
    return total


def should_summarize(
    messages: list[Any], max_tokens: int = 80000
) -> bool:
    return estimate_tokens(messages) > max_tokens


def compact_messages(
    messages: list[Any], keep_recent: int = 10
) -> list[Any]:
    if len(messages) <= keep_recent + 1:
        return messages

    system = (
        messages[0]
        if _get_field(messages[0], "role") == "system"
        else None
    )
    recent = messages[-keep_recent:]
    old = messages[1:-keep_recent] if system else messages[:-keep_recent]

    summary_parts = []
    for msg in old:
        role = _get_field(msg, "role", "unknown")
        content = _get_field(msg, "content", "")
        if isinstance(content, str) and content.strip():
            summary_parts.append(f"[{role}]: {content[:200]}")

    summary_text = (
        "Previous conversation summary:\n"
        + "\n".join(summary_parts[-20:])
    )
    summary_msg = {"role": "user", "content": summary_text}

    result: list[dict[str, Any]] = []
    if system:
        result.append(system)
    result.append(summary_msg)
    result.extend(recent)
    return result
