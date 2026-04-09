# evolution/

Core beam-search evolution algorithm. 6 files, ~590 lines.

## WHERE TO LOOK

| Task | File | Key function |
|------|------|-------------|
| Understand the main loop | `loop.py` | `EvolutionLoop.run()` — single 90-line async method |
| Change how configs mutate | `mutator.py` | `mutate_config()` + `_build_mutation_prompt()` |
| Change beam selection | `selector.py` | `BeamSelector.select()` |
| Change seed config | `seed.py` | `create_seed_harness()` |
| Track evolution history | `history.py` | `EvolutionHistory` — JSON serializable |

## ARCHITECTURE

```
seed.py → loop.py → mutator.py → selector.py
                ↓           ↑
           history.py    (eval/scorer.EvalReport)
```

`loop.py` is the orchestrator. It receives an `EvalRunner` (injected, not imported) and coordinates:
1. Evaluate beam → collect `EvalReport` per config
2. Build composite scores → inject into reports
3. Record generation in history + checkpoint
4. Mutate each parent config (LLM call via `mutator.py`)
5. Evaluate candidates → select top-K → repeat

## GOTCHAS

- `mutator.py` has a 60-line inline LLM prompt in `_build_mutation_prompt()` — no docstrings
- `DryRunLLMClient.generate()` uses regex to extract JSON from its own prompt — fragile
- `loop.py:run()` silently resets beam to `[seed_config]` if all candidates fail — no log warning
- `selector.py` and `history.py` use `TYPE_CHECKING`-only imports for `HarnessConfig`/`EvalReport`
- Empty-beam recovery loses all candidate information silently
