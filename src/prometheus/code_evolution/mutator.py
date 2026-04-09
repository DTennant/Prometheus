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
    if failed:
        lines.append("\nFailed tasks:")
        for r in failed[:10]:
            err = r.error or "incorrect output"
            lines.append(f"  - {r.instance_id}: {err}")
    return "\n".join(lines)


def _build_code_mutation_prompt(
    package: AgentPackage,
    report: EvalReport,
    history: CodeEvolutionHistory,
) -> str:
    return f"""\
You are an AI agent code optimizer. Your job is to modify \
the agent source code to improve its performance on coding \
tasks.

## Current Source Files

{_render_files(package.files)}

## Evaluation Results

{_render_eval_results(report)}

## Evolution History

{history.summary_for_mutation()}

## Your Task

Return a JSON array of file operations to apply. Each \
operation is an object with these fields:

- "op": one of "modify", "create", or "delete"
- "path": relative file path (e.g. "src/agent/agent.py")
- "content": full file content (required for modify/create, \
absent for delete)

Example:
```json
[
  {{"op": "modify", "path": "src/agent/agent.py", \
"content": "...full new content..."}},
  {{"op": "create", "path": "src/agent/utils.py", \
"content": "..."}},
  {{"op": "delete", "path": "src/agent/old.py"}}
]
```

Rules:
- Include full file content — no partial diffs.
- Only modify files that need changes. Don't echo \
unchanged files.
- The agent must still satisfy the CLI contract: \
`python -m agent run --prompt ... --workspace ...`
- Keep pyproject.toml and Dockerfile valid.

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
    """Satisfies LLMClient Protocol for testing."""

    def __init__(self) -> None:
        self._call_count = 0

    async def generate(self, prompt: str) -> str:
        strategy = self._call_count % 4
        self._call_count += 1

        # Extract current files from prompt
        file_blocks: dict[str, str] = {}
        pattern = re.compile(
            r"^### (.+?)\n```\n(.*?)\n```",
            re.MULTILINE | re.DOTALL,
        )
        for m in pattern.finditer(prompt):
            file_blocks[m.group(1)] = m.group(2)

        ops: list[dict[str, Any]] = []

        if strategy == 0:
            # Modify agent.py: add error handling
            agent = file_blocks.get("src/agent/agent.py", "")
            if agent:
                agent = "# Improved error handling\n" + agent
                agent = agent.replace(
                    "for _ in range(max_iterations):",
                    ("for _ in range(max_iterations):\n      try:"),
                )
                ops.append(
                    {
                        "op": "modify",
                        "path": "src/agent/agent.py",
                        "content": agent,
                    }
                )

        elif strategy == 1:
            # Modify tools.py: add docker_run tool
            tools = file_blocks.get("src/agent/tools.py", "")
            if tools:
                docker_schema = (
                    "    {\n"
                    '        "type": "function",\n'
                    '        "function": {\n'
                    '            "name": "docker_run",\n'
                    '            "description": '
                    '"Run a command in a Docker '
                    'container.",\n'
                    '            "parameters": {\n'
                    '                "type": "object",\n'
                    '                "properties": {\n'
                    '                    "image": '
                    '{"type": "string"},\n'
                    '                    "command": '
                    '{"type": "string"}\n'
                    "                },\n"
                    '                "required": '
                    '["image", "command"]\n'
                    "            }\n"
                    "        }\n"
                    "    },\n"
                )
                tools = tools.replace(
                    "TOOL_SCHEMAS: list[dict[str, Any]] = [\n",
                    "TOOL_SCHEMAS: list[dict[str, Any]] = [\n" + docker_schema,
                )
                docker_impl = (
                    "\n        if name == "
                    '"docker_run":\n'
                    "            result = "
                    "subprocess.run(\n"
                    '                ["docker", "run"'
                    ', "--rm",\n'
                    '                 args["image"]'
                    ', "sh", "-c",\n'
                    '                 args["command"'
                    "]],\n"
                    "                capture_output"
                    "=True, text=True,\n"
                    "                timeout=60,\n"
                    "            )\n"
                    "            return result.stdout"
                    ' or "(no output)"\n'
                )
                tools = tools.replace(
                    '        return f"Error: unknown tool: {name}"',
                    docker_impl + '\n        return f"Error: unknown tool: {name}"',
                )
                ops.append(
                    {
                        "op": "modify",
                        "path": "src/agent/tools.py",
                        "content": tools,
                    }
                )

        elif strategy == 2:
            # Modify cli.py: add --temperature
            cli = file_blocks.get("src/agent/cli.py", "")
            if cli:
                cli = cli.replace(
                    '    max_iterations: int = typer.Option(30, "--max-iterations"),',
                    "    max_iterations: int = "
                    'typer.Option(30, "--max-'
                    'iterations"),\n'
                    "    temperature: float = "
                    "typer.Option(0.7, "
                    '"--temperature"),',
                )
                cli = cli.replace(
                    "            max_iterations=max_iterations,",
                    "            max_iterations="
                    "max_iterations,\n"
                    "            temperature="
                    "temperature,",
                )
                ops.append(
                    {
                        "op": "modify",
                        "path": "src/agent/cli.py",
                        "content": cli,
                    }
                )

        else:
            # Modify agent.py: add retry logic
            agent = file_blocks.get("src/agent/agent.py", "")
            if agent:
                agent = agent.replace(
                    '        if choice.finish_reason != "tool_calls":\n            break',
                    "        if choice.finish_reason"
                    ' != "tool_calls":\n'
                    "            if not output.strip("
                    "):\n"
                    "                # Retry once if"
                    " empty\n"
                    "                messages.append("
                    '{"role": "user",\n'
                    '                    "content": '
                    '"Please try again."})\n'
                    "                continue\n"
                    "            break",
                )
                ops.append(
                    {
                        "op": "modify",
                        "path": "src/agent/agent.py",
                        "content": agent,
                    }
                )

        if not ops:
            # Fallback: trivial modify
            ops.append(
                {
                    "op": "modify",
                    "path": "src/agent/agent.py",
                    "content": "# mutated\n",
                }
            )

        return json.dumps(ops)
