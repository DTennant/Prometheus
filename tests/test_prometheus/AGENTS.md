# tests/test_prometheus/

16 test files covering all `src/prometheus/` subsystems. pytest + pytest-asyncio.

## CONVENTIONS

| Rule | Detail |
|------|--------|
| Organization | Class-based: `class TestFeature:` with `test_method()` methods |
| Async | Decorate `@pytest.mark.asyncio` on methods (belt-and-suspenders with `asyncio_mode=auto`) |
| Mocking | Protocol-based fake classes — NOT `unittest.mock` (sole exception: `test_benchmarks.py`) |
| Test data | Built inline or via `_make_*()` private factory helpers |
| Filesystem | `tmp_path` fixture (pytest built-in) — used in 9 files |
| Test doubles | `DryRunAgentClient` (from `eval/query_runner.py`) + `DryRunLLMClient` (from `evolution/mutator.py`) |

## SHARED FIXTURES (conftest.py)

```python
seed_config()           → HarnessConfig from create_seed_harness()
sample_task_instance()  → TaskInstance("test_001", add-two-numbers)
sample_passing_result() → TaskResult(passed=True, score=1.0)
sample_failing_result() → TaskResult(passed=False, error="...")
```

Used sparingly — most tests build data inline.

## TEST PATTERNS

- **Stub tasks**: `StubPassTask`, `AlwaysFailTask`, `StubMixedTask` — inline `Task` subclasses
- **Capture clients**: Record prompts/inputs for assertion (`CaptureClient.last_prompt`)
- **Stateful fakes**: `FakeInvalidClient.calls` counter to test retry behavior
- **Sandbox scoring**: Write solution code to `TaskSandbox` workspace, call `task.score()`
- **CLI testing**: `typer.testing.CliRunner` — module-level singleton in `test_cli.py`

## GOTCHAS

- `DryRunAgentClient` pass rate is hash-based (`hash(prompt) % 100`) — test outcomes are deterministic but depend on prompt content
- `test_benchmarks.py` is the only file using `unittest.mock` (patches external benchmark packages)
- No root `conftest.py` — relies on `pip install -e .` for import resolution
