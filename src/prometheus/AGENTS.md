# src/prometheus/

Evolution engine — 36 Python files, ~3,300 lines total. Installable package (`pyre` CLI).

## STRUCTURE

```
prometheus/
├── cli.py              # Typer app: 5 commands, lazy imports in each
├── api_clients.py      # 4 client classes: {Anthropic,OpenAI} × {Agent,LLM}
├── config/             # HarnessConfig (frozen, 7 nested models) + ExperimentConfig
├── eval/               # Task ABC → Scorer → Runner pipeline
├── evolution/          # Seed → Mutate → Evaluate → Select loop
├── logging/            # ExperimentLogger (JSONL + JSON checkpoints)
├── tools/              # CompositeToolFactory (unused at runtime)
└── analysis/           # compare.py — cross-run comparison (zero internal deps)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add CLI command | `cli.py` | Use deferred imports inside function body |
| Add API provider | `api_clients.py` | Satisfy `AgentClient` + `LLMClient` Protocols structurally |
| Change mutable surface | `config/harness_config.py` | Add field → update `schema_validator.py` |
| Change scoring formula | `eval/scorer.py` | 31 lines, `composite_score()` |

## SHARED TYPES

| Type | Defined in | Used by |
|------|-----------|---------|
| `HarnessConfig` | `config/harness_config.py` | 7+ files — the most depended-on type |
| `EvalReport` | `eval/scorer.py` | Crosses eval/ → evolution/ boundary |
| `TaskResult` | `eval/task.py` | All task files, scorer, mutator |
| `AgentClient` | `eval/query_runner.py` | Protocol — satisfied by api_clients structurally |
| `LLMClient` | `evolution/mutator.py` | Protocol — satisfied by api_clients structurally |

## CONVENTIONS

- No `utils/` or `helpers/` — each module uses stdlib + direct layer deps only
- `logging/experiment_logger.py` and `analysis/compare.py` have zero internal imports
- `api_clients.py` uses lazy SDK imports (anthropic/openai) — may not be installed
- All `__init__.py` files are empty — no re-exports
