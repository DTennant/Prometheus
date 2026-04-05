# Prometheus — Self-Bootstrapping Agent Harness

**Let each base model evolve its own optimal harness from a minimal seed, instead of hand-designing one-size-fits-all scaffolding.**

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/tests-91_passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/CLI-pyre-orange" alt="CLI">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
</p>

---

## The Problem

Every agent harness today — Claude Code, OpenHands, SWE-agent, Aider, AIDE, Cursor — is **human-designed**. The same system prompt, tool descriptions, error handling, and task decomposition strategies regardless of which model powers it.

But models differ dramatically in tool-calling reliability, instruction following style, planning ability, and error recovery. A harness designed for Claude may be suboptimal for GPT-4o and wasteful for Qwen-72B.

**Human-designed harnesses are a compromise — good enough for many models, optimal for none.**

## The Hypothesis

> A model that evolves its own harness through iterative self-modification and evaluation will outperform the same model inside a generic, human-designed harness.

> **Corollary:** Different models will converge to meaningfully different harnesses, reflecting their different capabilities and failure modes.

---

## Quick Start

```bash
# Install
git clone https://github.com/HKUDS/OpenHarness.git
cd OpenHarness
pip install -e .

# Dry-run evolution (no API key needed)
pyre run --dry-run --generations 5 --beam-size 3

# Real evolution with Claude
export ANTHROPIC_API_KEY=sk-...
pyre run --model claude-sonnet-4-20250514 --generations 20

# Real evolution with GPT-4o
export OPENAI_API_KEY=sk-...
pyre run --api-format openai --model gpt-4o --generations 20

# Real evolution with any OpenAI-compatible provider
pyre run --api-format openai --base-url https://api.deepseek.com --api-key sk-... --model deepseek-chat
```

---

## How It Works

```
seed harness → eval on tasks → model sees failures → LLM mutates config → re-eval → keep top-K → repeat
```

### 1. Minimal Seed

The evolution starts from an intentionally minimal harness:

```
system_prompt: "You are a coding assistant. You can read files, write files,
               and execute shell commands. Solve the given task."
tools: read_file, write_file, execute, list_directory
max_iterations: 30
```

The seed deliberately omits task decomposition strategies, error handling instructions, testing strategies, memory usage, and self-reflection prompts — for the model to discover on its own.

### 2. Mutable Surface

What the model **can** evolve:

| Component | What it controls |
|-----------|-----------------|
| `system_prompt` | Full instructions given to the agent |
| `tool_descriptions` | How each tool is described to the model |
| `workflow_prompts` | Pre-task and post-task reflection prompts |
| `parameters` | max_iterations, temperature, timeout, retry, scratchpad |
| `custom_tools` | Composite tools built from base tools (e.g. "search_and_read") |
| `few_shot_examples` | Self-selected task/solution pairs |

What stays **immutable**: base tools, eval suite, model weights.

### 3. Eval Suite

10 tasks across 3 categories, scored by `accuracy × (budget / tokens_used)`:

| Category | Tasks | What they test |
|----------|-------|---------------|
| Code Generation | 5 | fibonacci, palindrome, flatten_list, merge_sorted, count_words |
| File Manipulation | 3 | find_and_replace, extract_functions, merge_configs |
| Debugging | 2 | off_by_one fix, circular import fix |

Each task runs the agent in a sandboxed workspace and validates output via subprocess.

### 4. Evolution Loop

```
for each generation:
    evaluate all configs in beam → collect scores + failure cases
    for each parent config:
        ask LLM to mutate config given failures + history
        validate mutation against schema
    evaluate all mutations
    select top-K configs (beam search with deduplication)
```

The mutating LLM sees **specific failure cases** (not just scores) and the **full evolution history** (to avoid regression).

---

## CLI Reference

```
pyre run          Run the self-bootstrapping evolution loop
pyre eval-only    Evaluate a single harness config without evolution
pyre compare      Compare results across multiple evolution runs
pyre show         Display results from a completed run
```

### `pyre run`

```
Options:
  -m, --model TEXT              Model name [default: claude-sonnet-4-20250514]
  -g, --generations INTEGER     Number of evolution generations [default: 20]
  -k, --beam-size INTEGER       Top-K configs to keep per generation [default: 5]
  --mutations-per-parent INT    Mutations per parent config [default: 3]
  -o, --output-dir TEXT         Output directory [default: runs]
  --api-format TEXT             API format: anthropic or openai [default: anthropic]
  --base-url TEXT               Custom API base URL
  --api-key TEXT                API key (or set env var)
  -t, --task-suite TEXT         Task suite: default, code_generation, file_manipulation, debugging
  --token-budget INTEGER        Token budget for efficiency scoring [default: 50000]
  --dry-run                     Simulate evolution without API calls
  --resume TEXT                 Resume from checkpoint file
  --seed-config TEXT            Path to custom seed config JSON
```

