from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from prometheus.code_evolution.package import AgentPackage
from prometheus.eval.scorer import EvalReport
from prometheus.evolution.mutator import LLMClient

if TYPE_CHECKING:
    from prometheus.code_evolution.history import CodeEvolutionHistory

log = logging.getLogger(__name__)

MAX_MUTATION_RETRIES = 3


ALWAYS_FULL_FILES = {
    "src/agent/agent.py",
    "src/agent/prompts.py",
}
MAX_SOURCE_TOKENS = 12000


def _summarize_files(
    files: dict[str, str],
) -> dict[str, str]:
    summaries: dict[str, str] = {}
    for path in sorted(files):
        content = files[path]
        lines = content.count("\n") + 1
        summary = f"{path} ({lines} lines, {len(content)} bytes)"
        summaries[path] = summary
    return summaries


def _select_files_for_context(
    package: AgentPackage,
    report: EvalReport,
) -> set[str]:
    selected = set(ALWAYS_FULL_FILES)
    failed = [r for r in report.results if not r.passed]
    if not failed:
        return selected

    error_text = " ".join((r.error or "") + " " + (r.raw_output or "") for r in failed[:10])
    error_lower = error_text.lower()

    if any(
        kw in error_lower
        for kw in [
            "str_replace",
            "edit",
            "old_text",
            "tool",
            "search",
            "grep",
        ]
    ):
        selected.add("src/agent/tools.py")
    if any(kw in error_lower for kw in ["context", "token", "truncat", "compact"]):
        selected.add("src/agent/context.py")
    if any(kw in error_lower for kw in ["diff", "patch", "git"]):
        selected.add("src/agent/diff.py")

    if len(selected) < 3:
        selected.add("src/agent/tools.py")

    return {s for s in selected if s in package.files}


def _render_context(
    package: AgentPackage,
    report: EvalReport,
) -> str:
    summaries = _summarize_files(package.files)
    full_files = _select_files_for_context(package, report)

    parts: list[str] = ["File overview:"]
    for path, summary in summaries.items():
        marker = " [FULL BELOW]" if path in full_files else ""
        parts.append(f"  {summary}{marker}")

    total_tokens = 0
    for path in sorted(full_files):
        content = package.files[path]
        file_tokens = len(content) // 4
        if total_tokens + file_tokens > MAX_SOURCE_TOKENS:
            break
        total_tokens += file_tokens
        parts.append(f"\n### {path}\n```\n{content}\n```")

    return "\n".join(parts)


def _render_files(files: dict[str, str]) -> str:
    parts: list[str] = []
    for path in sorted(files):
        parts.append(f"### {path}\n```\n{files[path]}\n```")
    return "\n\n".join(parts)


def _render_eval_results(report: EvalReport) -> str:
    passed = [r for r in report.results if r.passed]
    failed = [r for r in report.results if not r.passed]
    lines = [
        f"Accuracy: {report.accuracy:.1%}",
        f"Tasks passed: {len(passed)}/{len(report.results)}",
        f"Total tokens: {report.total_tokens}",
    ]
    if passed:
        lines.append("\nPassed tasks:")
        for r in passed[:5]:
            lines.append(f"  - {r.instance_id} (tokens: {r.tokens_used})")
    if failed:
        lines.append("\nFailed tasks (ANALYZE THESE):")
        for r in failed[:10]:
            err = r.error or "incorrect output"
            lines.append(f"\n  ### {r.instance_id}")
            lines.append(f"  Error: {err[:500]}")
            if r.raw_output:
                snippet = r.raw_output[:300].replace("\n", "\n    ")
                lines.append(f"  Agent output: {snippet}")
    return "\n".join(lines)


def _build_code_mutation_prompt(
    package: AgentPackage,
    report: EvalReport,
    history: CodeEvolutionHistory,
) -> str:
    return f"""\
You are evolving an AI coding agent. This agent will be \
run by YOU — the same model that is reading this prompt. \
Your goal is to modify the source code so that when YOU \
execute this agent, YOU perform better on the eval tasks.

Think about what went wrong: look at the failed tasks \
below, see the errors and your previous output, and \
figure out what YOU would need — better prompts, better \
tools, better error handling — to get those tasks right.

## Source Files

{_render_context(package, report)}

## Evaluation Results

{_render_eval_results(report)}

## Evolution History

{history.summary_for_mutation()}

## Analysis Instructions

Before generating changes, analyze the failures:

1. For each failed task, identify the ROOT CAUSE. \
Was it a wrong tool call? Bad output format? Missing \
capability? Timeout?
2. Look at the agent output for failed tasks — what \
did the agent actually produce vs what was expected?
3. Consider: would a prompt change fix this, or does \
the agent need a new tool or different logic?
4. Prioritize fixes that address the MOST failures.

## Output Format

Return a JSON array of file operations:

- "op": "modify", "create", or "delete"
- "path": relative file path (e.g. "src/agent/agent.py")
- "content": full file content (for modify/create)

```json
[
  {{"op": "modify", "path": "src/agent/agent.py", \
"content": "...full new content..."}}
]
```

Rules:
- Include full file content — no partial diffs.
- Only modify files that need changes.
- The agent must satisfy: \
`python -m agent run --prompt ... --workspace ...`
- Keep pyproject.toml and Dockerfile valid.
- Write valid Python only — the code will be executed.

Output ONLY the JSON array. No explanation."""


