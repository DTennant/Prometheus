from __future__ import annotations

import subprocess
from pathlib import Path

from prometheus.eval.task import Task, TaskInstance, TaskResult


class LRUCacheTask(Task):
    name = "lru_cache"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import LRUCache

cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1
cache.put(3, 3)
assert cache.get(2) == -1
cache.put(4, 4)
assert cache.get(1) == -1
assert cache.get(3) == 3
assert cache.get(4) == 4

cache2 = LRUCache(1)
cache2.put(1, 10)
assert cache2.get(1) == 10
cache2.put(2, 20)
assert cache2.get(1) == -1
assert cache2.get(2) == 20

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_lru_cache",
                prompt=(
                    "Implement a class `LRUCache` with:\n"
                    "- `__init__(self, capacity: int)` — initialize with positive capacity\n"
                    "- `get(self, key: int) -> int` — return value if key exists, else -1\n"
                    "- `put(self, key: int, value: int)` — insert or update. "
                    "If capacity is exceeded, evict the least recently used key.\n"
                    "Both get and put must run in O(1) average time."
                ),
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


class IntervalMergeTask(Task):
    name = "interval_merge"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import merge_intervals

assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([]) == []
assert merge_intervals([[1,2]]) == [[1,2]]
assert merge_intervals([[1,4],[0,4]]) == [[0,4]]
assert merge_intervals([[1,4],[2,3]]) == [[1,4]]
assert merge_intervals([[2,3],[4,5],[6,7],[8,9],[1,10]]) == [[1,10]]

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_interval_merge",
                prompt=(
                    "Write a function `merge_intervals(intervals)` that takes a list of "
                    "[start, end] intervals and merges all overlapping intervals. "
                    "Return the merged list sorted by start time. Handle edge cases: "
                    "empty input, single interval, fully contained intervals."
                ),
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


class TrieTask(Task):
    name = "trie"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import Trie

t = Trie()
t.insert("apple")
assert t.search("apple") == True
assert t.search("app") == False
assert t.starts_with("app") == True
t.insert("app")
assert t.search("app") == True
assert t.search("apples") == False
assert t.starts_with("b") == False

t2 = Trie()
assert t2.search("") == False
t2.insert("")
assert t2.search("") == True
assert t2.starts_with("") == True

t3 = Trie()
t3.insert("abc")
t3.insert("abd")
t3.insert("xyz")
assert t3.starts_with("ab") == True
assert t3.starts_with("xy") == True
assert t3.starts_with("xz") == False

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_trie",
                prompt=(
                    "Implement a `Trie` (prefix tree) class with:\n"
                    "- `insert(word: str)` — insert a word\n"
                    "- `search(word: str) -> bool` — return True if the exact word is in the trie\n"
                    "- `starts_with(prefix: str) -> bool` — return True if any word starts with prefix\n"
                    "Handle empty strings correctly."
                ),
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


class TopKFrequentTask(Task):
    name = "top_k_frequent"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import top_k_frequent

assert sorted(top_k_frequent([1,1,1,2,2,3], 2)) == [1, 2]
assert top_k_frequent([1], 1) == [1]
assert sorted(top_k_frequent([4,4,4,1,1,2,2,2,3], 2)) == [2, 4]
assert sorted(top_k_frequent([1,2,3,4], 4)) == [1, 2, 3, 4]
assert top_k_frequent([5,5,5,5], 1) == [5]
assert sorted(top_k_frequent([1,1,2,2,3,3], 3)) == [1, 2, 3]

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_top_k_frequent",
                prompt=(
                    "Write a function `top_k_frequent(nums: list[int], k: int) -> list[int]` "
                    "that returns the k most frequent elements. The answer can be in any order. "
                    "Your solution should be better than O(n log n) — use a heap or bucket sort."
                ),
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


class SerializeTreeTask(Task):
    name = "serialize_tree"
    category = "code_generation"

    def get_instances(self) -> list[TaskInstance]:
        test_code = """
from solution import TreeNode, serialize, deserialize

root = TreeNode(1)
root.left = TreeNode(2)
root.right = TreeNode(3)
root.right.left = TreeNode(4)
root.right.right = TreeNode(5)

data = serialize(root)
assert isinstance(data, str)
new_root = deserialize(data)
assert new_root.val == 1
assert new_root.left.val == 2
assert new_root.right.val == 3
assert new_root.right.left.val == 4
assert new_root.right.right.val == 5
assert new_root.left.left is None
assert new_root.left.right is None

assert deserialize(serialize(None)) is None

single = TreeNode(42)
assert deserialize(serialize(single)).val == 42

left = TreeNode(1, TreeNode(2, TreeNode(3)))
r = deserialize(serialize(left))
assert r.val == 1 and r.left.val == 2 and r.left.left.val == 3
assert r.right is None

print("PASS")
"""
        return [
            TaskInstance(
                instance_id="codegen_serialize_tree",
                prompt=(
                    "Implement binary tree serialization and deserialization.\n\n"
                    "Define a `TreeNode` class with `val`, `left`, `right` attributes "
                    "(left and right default to None).\n"
                    "Write `serialize(root) -> str` to encode the tree as a string.\n"
                    "Write `deserialize(data) -> TreeNode or None` to decode it back.\n"
                    "The deserialized tree must be structurally identical to the original."
                ),
                expected_output=test_code,
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        return _run_code_test(instance, workspace, agent_output)


def _run_code_test(instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
    solution_path = workspace / "solution.py"
    test_path = workspace / "test_solution.py"

    code = agent_output.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        code = "\n".join(lines)

    solution_path.write_text(code, encoding="utf-8")
    test_path.write_text(instance.expected_output, encoding="utf-8")

    try:
        result = subprocess.run(
            ["python", str(test_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=10,
        )
        passed = result.returncode == 0
        error = result.stderr.strip() if not passed else None
    except subprocess.TimeoutExpired:
        passed = False
        error = "Test execution timed out"
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


def get_code_generation_tasks() -> list[Task]:
    return [
        LRUCacheTask(),
        IntervalMergeTask(),
        TrieTask(),
        TopKFrequentTask(),
        SerializeTreeTask(),
    ]
