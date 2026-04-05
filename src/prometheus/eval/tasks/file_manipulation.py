from __future__ import annotations

from pathlib import Path

from prometheus.eval.task import Task, TaskInstance, TaskResult


class FindAndReplaceTask(Task):
    name = "find_and_replace"
    category = "file_manipulation"

    def get_instances(self) -> list[TaskInstance]:
        return [
            TaskInstance(
                instance_id="filemanip_find_replace",
                prompt="Replace all occurrences of 'foo' with 'bar' in all .txt files in the workspace.",
                expected_output={
                    "a.txt": "bar baz bar",
                    "b.txt": "hello bar world",
                    "c.txt": "no match here",
                },
                setup_files={
                    "a.txt": "foo baz foo",
                    "b.txt": "hello foo world",
                    "c.txt": "no match here",
                },
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        expected = instance.expected_output
        total = len(expected)
        correct = 0
        for filename, expected_content in expected.items():
            filepath = workspace / filename
            if filepath.exists():
                actual = filepath.read_text(encoding="utf-8").strip()
                if actual == expected_content.strip():
                    correct += 1
        score = correct / total if total else 0.0
        return TaskResult(
            instance_id=instance.instance_id,
            passed=correct == total,
            score=score,
            tokens_used=0,
            wall_time_seconds=0.0,
            raw_output=agent_output,
            error=None if correct == total else f"Only {correct}/{total} files correct",
        )


class ExtractFunctionsTask(Task):
    name = "extract_functions"
    category = "file_manipulation"

    def get_instances(self) -> list[TaskInstance]:
        source_code = """def hello():
    pass

def world(x, y):
    return x + y

class MyClass:
    def method(self):
        pass

def standalone():
    return 42
"""
        return [
            TaskInstance(
                instance_id="filemanip_extract_functions",
                prompt="Read the file 'source.py' and extract all top-level function names (not methods inside classes). Write them one per line to 'functions.txt'.",
                expected_output="hello\nworld\nstandalone",
                setup_files={"source.py": source_code},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        output_path = workspace / "functions.txt"
        if not output_path.exists():
            return TaskResult(
                instance.instance_id, False, 0.0, 0, 0.0, agent_output, "functions.txt not created"
            )
        actual = output_path.read_text(encoding="utf-8").strip()
        expected = instance.expected_output.strip()
        actual_set = set(actual.split("\n"))
        expected_set = set(expected.split("\n"))
        passed = actual_set == expected_set
        return TaskResult(
            instance_id=instance.instance_id,
            passed=passed,
            score=1.0 if passed else len(actual_set & expected_set) / len(expected_set),
            tokens_used=0,
            wall_time_seconds=0.0,
            raw_output=agent_output,
            error=None if passed else f"Expected {expected_set}, got {actual_set}",
        )


class MergeConfigsTask(Task):
    name = "merge_configs"
    category = "file_manipulation"

    def get_instances(self) -> list[TaskInstance]:
        import json

        config_a = json.dumps({"host": "localhost", "port": 8080, "debug": True}, indent=2)
        config_b = json.dumps({"port": 9090, "workers": 4, "debug": False}, indent=2)
        expected = json.dumps(
            {"host": "localhost", "port": 9090, "debug": False, "workers": 4}, indent=2
        )
        return [
            TaskInstance(
                instance_id="filemanip_merge_configs",
                prompt="Merge config_a.json and config_b.json into merged.json. Values from config_b override config_a. Include all keys from both.",
                expected_output=expected,
                setup_files={"config_a.json": config_a, "config_b.json": config_b},
            )
        ]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        import json

        merged_path = workspace / "merged.json"
        if not merged_path.exists():
            return TaskResult(
                instance.instance_id, False, 0.0, 0, 0.0, agent_output, "merged.json not created"
            )
        try:
            actual = json.loads(merged_path.read_text(encoding="utf-8"))
            expected = json.loads(instance.expected_output)
            passed = actual == expected
        except json.JSONDecodeError as e:
            return TaskResult(
                instance.instance_id, False, 0.0, 0, 0.0, agent_output, f"Invalid JSON: {e}"
            )
        return TaskResult(
            instance_id=instance.instance_id,
            passed=passed,
            score=1.0 if passed else 0.0,
            tokens_used=0,
            wall_time_seconds=0.0,
            raw_output=agent_output,
            error=None if passed else "Merged config doesn't match expected",
        )


def get_file_manipulation_tasks() -> list[Task]:
    return [FindAndReplaceTask(), ExtractFunctionsTask(), MergeConfigsTask()]
