from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class AgentClient(Protocol):
    async def run_task(
        self, prompt: str, system_prompt: str, max_iterations: int, workspace: Path
    ) -> tuple[str, int]: ...


@dataclass
class QueryResult:
    output: str
    tokens_used: int
    wall_time_seconds: float
    timed_out: bool = False
    error: str | None = None


async def run_eval_query(
    client: AgentClient,
    prompt: str,
    system_prompt: str,
    max_iterations: int = 30,
    timeout: int = 600,
    workspace: Path | None = None,
) -> QueryResult:
    start = time.monotonic()
    ws = workspace or Path(".")
    try:
        async with asyncio.timeout(timeout):
            output, tokens = await client.run_task(prompt, system_prompt, max_iterations, ws)
            elapsed = time.monotonic() - start
            return QueryResult(output=output, tokens_used=tokens, wall_time_seconds=elapsed)
    except TimeoutError:
        elapsed = time.monotonic() - start
        return QueryResult(
            output="",
            tokens_used=0,
            wall_time_seconds=elapsed,
            timed_out=True,
            error=f"Task timed out after {timeout}s",
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return QueryResult(
            output="",
            tokens_used=0,
            wall_time_seconds=elapsed,
            error=str(exc),
        )


class DryRunAgentClient:
    """Simulated agent client for dry-run mode.

    Provides hardcoded solutions for all 13 built-in eval tasks.
    Code-generation tasks use ``_SOLUTIONS`` (returned as agent output).
    File-writing tasks use ``_FILE_SOLUTIONS`` (written to workspace).

    Pass gate: ``len(system_prompt) > 120 OR hash(prompt) % 100 < 30``.
    This simulates harness quality influencing task success.
    """

    # Code-gen tasks: agent output is written to solution.py by the scorer
    _SOLUTIONS: dict[str, str] = {
        "merge_intervals": (
            "def merge_intervals(intervals):\n"
            "    if not intervals: return []\n"
            "    intervals.sort()\n"
            "    merged = [intervals[0]]\n"
            "    for s, e in intervals[1:]:\n"
            "        if s <= merged[-1][1]:\n"
            "            merged[-1][1] = max(merged[-1][1], e)\n"
            "        else: merged.append([s, e])\n"
            "    return merged\n"
        ),
        "top_k_frequent": (
            "from collections import Counter\n"
            "def top_k_frequent(nums, k):\n"
            "    return [x for x, _ in Counter(nums).most_common(k)]\n"
        ),
        "LRUCache": (
            "from collections import OrderedDict\n"
            "class LRUCache:\n"
            "    def __init__(self, capacity):\n"
            "        self.cap = capacity\n"
            "        self.cache = OrderedDict()\n"
            "    def get(self, key):\n"
            "        if key not in self.cache: return -1\n"
            "        self.cache.move_to_end(key)\n"
            "        return self.cache[key]\n"
            "    def put(self, key, value):\n"
            "        if key in self.cache: self.cache.move_to_end(key)\n"
            "        self.cache[key] = value\n"
            "        if len(self.cache) > self.cap:\n"
            "            self.cache.popitem(last=False)\n"
        ),
        "prefix tree": (
            "class Trie:\n"
            "    def __init__(self): self.root = {}\n"
            "    def insert(self, word):\n"
            "        node = self.root\n"
            "        for c in word: node = node.setdefault(c, {})\n"
            "        node['$'] = True\n"
            "    def search(self, word):\n"
            "        node = self.root\n"
            "        for c in word:\n"
            "            if c not in node: return False\n"
            "            node = node[c]\n"
            "        return '$' in node\n"
            "    def starts_with(self, prefix):\n"
            "        node = self.root\n"
            "        for c in prefix:\n"
            "            if c not in node: return False\n"
            "            node = node[c]\n"
            "        return True\n"
        ),
        "serialize": (
            "class TreeNode:\n"
            "    def __init__(self, val=0, left=None, right=None):\n"
            "        self.val = val\n"
            "        self.left = left\n"
            "        self.right = right\n"
            "\n"
            "def serialize(root):\n"
            "    if root is None: return 'null'\n"
            "    return (f'{root.val},{serialize(root.left)}'\n"
            "            f',{serialize(root.right)}')\n"
            "\n"
            "def deserialize(data):\n"
            "    vals = iter(data.split(','))\n"
            "    def build():\n"
            "        v = next(vals)\n"
            "        if v == 'null': return None\n"
            "        node = TreeNode(int(v))\n"
            "        node.left = build()\n"
            "        node.right = build()\n"
            "        return node\n"
            "    return build()\n"
        ),
    }

    # File-writing tasks: files are written to workspace directly
    _FILE_SOLUTIONS: dict[str, dict[str, str]] = {
        # --- Debugging tasks ---
        "shared reference": {
            "config_merger.py": (
                "import json\nimport copy\n\n"
                "def update_config(config, updates):\n"
                '    """Apply updates to config dict."""\n'
                "    for key, value in updates.items():\n"
                "        if isinstance(value, dict) and key in config:\n"
                "            update_config(config[key], value)\n"
                "        else:\n"
                "            config[key] = value\n"
                "    return config\n\n"
                "def load_and_merge(base_path, override_path, output_path):\n"
                "    with open(base_path) as f:\n"
                "        base = json.load(f)\n"
                "    with open(override_path) as f:\n"
                "        overrides = json.load(f)\n"
                "    defaults = copy.deepcopy(base)\n"
                "    merged = update_config(defaults, overrides)\n"
                '    with open(output_path, "w") as f:\n'
                "        json.dump(merged, f, indent=2)\n"
                "    return base, merged\n"
            ),
        },
        "race condition": {
            "thread_counter.py": (
                "import threading\n\n"
                "class Counter:\n"
                "    def __init__(self):\n"
                "        self.value = 0\n"
                "        self._lock = threading.Lock()\n\n"
                "    def increment(self):\n"
                "        with self._lock:\n"
                "            self.value += 1\n\n"
                "    def get(self):\n"
                "        return self.value\n\n\n"
                "def run_increments(counter, n):\n"
                "    for _ in range(n):\n"
                "        counter.increment()\n"
            ),
        },
        "duplicate email": {
            "service.py": (
                "from repository import UserRepository\n\n"
                "class UserService:\n"
                "    def __init__(self):\n"
                "        self.repo = UserRepository()\n\n"
                "    def register(self, name, email):\n"
                "        if self.repo.find_by_email(email):\n"
                '            raise ValueError(f"Email {email} '
                'already registered")\n'
                "        return self.repo.create(name, email)\n\n"
                "    def get_user(self, user_id):\n"
                "        user = self.repo.get(user_id)\n"
                "        if user is None:\n"
                '            raise ValueError(f"User {user_id}'
                ' not found")\n'
                "        return user\n\n"
                "    def deactivate(self, user_id):\n"
                "        user = self.repo.get(user_id)\n"
                "        if user is None:\n"
                '            raise ValueError(f"User {user_id}'
                ' not found")\n'
                "        return self.repo.delete(user_id)\n"
            ),
        },
        # --- File manipulation tasks ---
        "Rename `UserRecord`": {
            "main.py": (
                "from utils import compute_annual_value\n"
                "from models import PersonRecord\n\n"
                "def process_users(users):\n"
                "    for user in users:\n"
                '        record = PersonRecord(user["name"],'
                ' user["age"])\n'
                "        total = compute_annual_value(record)\n"
                '        print(f"{record.name}: {total}")\n'
            ),
            "utils.py": (
                "def compute_annual_value(record):\n"
                "    return record.age * 12\n\n"
                "def format_total(total):\n"
                '    return f"${compute_annual_value(total):.2f}"\n'
            ),
            "models.py": (
                "class PersonRecord:\n"
                "    def __init__(self, name, age):\n"
                "        self.name = name\n"
                "        self.age = age\n\n"
                "    def __repr__(self):\n"
                "        return ("
                'f"PersonRecord({self.name}, {self.age})")\n'
            ),
        },
        "produce 'report.json'": {
            "pipeline.py": (
                "import csv, json\n\n"
                "departments = {}\n"
                "with open('data.csv') as f:\n"
                "    for row in csv.DictReader(f):\n"
                "        dept = row['department']\n"
                "        salary = int(row['salary'])\n"
                "        name = row['name']\n"
                "        if dept not in departments:\n"
                "            departments[dept] = {'names': [],"
                " 'salaries': []}\n"
                "        departments[dept]['names'].append(name)\n"
                "        departments[dept]['salaries']"
                ".append(salary)\n\n"
                "report = {}\n"
                "for dept, data in departments.items():\n"
                "    sals = data['salaries']\n"
                "    names = data['names']\n"
                "    top_idx = sals.index(max(sals))\n"
                "    report[dept] = {\n"
                "        'count': len(sals),\n"
                "        'average_salary': sum(sals) // len(sals),\n"
                "        'top_earner': names[top_idx],\n"
                "    }\n\n"
                "with open('report.json', 'w') as f:\n"
                "    json.dump(report, f)\n"
            ),
        },
        "test_calculator.py": {
            "test_calculator.py": (
                "import pytest\n"
                "from calculator import Calculator\n\n"
                "def test_add():\n"
                "    c = Calculator()\n"
                "    assert c.add(2, 3) == 5\n\n"
                "def test_add_negative():\n"
                "    c = Calculator()\n"
                "    assert c.add(-1, 1) == 0\n\n"
                "def test_divide():\n"
                "    c = Calculator()\n"
                "    assert c.divide(10, 2) == 5.0\n\n"
                "def test_divide_by_zero():\n"
                "    c = Calculator()\n"
                "    with pytest.raises(ValueError):\n"
                "        c.divide(1, 0)\n\n"
                "def test_power():\n"
                "    c = Calculator()\n"
                "    assert c.power(2, 3) == 8\n\n"
                "def test_power_negative_exp():\n"
                "    c = Calculator()\n"
                "    with pytest.raises(ValueError):\n"
                "        c.power(2, -1)\n\n"
                "def test_power_zero():\n"
                "    c = Calculator()\n"
                "    assert c.power(5, 0) == 1\n\n"
                "def test_history_last_n():\n"
                "    c = Calculator()\n"
                "    c.add(1, 2)\n"
                "    c.divide(6, 3)\n"
                "    h = c.last_n(2)\n"
                "    assert len(h) == 2\n\n"
                "def test_history_clear():\n"
                "    c = Calculator()\n"
                "    c.add(1, 2)\n"
                "    c.clear()\n"
                "    assert c.last_n(10) == []\n"
            ),
        },
        # --- Reasoning tasks ---
        "topological": {
            "build_order.py": (
                "def compute_build_order(deps):\n"
                "    order = []\n"
                "    visited = set()\n"
                "    visiting = set()\n\n"
                "    def visit(pkg):\n"
                "        if pkg in visiting:\n"
                "            raise ValueError('Cycle detected')\n"
                "        if pkg in visited:\n"
                "            return\n"
                "        visiting.add(pkg)\n"
                "        for dep in deps.get(pkg, []):\n"
                "            visit(dep)\n"
                "        visiting.discard(pkg)\n"
                "        visited.add(pkg)\n"
                "        order.append(pkg)\n\n"
                "    for pkg in deps:\n"
                "        visit(pkg)\n"
                "    return order\n"
            ),
        },
        "OrderStateMachine": {
            "state_machine.py": (
                "class OrderStateMachine:\n"
                "    _TRANSITIONS = {\n"
                "        'pending': {'confirm': 'confirmed',"
                " 'cancel': 'cancelled'},\n"
                "        'confirmed': {'ship': 'shipped',"
                " 'cancel': 'cancelled'},\n"
                "        'shipped': {'deliver': 'delivered'},\n"
                "        'delivered': {},\n"
                "        'cancelled': {},\n"
                "    }\n\n"
                "    def __init__(self):\n"
                "        self._state = 'pending'\n"
                "        self._history = ['pending']\n\n"
                "    @property\n"
                "    def state(self):\n"
                "        return self._state\n\n"
                "    def transition(self, action):\n"
                "        transitions = self._TRANSITIONS"
                ".get(self._state, {})\n"
                "        if action not in transitions:\n"
                "            return False\n"
                "        self._state = transitions[action]\n"
                "        self._history.append(self._state)\n"
                "        return True\n\n"
                "    def get_history(self):\n"
                "        return list(self._history)\n"
            ),
        },
    }

    def __init__(self, default_output: str = "# solution placeholder\nresult = 42") -> None:
        self._default_output = default_output

    async def run_task(
        self,
        prompt: str,
        system_prompt: str,
        max_iterations: int,
        workspace: Path,
    ) -> tuple[str, int]:
        await asyncio.sleep(0.01)
        prompt_quality = len(system_prompt)
        task_hash = hash(prompt) % 100
        quality_ok = prompt_quality > 120 or task_hash < 30

        # Code-gen tasks: return solution as output text
        for keyword, solution in self._SOLUTIONS.items():
            if keyword.lower() in prompt.lower():
                if quality_ok:
                    return solution, 100 + prompt_quality
                break

        # File-writing tasks: write solution files to workspace
        for keyword, files in self._FILE_SOLUTIONS.items():
            if keyword.lower() in prompt.lower():
                if quality_ok:
                    for fname, content in files.items():
                        fpath = workspace / fname
                        fpath.parent.mkdir(parents=True, exist_ok=True)
                        fpath.write_text(content, encoding="utf-8")
                    return "Files updated.", 100 + prompt_quality
                break

        return self._default_output, 150