def _parse_ops(raw: str) -> list[dict[str, Any]]:
    """Parse file operations JSON from LLM response."""
    cleaned = raw.strip()
    # Strip markdown fences if present
    fence_match = re.search(
        r"```(?:json)?\s*\n(.*?)```",
        cleaned,
        re.DOTALL,
    )
    if fence_match:
        cleaned = fence_match.group(1).strip()
    ops: list[dict[str, Any]] = json.loads(cleaned)
    if not isinstance(ops, list):
        raise ValueError("Expected a JSON array of operations")
    return ops


def _validate_and_apply(
    ops: list[dict[str, Any]],
    files: dict[str, str],
) -> dict[str, str]:
    """Validate operations and apply to a copy of files."""
    result = dict(files)
    valid_ops = {"modify", "create", "delete"}
    for op in ops:
        op_type = op.get("op")
        path = op.get("path", "")
        if op_type not in valid_ops:
            raise ValueError(f"Invalid op: {op_type}")
        if not path or path.startswith("..") or path.startswith("/"):
            raise ValueError(f"Invalid path: {path!r}")
        if op_type in ("modify", "create"):
            if "content" not in op:
                raise ValueError(f"Missing content for {op_type} on {path}")
            result[path] = op["content"]
        elif op_type == "delete":
            result.pop(path, None)
    return result


async def mutate_package(
    client: LLMClient,
    package: AgentPackage,
    report: EvalReport,
    history: CodeEvolutionHistory,
) -> AgentPackage:
    """Mutate an agent package using LLM-guided code changes."""
    prompt = _build_code_mutation_prompt(package, report, history)

    for attempt in range(MAX_MUTATION_RETRIES):
        try:
            raw = await client.generate(prompt)
            ops = _parse_ops(raw)
            new_files = _validate_and_apply(ops, package.files)
            return AgentPackage(
                package_id=uuid4().hex[:8],
                generation=package.generation + 1,
                parent_id=package.package_id,
                files=new_files,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            log.warning(
                "Code mutation failed (attempt %d): %s",
                attempt + 1,
                exc,
            )
            continue

    raise RuntimeError("Code mutation failed after 3 attempts")


class DryRunCodeMutator:
    def __init__(self) -> None:
        self._call_count = 0

    async def generate(self, prompt: str) -> str:
        strategy = self._call_count % 4
        self._call_count += 1

        file_blocks: dict[str, str] = {}
        pattern = re.compile(
            r"^### (.+?)\n```\n(.*?)\n```",
            re.MULTILINE | re.DOTALL,
        )
        for m in pattern.finditer(prompt):
            file_blocks[m.group(1)] = m.group(2)

        ops: list[dict[str, Any]] = []

        prompts = file_blocks.get("src/agent/prompts.py", "")
        agent = file_blocks.get("src/agent/agent.py", "")

        if strategy == 0 and prompts:
            prompts += '\n\nEXTRA_RULES = "Always verify your changes by running tests."\n'
            ops.append(
                {
                    "op": "modify",
                    "path": "src/agent/prompts.py",
                    "content": prompts,
                }
            )
        elif strategy == 1 and agent:
            agent = agent.replace(
                "max_tokens=8192",
                "max_tokens=16384",
            )
            ops.append(
                {
                    "op": "modify",
                    "path": "src/agent/agent.py",
                    "content": agent,
                }
            )
        elif strategy == 2 and prompts:
            prompts = prompts.replace(
                "str_replace for precise edits",
                "str_replace for precise edits. Read test files to understand expected behavior",
            )
            ops.append(
                {
                    "op": "modify",
                    "path": "src/agent/prompts.py",
                    "content": prompts,
                }
            )
        elif strategy == 3 and agent:
            agent = agent.replace(
                '5: "locate"',
                '3: "locate"',
            )
            agent = agent.replace(
                '15: "edit"',
                '8: "edit"',
            )
            ops.append(
                {
                    "op": "modify",
                    "path": "src/agent/agent.py",
                    "content": agent,
                }
            )

        if not ops:
            ops.append(
                {
                    "op": "modify",
                    "path": "src/agent/prompts.py",
                    "content": prompts or "MUTATED = True\n",
                }
            )

        return json.dumps(ops)
