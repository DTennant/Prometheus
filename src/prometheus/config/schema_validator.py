from __future__ import annotations

from prometheus.config.harness_config import HarnessConfig

ALLOWED_BASE_TOOLS = {"read_file", "write_file", "execute", "list_directory"}
MAX_SYSTEM_PROMPT_LENGTH = 10000
MAX_FEW_SHOT_EXAMPLES = 20
MAX_WORKFLOW_PHASES = 8
MAX_PHASE_PROMPT_LENGTH = 5000


def validate_harness_config(config: HarnessConfig) -> list[str]:
    errors: list[str] = []

    if not config.system_prompt.strip():
        errors.append("system_prompt must not be empty")
    if len(config.system_prompt) > MAX_SYSTEM_PROMPT_LENGTH:
        errors.append(f"system_prompt exceeds {MAX_SYSTEM_PROMPT_LENGTH} characters")

    for ct in config.custom_tools:
        for sub in ct.sub_tools:
            if sub not in ALLOWED_BASE_TOOLS:
                errors.append(f"Custom tool '{ct.name}' references unknown base tool '{sub}'")
    tool_names = [ct.name for ct in config.custom_tools]
    if len(tool_names) != len(set(tool_names)):
        errors.append("Duplicate custom tool names found")

    if len(config.few_shot_examples) > MAX_FEW_SHOT_EXAMPLES:
        errors.append(f"Too many few-shot examples (max {MAX_FEW_SHOT_EXAMPLES})")

    phases = config.workflow.phases
    if len(phases) > MAX_WORKFLOW_PHASES:
        errors.append(f"Too many workflow phases (max {MAX_WORKFLOW_PHASES})")

    has_task_ref = False
    phase_names: list[str] = []
    for phase in phases:
        if not phase.name.strip():
            errors.append("Workflow phase name must not be empty")
        phase_names.append(phase.name)
        if len(phase.prompt_template) > MAX_PHASE_PROMPT_LENGTH:
            errors.append(
                f"Phase '{phase.name}' prompt_template exceeds {MAX_PHASE_PROMPT_LENGTH} characters"
            )
        if "$task" in phase.prompt_template or "${task}" in phase.prompt_template:
            has_task_ref = True

    if phases and not has_task_ref:
        errors.append("At least one workflow phase must reference $task in its prompt_template")

    if len(phase_names) != len(set(phase_names)):
        errors.append("Duplicate workflow phase names found")

    return errors
