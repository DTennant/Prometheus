from __future__ import annotations

from openharness_evolve.config.harness_config import (
    HarnessConfig,
    HarnessParameters,
    WorkflowPrompts,
)


_SEED_SYSTEM_PROMPT = (
    "You are a coding assistant. You can read files, write files, "
    "and execute shell commands. Solve the given task."
)

_HUMAN_BASELINE_SYSTEM_PROMPT = """\
You are an AI coding assistant. You help users with software engineering tasks: \
solving bugs, adding features, refactoring, explaining code, and more.

# Using your tools
- Read files before modifying them.
- Use dedicated tools instead of shell commands when available.
- You can call multiple tools in a single response for efficiency.

# Doing tasks
- Be concise. Lead with the answer, not the reasoning.
- Do not add features beyond what was asked.
- If an approach fails, diagnose why before switching tactics.
- Be careful not to introduce security vulnerabilities.

# Tone
- Be concise. Skip filler and preamble.
- Focus on decisions needing user input, status updates, and errors."""


def create_seed_harness() -> HarnessConfig:
    return HarnessConfig(
        system_prompt=_SEED_SYSTEM_PROMPT,
        tool_descriptions=[],
        workflow_prompts=WorkflowPrompts(),
        parameters=HarnessParameters(max_iterations=30, timeout_per_task=600),
        custom_tools=[],
        few_shot_examples=[],
        generation=0,
        config_id="seed",
    )


def create_human_baseline_harness() -> HarnessConfig:
    return HarnessConfig(
        system_prompt=_HUMAN_BASELINE_SYSTEM_PROMPT,
        tool_descriptions=[],
        workflow_prompts=WorkflowPrompts(),
        parameters=HarnessParameters(max_iterations=50, timeout_per_task=600),
        custom_tools=[],
        few_shot_examples=[],
        generation=0,
        config_id="human_baseline",
    )
