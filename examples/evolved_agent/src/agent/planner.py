from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    description: str
    tools_needed: list[str] = field(default_factory=list)
    completed: bool = False


class TaskPlanner:
    def __init__(self) -> None:
        self.steps: list[Step] = []

    def decompose(self, prompt: str) -> list[Step]:
        self.steps = []
        lower = prompt.lower()

        self.steps.append(
            Step(
                description=(
                    "Understand the codebase: read relevant files "
                    "and explore the directory structure"
                ),
                tools_needed=[
                    "list_directory",
                    "read_file",
                    "search_files",
                ],
            )
        )

        if _is_bug_fix(lower):
            self.steps.append(
                Step(
                    description=(
                        "Identify the root cause by reading error "
                        "messages and tracing the code path"
                    ),
                    tools_needed=["read_file", "search_files"],
                )
            )
            self.steps.append(
                Step(
                    description="Implement the fix",
                    tools_needed=["edit_file"],
                )
            )
        elif _is_creation(lower):
            self.steps.append(
                Step(
                    description=("Plan the implementation: identify files to create or modify"),
                    tools_needed=["list_directory", "search_files"],
                )
            )
            self.steps.append(
                Step(
                    description=("Write the code — create new files or modify existing ones"),
                    tools_needed=[
                        "write_file",
                        "edit_file",
                    ],
                )
            )
        elif _is_refactor(lower):
            self.steps.append(
                Step(
                    description=("Find all references to the target across the codebase"),
                    tools_needed=["search_files"],
                )
            )
            self.steps.append(
                Step(
                    description=("Apply changes across all affected files"),
                    tools_needed=["edit_file"],
                )
            )
        else:
            self.steps.append(
                Step(
                    description="Analyze what needs to be done",
                    tools_needed=[
                        "read_file",
                        "search_files",
                    ],
                )
            )
            self.steps.append(
                Step(
                    description="Implement the solution",
                    tools_needed=[
                        "write_file",
                        "edit_file",
                        "execute_command",
                    ],
                )
            )

        self.steps.append(
            Step(
                description="Run tests to verify correctness",
                tools_needed=["run_tests"],
            )
        )

        self.steps.append(
            Step(
                description=("Review changes with git diff and confirm the task is complete"),
                tools_needed=["git_diff"],
            )
        )

        return self.steps

    def mark_complete(self, step_index: int) -> None:
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].completed = True

    def format_plan(self) -> str:
        if not self.steps:
            return "No plan created yet."
        lines = ["Plan:"]
        for i, step in enumerate(self.steps, 1):
            status = "[done]" if step.completed else "[    ]"
            tools = ", ".join(step.tools_needed)
            lines.append(f"  {status} {i}. {step.description}")
            if tools:
                lines.append(f"         Tools: {tools}")
        done = sum(1 for s in self.steps if s.completed)
        lines.append(f"\nProgress: {done}/{len(self.steps)} steps complete")
        return "\n".join(lines)

    def next_incomplete(self) -> int | None:
        for i, step in enumerate(self.steps):
            if not step.completed:
                return i
        return None


def _is_bug_fix(text: str) -> bool:
    keywords = ["fix", "bug", "error", "fail", "broken", "crash"]
    return any(kw in text for kw in keywords)


def _is_creation(text: str) -> bool:
    keywords = [
        "write",
        "create",
        "add",
        "implement",
        "build",
        "make",
    ]
    return any(kw in text for kw in keywords)


def _is_refactor(text: str) -> bool:
    keywords = ["refactor", "rename", "move", "reorganize"]
    return any(kw in text for kw in keywords)
