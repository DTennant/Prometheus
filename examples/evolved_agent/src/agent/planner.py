from __future__ import annotations


def create_plan(prompt: str) -> list[str]:
    steps = []
    steps.append("Read relevant files to understand the codebase")
    if any(kw in prompt.lower() for kw in ["fix", "bug", "error", "fail"]):
        steps.append("Identify the root cause of the issue")
        steps.append("Implement the fix")
        steps.append("Run tests to verify the fix")
    elif any(kw in prompt.lower() for kw in ["write", "create", "add", "implement"]):
        steps.append("Plan the implementation approach")
        steps.append("Write the code")
        steps.append("Run tests to verify correctness")
    elif any(kw in prompt.lower() for kw in ["refactor", "rename", "move", "change"]):
        steps.append("Find all references to the target")
        steps.append("Make the changes across all files")
        steps.append("Run tests to verify nothing broke")
    else:
        steps.append("Analyze what needs to be done")
        steps.append("Implement the solution")
        steps.append("Verify the result")
    return steps


def format_plan(steps: list[str]) -> str:
    lines = ["Plan:"]
    for i, step in enumerate(steps, 1):
        lines.append(f"  {i}. {step}")
    return "\n".join(lines)
