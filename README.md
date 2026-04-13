# Prometheus

**Let each base model evolve its own optimal agent harness — instead of hand-designing one-size-fits-all scaffolding.**

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/tests-144_passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/CLI-pyre-orange" alt="CLI">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
</p>

Prometheus evolves agent harnesses through beam-search mutation and evaluation. Give it a model, and it discovers the optimal agent architecture — tools, prompts, error handling, and code structure — by iteratively mutating and testing against real programming tasks.

**Key result**: In a 3-generation run with Claude Sonnet 4, the system evolved a seed agent from **54% → 92% accuracy** by autonomously adding Python syntax validation, a `check_syntax` tool, and targeted prompt improvements. See [Example Evolved Agent](#example-evolved-agent).

It has two modes:

- **Config mode** (`--mode config`) — evolves harness configuration (system prompt, workflow, tools, parameters)
- **Code mode** (`--mode code`) — evolves the entire agent codebase, producing a standalone, pip-installable, Docker-buildable agent each generation

---

## Setup

### Prerequisites

- Python 3.10+ (3.11 recommended)
- Docker (required for `--mode code` and containerized runs)

### Install

```bash
git clone https://github.com/DTennant/Prometheus.git
cd Prometheus

pip install -e .

# With dev tools (testing/linting)
pip install -e ".[dev]"
```

Verify:

```bash
pyre --help
pytest tests/test_prometheus/ -q   # 144 tests
```

---

## Quick Start

### 1. Dry Run (no API key needed)

```bash
# Config evolution
pyre run --dry-run --generations 5 --beam-size 3

# Code evolution
pyre run --mode code --dry-run --generations 3 --beam-size 2
```

### 2. Real Evolution

```bash
# Anthropic
export ANTHROPIC_API_KEY=sk-...
pyre run --model claude-sonnet-4-20250514 --generations 10

# OpenAI
export OPENAI_API_KEY=sk-...
pyre run --api-format openai --model gpt-4o --generations 10

# Any OpenAI-compatible provider (LiteLLM, vLLM, Ollama, etc.)
pyre run --api-format openai \
    --base-url https://your-proxy.com/v1/ \
    --api-key your-key \
    --model your-model \
    --generations 10
```

### 3. Code Evolution with Docker

```bash
# Build Prometheus image
docker build -t prometheus-evolution \
    --build-arg UID="$(id -u)" \
    --build-arg GID="$(id -g)" .

# Run evolution (agents execute in nested Docker containers)
docker run --rm \
    -v "$(pwd)/runs:/app/runs" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    --group-add "$(stat -c '%g' /var/run/docker.sock)" \
    --network host \
    -e OPENAI_API_KEY="$KEY" \
    prometheus-evolution \
    run --mode code \
    --api-format openai \
    --base-url https://your-proxy.com/v1/ \
    --model claude-sonnet-4-6 \
    --generations 5 --beam-size 2
```

---

## How It Works

```
seed → evaluate on tasks → LLM reads failures → mutate code → re-evaluate → keep top-K → repeat
```

### Code Mode

Evolves a complete Python agent package. The LLM mutator reads all source files plus eval results, then returns targeted file modifications — adding tools, fixing bugs, improving prompts, or restructuring the conversation loop.

Each candidate is built into a Docker image, run against eval tasks in isolated containers, and scored. Workspace files are transferred via `docker cp` for full isolation.

**Seed agent** (9 files, ~17K bytes):
```
seed_agent/
├── pyproject.toml          # pip-installable
├── Dockerfile              # Docker-buildable
└── src/agent/
    ├── cli.py              # CLI entry point (--prompt, --workspace, --model)
    ├── agent.py            # Plan-augmented LLM conversation loop
    ├── tools.py            # 7 tools (read, write, edit, list, search, exec, test)
    ├── planner.py          # Task decomposition
    └── context.py          # Token-aware conversation compaction
```

### Staged Evolution

Multi-stage campaigns via `--stage`:

| Stage | Seed | Tasks | Goal |
|-------|------|-------|------|
| 1 (default) | Minimal (7 tools) | 13 built-in tasks | Evolve tool use, prompting, error handling |
| 2 | Evolved example agent (8 tools) | 13 built-in tasks | Evolve planning, context management |
| 3 | Winner of stage 2 | SWE-bench subset | Evolve toward real-world SWE capability |

```bash
pyre run --mode code --stage 1 --generations 8 --beam-size 3
pyre run --mode code --stage 2 --generations 10 --beam-size 3
pyre run --mode code --stage 3 --task-suite swebench --task-limit 30
```

### Eval Suite

13 built-in tasks across 4 categories, scored by `accuracy × (budget / tokens_used)`:

| Category | Tasks | What they test |
|----------|-------|---------------|
| Code Generation | 5 | merge_intervals, top_k_frequent, LRUCache, Trie, tree serialization |
| File Manipulation | 3 | multi-file rename, CSV pipeline, test writing |
| Debugging | 3 | shared-reference bug, race condition, multi-file dependency |
| Reasoning | 2 | topological sort, state machine |

### External Benchmarks

| Benchmark | Docker | Install | Scoring |
|-----------|--------|---------|---------|
| **SWE-bench Verified** | Yes — official `swebench/sweb.eval.x86_64.*` images | `pip install datasets` | Applies agent patch + test patch in Docker, runs `FAIL_TO_PASS` tests |
| **HumanEval+** | No (subprocess) | `pip install evalplus` | Runs base tests + augmented `plus_input` smoke tests, 30s timeout |
| **TerminalBench** | Yes — builds task Dockerfile | `pip install terminal-bench pyyaml` | Docker build + `docker run` for `run-tests.sh`, compose support |

```bash
pyre benchmarks                                              # List available
pyre run --task-suite swebench --task-limit 30 --generations 5   # SWE-bench
pyre run --task-suite humaneval_plus --task-limit 50              # HumanEval+
```

---

## Example Evolved Agent

`examples/evolved_agent/` contains an agent **produced by a real Prometheus evolution run** — not hand-crafted.

### Evolution Results

| Generation | Config | Accuracy | Key Mutations |
|------------|--------|----------|---------------|
| 0 (seed) | `seed` | 7/13 (54%) | — |
| 1 | `36ea3d1c` | 7/13 (54%) | Enhanced system prompt, increased max_tokens |
| 2 | **`068a779a`** | **12/13 (92%)** | Added syntax validation, `check_syntax` tool, IMPORTANT REMINDERS |

The winning mutation analyzed eval failures (agent writing prose into `.py` files) and evolved 3 targeted fixes:
1. **`_validate_python_content()`** — rejects prose/markdown before writing `.py` files using `compile()` + pattern detection
2. **`check_syntax` tool** — lets the agent verify Python files after writing
3. **Prompt engineering** — "IMPORTANT REMINDERS" block preventing markdown in code files

**Model**: `claude-sonnet-4-6` (for both agent execution and mutation). **Run**: 3 generations, beam_size=2.

### Try it

```bash
cd examples/evolved_agent
pip install -e .
agent run --prompt "Write a merge_intervals function" \
    --workspace /tmp/ws --api-key $KEY --model claude-sonnet-4-6

# Or via Docker
docker build -t evolved-agent .
docker run --rm -v /tmp/ws:/workspace \
    -e OPENAI_API_KEY=$KEY \
    evolved-agent --prompt "Fix the bug" \
    --workspace /workspace --model gpt-4o
```

See `examples/evolved_agent/lineage.json` for the full evolution tree.

---

## Output

### Code Mode

```
runs/<run_id>/
├── config.json                # Experiment parameters
├── events.jsonl               # All eval results, generations, failures
├── checkpoint_gen0000.json    # Best agent at generation 0
├── checkpoint_gen0001.json
└── best_agent/                # Standalone agent package
    ├── pyproject.toml
    ├── Dockerfile
    └── src/agent/
```

The `best_agent/` directory is a complete, runnable project:

```bash
cd runs/<run_id>/best_agent
pip install -e .
agent run --prompt "Solve this" --workspace /tmp/ws --api-key $KEY --model gpt-4o
```

---

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `config` | `config` or `code` |
| `--stage` | `1` | Code evolution stage: `1`/`2`/`3` |
| `-m, --model` | `claude-sonnet-4-20250514` | Model name |
| `-g, --generations` | `20` | Evolution generations |
| `-k, --beam-size` | `5` | Top-K candidates per generation |
| `--mutations-per-parent` | `3` | Mutations per parent |
| `-o, --output-dir` | `runs` | Output directory |
| `--api-format` | `anthropic` | `anthropic` or `openai` |
| `--base-url` | — | Custom API base URL |
| `--api-key` | — | API key (or env var) |
| `-t, --task-suite` | `default` | Task suite: `default`, `swebench`, `humaneval_plus`, `terminal_bench` |
| `--token-budget` | `50000` | Token budget for efficiency scoring |
| `--dry-run` | — | Simulate without API calls |
| `--task-limit` | — | Max tasks to load |

---

## Project Structure

```
src/prometheus/
├── cli.py                  # pyre CLI (Typer)
├── api_clients.py          # Anthropic + OpenAI with tool execution
├── config/                 # HarnessConfig + ExperimentConfig
├── eval/
│   ├── tasks/              # 13 built-in eval tasks
│   ├── benchmarks/         # SWE-bench, HumanEval+, TerminalBench adapters
│   ├── runner.py           # Config-mode evaluation
│   ├── scorer.py           # accuracy × efficiency scoring
│   └── sandbox.py          # Workspace isolation
├── evolution/              # Config evolution (--mode config)
├── code_evolution/         # Code evolution (--mode code)
│   ├── package.py          # AgentPackage dataclass
│   ├── seed.py             # Seed agent source files
│   ├── mutator.py          # LLM-guided code mutation
│   ├── builder.py          # Docker image builder
│   ├── runner.py           # Docker-based evaluation
│   └── loop.py             # Beam-search loop
├── logging/                # JSONL events + checkpoints
└── analysis/               # Cross-run comparison
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/test_prometheus/ -v   # 144 tests, ~4s
ruff check src/prometheus/
mypy src/prometheus/
pyre run --dry-run --generations 2 --beam-size 1
```

---

## Reference

The `reference/` directory contains an archived copy of the original [OpenHarness](https://github.com/HKUDS/OpenHarness) agent — preserved as a read-only design baseline.

## License

MIT — see [LICENSE](reference/LICENSE).
