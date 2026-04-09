# Evolved Agent Example

**This is a hand-crafted example of what a Stage 2 code evolution output
might look like. It was not produced by running the evolution loop.**

It demonstrates the kind of improvements an LLM mutator would accumulate
over ~3 generations of code evolution starting from the seed agent.

## Tools (8)

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `write_file` | Write content to a file |
| `edit_file` | String-replacement editing |
| `list_directory` | List files and subdirectories |
| `search_files` | Grep across multiple file types |
| `execute_command` | Run shell commands (120s timeout) |
| `run_tests` | Run pytest with detailed tracebacks |
| `git_diff` | Show git diff output |

## Workflow: Plan → Execute → Verify

1. **Plan** — Decomposes the task into typed steps with tool hints
2. **Execute** — Runs the tool-call loop with context management,
   error retry (up to 2 retries per tool failure), and step tracking
3. **Verify** — Asks the LLM whether the task is complete;
   continues if work remains

## Usage

```bash
pip install -e .
python -m agent --prompt "Fix the bug in utils.py" \
    --workspace /path/to/repo \
    --api-key $OPENAI_API_KEY \
    --model gpt-4.1-mini
```

## Lineage

See `lineage.json` for the illustrative 3-generation evolution tree.
