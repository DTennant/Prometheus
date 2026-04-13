from __future__ import annotations

import subprocess
from pathlib import Path

from prometheus.eval.task import Task, TaskInstance, TaskResult


class SilentDataCorruptionTask(Task):
    name = "silent_data_corruption"
    category = "debugging"

    def get_instances(self) -> list[TaskInstance]:
        buggy_code = '''import json

def update_config(config, updates):
    """Apply updates to config dict, preserving nested structure."""
    for key, value in updates.items():
        if isinstance(value, dict) and key in config:
            update_config(config[key], value)
        else:
            config[key] = value
    return config

def load_and_merge(base_path, override_path, output_path):
    with open(base_path) as f:
        base = json.load(f)
    with open(override_path) as f:
        overrides = json.load(f)

    # BUG: shared reference — mutating base also mutates the cached version
    defaults = base
    merged = update_config(defaults, overrides)

    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2)

    return base, merged
'''
        test_code = """import json, os, sys
sys.path.insert(0, ".")
from config_merger import load_and_merge

base = {"db": {"host": "localhost", "port": 5432}, "debug": False}
overrides = {"db": {"port": 9999}, "debug": True}

with open("base.json", "w") as f:
    json.dump(base, f)
with open("overrides.json", "w") as f:
    json.dump(overrides, f)

original_base, merged = load_and_merge("base.json", "overrides.json", "output.json")

# The bug: original_base should NOT be modified
assert original_base["db"]["port"] == 5432, f"Base was corrupted: port={original_base['db']['port']}"
assert original_base["debug"] == False, "Base debug was corrupted"
assert merged["db"]["port"] == 9999
assert merged["db"]["host"] == "localhost"
assert merged["debug"] == True

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="debug_silent_corruption",
                prompt=(
                    "The file 'config_merger.py' has a subtle bug: `load_and_merge` corrupts "
                    "the original base config because it uses a shared reference instead of a copy. "
                    "Fix it so the original base dict is never modified. Only modify config_merger.py."
                ),
                expected_output=test_code,
                setup_files={"config_merger.py": buggy_code, "test.py": test_code},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_debug_test(instance, workspace, agent_output)


class ConcurrencyBugTask(Task):
    name = "concurrency_bug"
    category = "debugging"

    def get_instances(self) -> list[TaskInstance]:
        buggy_code = """import threading

class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        current = self.value
        self.value = current + 1

    def get(self):
        return self.value


def run_increments(counter, n):
    for _ in range(n):
        counter.increment()
"""
        test_code = """import threading, sys
sys.path.insert(0, ".")
from thread_counter import Counter, run_increments

counter = Counter()
threads = []
num_threads = 10
increments_per_thread = 1000

for _ in range(num_threads):
    t = threading.Thread(target=run_increments, args=(counter, increments_per_thread))
    threads.append(t)

for t in threads:
    t.start()
for t in threads:
    t.join()

expected = num_threads * increments_per_thread
actual = counter.get()
assert actual == expected, f"Expected {expected}, got {actual} (race condition still present)"
print("PASS")
"""
        return [
            TaskInstance(
                instance_id="debug_concurrency",
                prompt=(
                    "The file 'thread_counter.py' has a race condition in the `Counter.increment` "
                    "method — it reads and writes `self.value` non-atomically. Fix it so the counter "
                    "is thread-safe. Use a threading.Lock. Only modify thread_counter.py."
                ),
                expected_output=test_code,
                setup_files={"thread_counter.py": buggy_code, "test.py": test_code},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_debug_test(instance, workspace, agent_output)


class MultiFileBugTask(Task):
    name = "multi_file_bug"
    category = "debugging"

    def get_instances(self) -> list[TaskInstance]:
        repo_py = """class UserRepository:
    def __init__(self):
        self._users = {}
        self._next_id = 1

    def create(self, name, email):
        user_id = self._next_id
        self._next_id += 1
        self._users[user_id] = {"id": user_id, "name": name, "email": email}
        return user_id

    def get(self, user_id):
        return self._users.get(user_id)

    def find_by_email(self, email):
        for user in self._users.values():
            if user["email"] == email:
                return user
        return None

    def delete(self, user_id):
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False
"""
        service_py = """from repository import UserRepository

class UserService:
    def __init__(self):
        self.repo = UserRepository()

    def register(self, name, email):
        # BUG 1: doesn't check for duplicate email
        user_id = self.repo.create(name, email)
        return user_id

    def get_user(self, user_id):
        user = self.repo.get(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        return user

    def deactivate(self, user_id):
        user = self.repo.get(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        # BUG 2: deletes user but doesn't return confirmation
        self.repo.delete(user_id)
"""
        test_code = """import sys
sys.path.insert(0, ".")
from service import UserService

svc = UserService()

# Test register
uid1 = svc.register("Alice", "alice@test.com")
assert uid1 is not None

# Test duplicate email raises
try:
    svc.register("Alice2", "alice@test.com")
    assert False, "Should have raised ValueError for duplicate email"
except ValueError:
    pass

# Test get_user
user = svc.get_user(uid1)
assert user["name"] == "Alice"

# Test deactivate returns True
result = svc.deactivate(uid1)
assert result == True, f"deactivate should return True, got {result}"

# Test get after deactivate raises
try:
    svc.get_user(uid1)
    assert False, "Should have raised ValueError for deleted user"
except ValueError:
    pass

# Test deactivate non-existent raises
try:
    svc.deactivate(999)
    assert False, "Should have raised ValueError"
except ValueError:
    pass

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="debug_multi_file",
                prompt=(
                    "This project has two bugs across two files:\n"
                    "1. In service.py, `register()` doesn't check for duplicate emails — "
                    "it should raise ValueError if the email already exists\n"
                    "2. In service.py, `deactivate()` doesn't return a value — "
                    "it should return True on success\n"
                    "Fix both bugs. You may modify both repository.py and service.py."
                ),
                expected_output=test_code,
                setup_files={
                    "repository.py": repo_py,
                    "service.py": service_py,
                    "test.py": test_code,
                },
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_debug_test(instance, workspace, agent_output)


def _run_debug_test(instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
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


def get_debugging_tasks() -> list[Task]:
    return [SilentDataCorruptionTask(), ConcurrencyBugTask(), MultiFileBugTask()]
