# Prometheus

**Let each base model evolve its own optimal agent harness — instead of hand-designing one-size-fits-all scaffolding.**

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/tests-144_passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/CLI-pyre-orange" alt="CLI">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
</p>

Prometheus evolves agent harnesses through beam-search mutation and evaluation. It has two modes:

- **Config mode** (`--mode config`) — evolves the harness configuration (system prompt, workflow, tools, parameters)
- **Code mode** (`--mode code`) — evolves the entire agent codebase (Python source files), producing a standalone, pip-installable, Docker-buildable agent package each generation

---

## Setup

### Prerequisites

- Python 3.10+ (3.11 recommended)
- Docker (required for `--mode code` and containerized runs)

### Install

```bash
git clone https://github.com/DTennant/Prometheus.git
cd Prometheus

# Install the package
pip install -e .

# Install with dev tools (for testing/linting)
pip install -e ".[dev]"
```

Verify the installation:

```bash
pyre --help
pytest tests/test_prometheus/ -q   # 144 tests should pass
```

---

## Quick Start

### 1. Dry Run (no API key needed)

```bash
# Config evolution — evolves JSON configs
pyre run --dry-run --generations 5 --beam-size 3

# Code evolution — evolves Python agent codebases
pyre run --mode code --dry-run --generations 3 --beam-size 2
```

### 2. Real Evolution with an API

```bash
# With Anthropic
export ANTHROPIC_API_KEY=sk-...
pyre run --model claude-sonnet-4-20250514 --generations 10

# With OpenAI
export OPENAI_API_KEY=sk-...
pyre run --api-format openai --model gpt-4o --generations 10

# With any OpenAI-compatible provider (LiteLLM, vLLM, Ollama, etc.)
pyre run --api-format openai \
    --base-url https://your-proxy.com/v1/ \
    --api-key your-key \
    --model your-model \
    --generations 10
```

### 3. Code Evolution with Docker

Code mode builds and runs each evolved agent inside a Docker container:

```bash
# Build the Prometheus Docker image
docker build -t prometheus-evolution \
    --build-arg UID="$(id -u)" \
    --build-arg GID="$(id -g)" .

# Run code evolution in Docker (with LiteLLM example)
docker run --rm \
    -v "$(pwd)/runs:/app/runs" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    --group-add "$(stat -c '%g' /var/run/docker.sock)" \
    --network host \
    -e OPENAI_API_KEY="$YOUR_API_KEY" \
    prometheus-evolution \
    run --mode code \
    --api-format openai \
    --base-url https://your-proxy.com/v1/ \
    --model gpt-4.1-mini \
    --generations 3 --beam-size 2
```

Or use the convenience script:

```bash
export LITELLM_API_KEY=your-key
export LITELLM_BASE_URL=https://your-proxy.com/v1/
./run_evolution.sh
```

---

## How It Works

```
seed → evaluate on tasks → LLM sees failures → mutate → re-evaluate → keep top-K → repeat
```

### Config Mode

Evolves a `HarnessConfig` JSON object controlling:

| Field | Controls |
|-------|----------|
| `system_prompt` | Full instructions given to the agent |
| `tool_descriptions` | How each tool is described to the model |
| `workflow.phases` | Multi-phase execution (planning → execution → verification) |
| `parameters` | max_iterations, temperature, timeout, retry |
| `custom_tools` | Composite tools built from base tools |
| `few_shot_examples` | Task/solution pairs injected into prompts |

The base tools (`read_file`, `write_file`, `list_directory`, `execute_command`), eval tasks, and model weights are immutable.

### Code Mode

Evolves a complete Python agent package:

```
seed_agent/
├── pyproject.toml      # pip-installable
├── Dockerfile          # Docker-buildable
└── src/agent/
    ├── cli.py          # CLI entry point
    ├── agent.py        # LLM conversation loop + tool execution
    └── tools.py        # Tool implementations
```

The LLM mutator reads all source files, receives eval results (which tasks passed/failed with error details), and returns a list of file modifications. Each mutation can add tools, change the conversation loop, improve error handling, adjust prompting — anything in the source code.

Each candidate is built into a Docker image, run against all eval tasks in isolated containers, and scored on the host.

### Eval Suite

13 tasks across 4 categories, scored by `accuracy × (budget / tokens_used)`:

| Category | Tasks | What they test |
|----------|-------|---------------|
| Code Generation | 5 | merge_intervals, top_k_frequent, LRUCache, Trie, serialize/deserialize tree |
| File Manipulation | 3 | multi-file rename/refactor, CSV pipeline, test writing |
| Debugging | 3 | shared-reference corruption, race condition, multi-file dependency |
| Reasoning | 2 | topological sort, state machine |

Each task runs the agent in a sandboxed workspace and validates results via subprocess test execution.

---

## CLI Reference

```
pyre run          Run the evolution loop
pyre eval-only    Evaluate a single harness config
pyre compare      Compare multiple evolution runs
pyre show         Display results from a completed run
pyre benchmarks   List available benchmark suites
```

