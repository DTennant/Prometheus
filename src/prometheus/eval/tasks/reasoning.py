from __future__ import annotations

import subprocess
from pathlib import Path

from prometheus.eval.task import Task, TaskInstance, TaskResult


class BuildDependencyOrderTask(Task):
    name = "build_dependency_order"
    category = "reasoning"

    def get_instances(self) -> list[TaskInstance]:
        deps_json = """
{
  "frontend": ["api", "shared"],
  "api": ["database", "shared", "auth"],
  "auth": ["database", "shared"],
  "database": ["shared"],
  "shared": [],
  "cli": ["api", "shared"]
}
"""
        test_code = """import json, sys
sys.path.insert(0, ".")
from build_order import compute_build_order

with open("deps.json") as f:
    deps = json.load(f)

order = compute_build_order(deps)
assert isinstance(order, list)
assert set(order) == set(deps.keys()), f"Missing or extra packages: {order}"

# Verify ordering: each package appears after all its dependencies
for i, pkg in enumerate(order):
    for dep in deps[pkg]:
        dep_idx = order.index(dep)
        assert dep_idx < i, f"{dep} must come before {pkg}"

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="reasoning_build_order",
                prompt=(
                    "Read 'deps.json' which maps package names to their dependencies. "
                    "Write a Python module 'build_order.py' with a function "
                    "`compute_build_order(deps: dict) -> list[str]` that returns a valid "
                    "build order (topological sort). Each package must appear after all "
                    "its dependencies. Raise ValueError if there's a cycle."
                ),
                expected_output=test_code,
                setup_files={"deps.json": deps_json, "test.py": test_code},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_reasoning_test(instance, workspace, agent_output)


class StateMachineTask(Task):
    name = "state_machine"
    category = "reasoning"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """import sys
sys.path.insert(0, ".")
from state_machine import OrderStateMachine

sm = OrderStateMachine()
assert sm.state == "pending"

assert sm.transition("confirm") == True
assert sm.state == "confirmed"

assert sm.transition("ship") == True
assert sm.state == "shipped"

assert sm.transition("deliver") == True
assert sm.state == "delivered"

# Can't go backward
assert sm.transition("confirm") == False
assert sm.state == "delivered"

# Test cancel from pending
sm2 = OrderStateMachine()
assert sm2.transition("cancel") == True
assert sm2.state == "cancelled"

# Can't do anything from cancelled
assert sm2.transition("confirm") == False
assert sm2.state == "cancelled"

# Test cancel from confirmed
sm3 = OrderStateMachine()
sm3.transition("confirm")
assert sm3.transition("cancel") == True
assert sm3.state == "cancelled"

# Can't cancel after shipping
sm4 = OrderStateMachine()
sm4.transition("confirm")
sm4.transition("ship")
assert sm4.transition("cancel") == False
assert sm4.state == "shipped"

# Test history
sm5 = OrderStateMachine()
sm5.transition("confirm")
sm5.transition("ship")
history = sm5.get_history()
assert len(history) == 3
assert history[0] == "pending"
assert history[1] == "confirmed"
assert history[2] == "shipped"

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="reasoning_state_machine",
                prompt=(
                    "Implement an `OrderStateMachine` class in 'state_machine.py' with:\n"
                    "- States: pending, confirmed, shipped, delivered, cancelled\n"
                    "- Transitions: pending→confirmed (confirm), confirmed→shipped (ship), "
                    "shipped→delivered (deliver), pending→cancelled (cancel), "
                    "confirmed→cancelled (cancel)\n"
                    "- `__init__()` starts in 'pending'\n"
                    "- `transition(action: str) -> bool` — returns True if transition valid, "
                    "False if invalid (state unchanged)\n"
                    "- `state` property returning current state\n"
                    "- `get_history() -> list[str]` returning all states visited in order"
                ),
                expected_output=test_code,
                setup_files={"test.py": test_code},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_reasoning_test(instance, workspace, agent_output)


def _run_reasoning_test(instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
    test_path = workspace / "test.py"
    if not test_path.exists():
        return TaskResult(instance.instance_id, False, 0.0, 0, 0.0, agent_output, "test.py missing")
    try:
        result = subprocess.run(
            ["python", str(test_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=15,
        )
        passed = result.returncode == 0 and "PASS" in result.stdout
        error = result.stderr.strip() if not passed else None
        if not passed and not error:
            error = f"stdout: {result.stdout.strip()[:500]}"
    except subprocess.TimeoutExpired:
        passed = False
        error = "Test timed out"
    except Exception as exc:
        passed = False
        error = str(exc)

    return TaskResult(
        instance_id=instance.instance_id,
        passed=passed,
        score=1.0 if passed else 0.0,
        tokens_used=0,
        wall_time_seconds=0.0,
        raw_output=agent_output,
        error=error,
    )


def get_reasoning_tasks() -> list[Task]:
    return [BuildDependencyOrderTask(), StateMachineTask()]
