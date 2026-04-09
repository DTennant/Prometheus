from __future__ import annotations

from typing import Any


class ContextManager:
    def __init__(self, token_budget: int = 80000, keep_recent: int = 10) -> None:
        self.token_budget = token_budget
        self.keep_recent = keep_recent
        self.messages: list[dict[str, Any]] = []
        self.total_tokens_used: int = 0

    def add_message(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    def add_messages(self, messages: list[dict[str, Any]]) -> None:
        self.messages.extend(messages)

    def get_messages(self) -> list[dict[str, Any]]:
        return self.messages

    def record_tokens(self, count: int) -> None:
        self.total_tokens_used += count

    def should_compact(self) -> bool:
        estimated = estimate_tokens(self.messages)
        return estimated > int(self.token_budget * 0.7)

    def compact(self) -> None:
        if len(self.messages) <= self.keep_recent + 1:
            return

        system = None
        if self.messages and self.messages[0].get("role") == "system":
            system = self.messages[0]

        recent = self.messages[-self.keep_recent :]
        start = 1 if system else 0
        end = len(self.messages) - self.keep_recent
        old = self.messages[start:end]

        if not old:
            return

        summary_text = _build_summary(old)
        summary_msg: dict[str, Any] = {
            "role": "user",
            "content": summary_text,
        }

        result: list[dict[str, Any]] = []
        if system:
            result.append(system)
        result.append(summary_msg)
        result.extend(recent)
        self.messages = result


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if isinstance(content, str):
            # Tool results are denser (code/logs): ~3 chars/token
            # vs natural language: ~4 chars/token
            chars_per_token = 3 if role == "tool" else 4
            total += len(content) // chars_per_token
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    total += len(str(item)) // 4

        tool_calls = msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            for tc in tool_calls:
                fn = getattr(tc, "function", None)
                if fn is not None:
                    args_str = getattr(fn, "arguments", "")
                    total += len(str(args_str)) // 4
                elif isinstance(tc, dict):
                    fn_dict = tc.get("function", {})
                    total += len(str(fn_dict)) // 4

    return total


def _build_summary(
    messages: list[dict[str, Any]],
) -> str:
    key_facts: list[str] = []
    tool_actions: list[str] = []
    errors: list[str] = []

    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if not isinstance(content, str) or not content.strip():
            continue

        snippet = content[:300]

        if role == "tool":
            if content.lower().startswith("error"):
                errors.append(snippet)
            else:
                tool_actions.append(snippet)
        elif role == "assistant":
            key_facts.append(snippet)
        elif role == "user":
            key_facts.append(f"[user]: {snippet}")

    parts = ["=== Conversation Summary ==="]

    if key_facts:
        parts.append("\nKey context:")
        for fact in key_facts[-10:]:
            parts.append(f"  - {fact}")

    if tool_actions:
        parts.append(f"\nTool actions taken: {len(tool_actions)}")
        for action in tool_actions[-5:]:
            parts.append(f"  - {action[:150]}")

    if errors:
        parts.append(f"\nErrors encountered: {len(errors)}")
        for err in errors[-5:]:
            parts.append(f"  - {err[:150]}")

    parts.append("=== End Summary ===")
    return "\n".join(parts)
