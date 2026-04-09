# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-09
**Commit:** fa3715f
**Branch:** origin/vk/d9ef-ulw-loop-self-bo

## OVERVIEW

Prometheus — self-bootstrapping agent harness evolution system. An LLM evolves its own optimal harness config (system prompt, tool descriptions, workflow phases) through beam-search mutation + evaluation. Python 3.11, Pydantic v2, Typer CLI (`pyre`). The `reference/` directory contains the original OpenHarness agent (`oh`) preserved as a read-only design baseline.

## STRUCTURE

```
OpenHarness/
├── src/prometheus/         # Active codebase — the evolution engine
│   ├── cli.py              # pyre CLI (Typer): run, eval-only, compare, show, benchmarks
│   ├── api_clients.py      # Anthropic + OpenAI dual-provider clients
│   ├── config/             # HarnessConfig (mutable surface) + ExperimentConfig
│   ├── eval/               # Task evaluation: runner, sandbox, scorer, tasks/, benchmarks/
│   ├── evolution/          # Core algorithm: loop, mutator, selector, history, seed
│   ├── logging/            # JSONL event logger + checkpoints
│   ├── tools/              # CompositeToolFactory (macro tools)
│   └── analysis/           # Cross-run comparison utilities
├── tests/test_prometheus/  # 16 test files, pytest + pytest-asyncio
├── reference/              # READ-ONLY archived OpenHarness (oh CLI, 28 modules, React TUI)
└── pyproject.toml          # Single config: hatchling build, ruff, mypy strict, pytest
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Run evolution | `src/prometheus/cli.py` → `run()` | `pyre run --dry-run --generations 5` |
| Understand mutation | `src/prometheus/evolution/mutator.py` | LLM prompt + retry + JSON validation |
| Add eval task | `src/prometheus/eval/tasks/` | Subclass `Task` ABC, register in `__init__.py` |
| Add benchmark | `src/prometheus/eval/benchmarks/` | Subclass `BenchmarkAdapter`, register in `__init__.py` |
| Understand scoring | `src/prometheus/eval/scorer.py` | `accuracy × (budget / tokens_used)` |
| Config schema | `src/prometheus/config/harness_config.py` | Frozen Pydantic model, 7 nested types |
| Reference harness | `reference/openharness/` | 43 tools, multi-agent swarm, React TUI |
| Tests | `tests/test_prometheus/` | Protocol-based fakes, DryRun clients, `tmp_path` |

## DEPENDENCY FLOW

```
config/ ← eval/task ← eval/scorer ← eval/runner ← evolution/* ← cli.py
                                                        ↑
logging/ ──────────────────────────────── (consumed laterally)
api_clients.py ────────────────────────── (satisfies Protocols structurally)
```

No circular imports. `EvalReport` and `HarnessConfig` are the two shared types crossing boundaries.

## CONVENTIONS

| Rule | Value |
|------|-------|
| Line length | 100 chars (ruff) |
| Type annotations | Required everywhere (mypy strict) |
| Python target | 3.11 |
| Async tests | `asyncio_mode = "auto"`, but methods still decorated `@pytest.mark.asyncio` |
| Test doubles | Protocol-based fake classes, not `unittest.mock` (except `test_benchmarks.py`) |
| Imports in CLI | Deferred (inside function bodies) to avoid circular deps + speed startup |
| Config immutability | `HarnessConfig` is `frozen=True`; mutation via `model_validate()` on new data |

## ANTI-PATTERNS (THIS PROJECT)

- **DO NOT fix `# BUG:` comments** in `eval/tasks/debugging.py` — they are intentional eval fixtures
- **DO NOT import from `reference/`** — it is a static baseline, not a dependency
- `logging/` module name shadows stdlib — access stdlib via `import logging` before any `prometheus.logging` import
- `tools/composite.py` is unused at runtime — `EvalRunner` renders composites as prompt text directly

## COMMANDS

```bash
pip install -e ".[dev]"                    # Install with dev deps
pyre run --dry-run --generations 5         # Dry-run evolution
pyre eval-only config.json --dry-run       # Evaluate single config
pytest tests/test_prometheus/ -v           # Run tests
ruff check src/prometheus/                 # Lint
ruff format src/prometheus/                # Format
mypy src/prometheus/                       # Type check
```

## NOTES

- No CI pipeline exists for Prometheus (root) — only `reference/.github/workflows/ci.yml` for OpenHarness
- `uv.lock` is gitignored — builds not fully reproducible without regeneration
- `DryRunAgentClient` uses `hash(prompt) % 100` for pseudo-random pass/fail — not truly random
- Schema migrations in `HarnessConfig` are silent (`@model_validator(mode="before")`)
- `api_clients.py` `"Continue."` re-injection doesn't handle real tool calls — stub behavior