### `pyre run`

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `config` | Evolution mode: `config` or `code` |
| `-m, --model` | `claude-sonnet-4-20250514` | Model name |
| `-g, --generations` | `20` | Number of evolution generations |
| `-k, --beam-size` | `5` | Top-K candidates kept per generation |
| `--mutations-per-parent` | `3` | Mutations generated per parent |
| `-o, --output-dir` | `runs` | Output directory |
| `--api-format` | `anthropic` | API format: `anthropic` or `openai` |
| `--base-url` | — | Custom API base URL |
| `--api-key` | — | API key (or use env var) |
| `-t, --task-suite` | `default` | Task suite name |
| `--token-budget` | `50000` | Token budget for efficiency scoring |
| `--dry-run` | — | Simulate without API calls |
| `--resume` | — | Resume from checkpoint |
| `--seed-config` | — | Custom seed config JSON |
| `--task-limit` | — | Max tasks to load |

### Examples

```bash
# Quick config evolution test
pyre run --dry-run --generations 3 --beam-size 2

# Full code evolution with DeepSeek
pyre run --mode code \
    --api-format openai \
    --base-url https://api.deepseek.com \
    --api-key sk-... \
    --model deepseek-chat \
    --generations 10 --beam-size 3

# Evaluate an existing config
pyre eval-only runs/<run_id>/best_config.json --dry-run

# Compare two runs
pyre compare runs/<run1> runs/<run2>
```

---

## Output

### Config Mode

```
runs/<run_id>/
├── config.json                # Experiment parameters
├── events.jsonl               # All eval results, generations, failures
├── checkpoint_gen0000.json    # Best config at generation 0
├── checkpoint_gen0001.json    # Best config at generation 1
└── best_config.json           # Final best harness config
```

### Code Mode

```
runs/<run_id>/
├── config.json
├── events.jsonl
├── checkpoint_gen0000.json    # Best package manifest at generation 0
├── checkpoint_gen0001.json
└── best_agent/                # Standalone agent package
    ├── pyproject.toml
    ├── Dockerfile
    └── src/agent/
        ├── cli.py
        ├── agent.py
        └── tools.py
```

The `best_agent/` directory is a complete, runnable Python project:

```bash
cd runs/<run_id>/best_agent

# Install and run directly
pip install -e .
agent run --prompt "Write hello world" --workspace /tmp/test --api-key $KEY --model gpt-4o

# Or build and run as Docker container
docker build -t my-evolved-agent .
docker run --rm -v /tmp/ws:/workspace \
    -e OPENAI_API_KEY=$KEY \
    my-evolved-agent \
    --prompt "Solve this task..." \
    --workspace /workspace \
    --model gpt-4o
```

---

## Project Structure

```
src/prometheus/
├── cli.py                      # pyre CLI (Typer)
├── api_clients.py              # Anthropic + OpenAI clients with tool execution
├── config/                     # HarnessConfig + ExperimentConfig
├── eval/                       # Task evaluation pipeline
│   ├── tasks/                  # 13 built-in eval tasks
│   ├── benchmarks/             # External benchmark adapters (SWE-bench, HumanEval+, TerminalBench)
│   ├── runner.py               # Config-mode evaluation orchestrator
│   ├── scorer.py               # Composite scoring (accuracy × efficiency)
│   └── sandbox.py              # Workspace isolation
├── evolution/                  # Config evolution (--mode config)
│   ├── seed.py                 # Minimal seed config
│   ├── mutator.py              # LLM-guided config mutation
│   ├── selector.py             # Beam selection with deduplication
│   ├── history.py              # Evolution history tracking
│   └── loop.py                 # Main evolution loop
├── code_evolution/             # Code evolution (--mode code)
│   ├── package.py              # AgentPackage dataclass
│   ├── seed.py                 # Seed agent source files
│   ├── mutator.py              # LLM-guided code mutation (file operations)
│   ├── builder.py              # Docker image builder with caching
│   ├── runner.py               # Docker-based agent evaluation
│   ├── selector.py             # Content-hash deduplication
│   ├── history.py              # Code evolution history
│   └── loop.py                 # Code evolution loop
├── logging/                    # JSONL event logger + checkpoints
├── tools/                      # Composite tool factory
└── analysis/                   # Cross-run comparison
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (144 tests, ~4s)
pytest tests/test_prometheus/ -v

# Lint
ruff check src/prometheus/

# Type check
mypy src/prometheus/

# Quick dry-run to verify everything works
pyre run --dry-run --generations 2 --beam-size 1
```

### Adding Eval Tasks

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
            expected_output="",
            setup_files={"starter.py": "# starting code"},
        )]

    def score(self, instance: TaskInstance, workspace: Path, agent_output: str) -> TaskResult:
        passed = "expected" in agent_output
        return TaskResult(instance.instance_id, passed, 1.0 if passed else 0.0, 0, 0.0, agent_output)
```

Register it in `eval/tasks/__init__.py`.

---

## Reference

The `reference/` directory contains an archived copy of the original [OpenHarness](https://github.com/HKUDS/OpenHarness) agent harness — preserved as a read-only design baseline for comparison experiments. Prometheus does not import from it.

## License

MIT — see [LICENSE](reference/LICENSE).
