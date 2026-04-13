# Evolved Agent Example

This agent was **produced by a real Prometheus evolution run** — not hand-crafted.

## Lineage

- **Seed**: 7 tools, 17K bytes, 54% accuracy (7/13 tasks)
- **Gen 1** (`36ea3d1c`): Prompt improvements, 54% accuracy
- **Gen 2** (`068a779a`): **This agent** — 8 tools, 23K bytes, **92% accuracy (12/13 tasks)**

## What Evolution Changed

The LLM mutator (Claude Sonnet 4-6) analyzed the seed's eval failures and made targeted improvements:

1. **Added Python syntax validation** — `_validate_python_content()` rejects prose/markdown before writing `.py` files
2. **Added `check_syntax` tool** — uses `compile()` + AST to verify Python files
3. **Enhanced prompts** — "IMPORTANT REMINDERS" block preventing the agent from writing markdown into code files
4. **Increased `max_tokens`** — 4096 → 8192 for longer code generation
5. **Enhanced tool descriptions** — `write_file` warns about Python-only content

## Evolution Run Details

- **Model**: `claude-sonnet-4-6` (both for agent execution and mutation)
- **Generations**: 3 (beam_size=2, mutations_per_parent=1)
- **Eval suite**: 13 built-in tasks (code generation, file manipulation, debugging, reasoning)
- **Environment**: Docker-in-Docker (Prometheus container → agent containers)

## Usage

```bash
# Install
pip install -e .

# Run
agent run --prompt "Write a function..." --workspace /tmp/ws \
    --api-key $KEY --model claude-sonnet-4-6

# Or via Docker
docker build -t evolved-agent .
docker run --rm -v /tmp/ws:/workspace \
    -e OPENAI_API_KEY=$KEY \
    evolved-agent \
    --prompt "Fix the bug in main.py" \
    --workspace /workspace --model gpt-4o
```

## Tools (8)

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `write_file` | Write files with Python syntax validation |
| `edit_file` | String replacement with syntax checking |
| `list_directory` | List directory contents |
| `search_files` | Grep with configurable file patterns |
| `execute_command` | Shell command execution (120s timeout) |
| `run_tests` | Pytest with extra args support |
| `check_syntax` | Python syntax verification via `compile()` |
