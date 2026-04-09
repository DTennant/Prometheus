# eval/

Task evaluation pipeline. 18 files across 3 layers: core (6), tasks (5), benchmarks (5).

## STRUCTURE

```
eval/
├── task.py             # Task ABC, TaskInstance, TaskResult — fundamental types
├── scorer.py           # EvalReport dataclass, composite_score()
├── runner.py           # EvalRunner — orchestrates prompt assembly + execution
├── query_runner.py     # AgentClient Protocol, DryRunAgentClient
├── sandbox.py          # TaskSandbox — tmpdir workspace isolation
├── tasks/              # 5 built-in task files (code_gen, file_manip, debugging, reasoning)
└── benchmarks/         # 3 external benchmark adapters (SWE-bench, HumanEval+, TerminalBench)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add a new eval task | `tasks/` | Subclass `Task`, register in `tasks/__init__.py` |
| Add external benchmark | `benchmarks/` | Subclass `BenchmarkAdapter`, register in `benchmarks/__init__.py` |
| Change scoring | `scorer.py` | `accuracy × (budget / tokens_used)` |
| Change prompt assembly | `runner.py` | `_build_system_prompt()`, `_build_task_prompt()` |
| Understand workflow phases | `runner.py` | `_run_workflow()` — scratchpad vs context modes |

## ANTI-PATTERNS

- **DO NOT fix `# BUG:` comments** in `tasks/debugging.py` — they are intentional eval fixtures
- `runner.py` rebuilds `TaskResult` twice to inject `total_tokens` and `wall_time` — intentional override
- `runner.py` silently injects a default workflow phase when none configured — can confuse debugging
- `query_runner.py` `DryRunAgentClient` pass rate depends on `hash(prompt) % 100` — deterministic but opaque
- `tasks/code_generation.py` strips markdown fences from LLM output — can corrupt nested fences
- `benchmarks/swebench.py` says `requires_docker = True` but never uses Docker

## CONVENTIONS

- All task files use `_run_*_test()` shared scorers with subprocess execution
- Task `setup_files` embed test code as triple-quoted strings — test harness is data, not framework
- `get_task_suite()` in `tasks/__init__.py` is the only registry — add tasks there
