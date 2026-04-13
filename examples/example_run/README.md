# Example Evolution Run

This directory contains the complete output of a real Prometheus code evolution run.

## Run Configuration

- **Model**: `claude-sonnet-4-6` (via LiteLLM, OpenAI-compatible API)
- **Generations**: 3
- **Beam size**: 2
- **Mutations per parent**: 1
- **Eval suite**: 13 built-in tasks (code generation, debugging, file manipulation, reasoning)
- **Environment**: Docker-in-Docker (Prometheus in container, agents in nested containers)

## Results

| Generation | Best Config | Accuracy | Composite Score |
|------------|-------------|----------|-----------------|
| 0 (seed)   | `seed`      | 7/13 (54%) | 0.0862 |
| 1          | `36ea3d1c`  | 7/13 (54%) | 0.0913 |
| 2          | **`068a779a`** | **12/13 (92%)** | **0.1384** |

## What Evolution Changed

The winning mutation (`068a779a`, generation 2) analyzed eval failures and made targeted improvements:

1. **Added `_validate_python_content()`** — rejects prose/markdown before writing `.py` files
2. **Added `check_syntax` tool** — Python syntax verification via `compile()` + AST
3. **Added "IMPORTANT REMINDERS"** — prompt block preventing markdown in code files
4. **Increased `max_tokens`** from 4096 to 8192
5. **Enhanced tool descriptions** — `write_file` warns about Python-only content

## Files

| File | Description |
|------|-------------|
| `config.json` | Experiment parameters |
| `events.jsonl` | All 91 eval events (59 passes, 32 failures) |
| `checkpoint_gen0000.json` | Seed agent (generation 0) |
| `checkpoint_gen0001.json` | Generation 1 best (same accuracy as seed) |
| `checkpoint_gen0002.json` | Generation 2 best — the **winning mutation** |
| `best_agent/` | Standalone agent package (the winner, pip-installable + Docker-buildable) |

## Try the Evolved Agent

```bash
cd best_agent
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

## Reproduce

```bash
docker build -t prometheus-evolution --build-arg UID="$(id -u)" --build-arg GID="$(id -g)" .
docker run --rm \
    -v "$(pwd)/runs:/app/runs" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    --group-add "$(stat -c '%g' /var/run/docker.sock)" \
    --network host \
    -e OPENAI_API_KEY="$KEY" \
    prometheus-evolution run --mode code \
    --api-format openai --base-url https://your-proxy/v1/ \
    --model claude-sonnet-4-6 \
    --generations 3 --beam-size 2 --mutations-per-parent 1
```
