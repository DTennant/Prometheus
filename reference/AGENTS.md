# reference/

**READ-ONLY** archived copy of the original OpenHarness agent harness (`oh` CLI). Preserved as a design baseline for Prometheus evolution experiments. ~260 files.

## CRITICAL RULES

- **DO NOT import from this directory** — it is not a dependency of `src/prometheus/`
- **DO NOT modify** — this is a static snapshot of upstream `HKUDS/OpenHarness`
- The only CI pipeline in this repo (`reference/.github/workflows/ci.yml`) belongs here

## STRUCTURE

```
reference/
├── openharness/        # 28-module Python package (the harness)
├── frontend/           # React/Ink TUI (TypeScript)
├── tests/              # 114 unit + integration tests
├── scripts/            # 9 E2E test scripts (manual, need API keys)
├── .github/            # CI: pytest + ruff + tsc
├── docs/               # Showcase, contributing guide
└── assets/             # Logo, screenshots, architecture diagrams
```

## WHAT'S INSIDE

| Module | Purpose | Key detail |
|--------|---------|-----------|
| `openharness/engine/` | Agent loop | Stream → tool-call → loop cycle |
| `openharness/tools/` | 43 built-in tools | Pydantic inputs, Anthropic API schema output |
| `openharness/swarm/` | Multi-agent coordination | File-based mailbox, tmux/subprocess/in-process backends |
| `openharness/services/` | Compaction, LSP, sessions | LLM-powered context compression |
| `openharness/coordinator/` | Agent definitions | System prompts with NEVER/ALWAYS/CRITICAL constraints |
| `openharness/prompts/` | System prompt assembly | CLAUDE.md discovery, skill injection |
| `openharness/permissions/` | Safety layer | Multi-level modes, path rules, command deny lists |
| `openharness/plugins/` | Extension system | Compatible with anthropics/skills + claude-code plugins |
| `frontend/terminal/` | React TUI | Ink 5, 13 components, JSON-lines backend protocol |

## WHY IT EXISTS

Prometheus compares evolved harness configs against this human-designed baseline. The reference harness represents the "human-designed" point in the experiment — what a team of engineers would build by hand.