### `pyre eval-only`

```
pyre eval-only config.json --dry-run --task-suite code_generation
```

### `pyre compare`

```
pyre compare runs/run_abc123 runs/run_def456
```

### `pyre show`

```
pyre show runs/run_abc123 --generation 5
```

---

## Architecture

```
src/prometheus/
├── cli.py                     # pyre CLI entry point (Typer)
├── api_clients.py             # Anthropic + OpenAI API clients
├── __main__.py                # python -m prometheus
│
├── config/
│   ├── harness_config.py      # HarnessConfig — the mutable surface (frozen Pydantic)
│   ├── experiment_config.py   # ExperimentConfig — run parameters
│   └── schema_validator.py    # Prevents degenerate configs
│
├── eval/
│   ├── task.py                # Task ABC, TaskInstance, TaskResult
│   ├── sandbox.py             # Workspace isolation (tmpdir + subprocess)
│   ├── query_runner.py        # Agent execution with timeout
│   ├── runner.py              # EvalRunner — orchestrates task evaluation
│   ├── scorer.py              # Composite scoring (accuracy × efficiency)
│   └── tasks/
│       ├── code_generation.py # 5 HumanEval-style tasks
│       ├── file_manipulation.py # 3 multi-file editing tasks
│       └── debugging.py       # 2 bug diagnosis tasks
│
├── evolution/
│   ├── seed.py                # Minimal seed + human baseline configs
│   ├── mutator.py             # LLM-guided config mutation with retry
│   ├── selector.py            # Beam selection with deduplication
│   ├── history.py             # Evolution history tracking + serialization
│   └── loop.py                # Main evolution loop orchestrator
│
├── tools/
│   └── composite.py           # CompositeToolFactory for macro tools
│
├── logging/
│   └── experiment_logger.py   # JSONL events + JSON checkpoints
│
└── analysis/
    └── compare.py             # Cross-run comparison utilities
```

---

## Output Structure

Each run produces:

```
runs/<run_id>/
├── config.json                # Experiment config snapshot
├── events.jsonl               # All events (evals, generations, failures)
├── checkpoint_gen0000.json    # Config checkpoint for generation 0
├── checkpoint_gen0001.json    # Config checkpoint for generation 1
├── ...
└── best_config.json           # Best evolved harness config
```

---

## Experiment Design

### Baselines

| Baseline | Description |
|----------|-------------|
| Seed | Minimal harness, no evolution |
| Human-designed | Existing OpenHarness default config (in `reference/`) |
| Evolved | Self-bootstrapped after N generations |
| Cross-model transfer | Model A's evolved harness given to Model B |

### Models

| Model | API Format | Strengths |
|-------|-----------|-----------|
| Claude Sonnet 4 | anthropic | Strong instruction follower |
| GPT-4o | openai | Different tool-calling style |
| Qwen-72B / DeepSeek-V3 | openai | Open-weight, different optimization |

### Expected Results

1. **Evolved > Seed** — validates the setup works
2. **Evolved ≥ Human-designed** — the interesting claim
3. **Different models → different harnesses** — key insight about model-specificity
4. **Cross-model transfer degrades** — confirms harnesses are model-specific
5. **Convergence in ~10-15 generations** — practical runtime bounds

### Cost Estimate

~2.1M tokens per model ≈ $6-15 per model. Three models total: **$20-50**.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/test_prometheus/ -v

# Run a quick dry-run to verify everything works
pyre run --dry-run --generations 2 --beam-size 1

# Lint
ruff check src/prometheus/
```

### Adding New Eval Tasks

Subclass `Task` from `prometheus.eval.task`:

```python
from prometheus.eval.task import Task, TaskInstance, TaskResult
from pathlib import Path

class MyTask(Task):
    name = "my_task"
    category = "custom"

    def get_instances(self) -> list[TaskInstance]:
        return [TaskInstance(
            instance_id="custom_001",
            prompt="Write a function that...",
            expected_output="test code here",
            setup_files={"starter.py": "# starting code"},
        )]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        # Validate the agent's output
        passed = "expected" in agent_output
        return TaskResult(instance.instance_id, passed, 1.0 if passed else 0.0, 0, 0.0, agent_output)
```

Register it in `eval/tasks/__init__.py`.

---

## Reference Code

The original OpenHarness agent harness is preserved in `reference/` — the full source, tests, scripts, and documentation. Prometheus uses it as design reference but does not import from it.

---

## License

MIT — see [LICENSE](reference/LICENSE).
