# reference/openharness/

Full agent harness — 28 submodules, ~230 Python files. The `oh` CLI.

## STRUCTURE

```
openharness/
├── engine/         # Agent loop: query → stream → tool-call → result → loop
├── tools/          # 43 tools (file I/O, shell, search, web, MCP, agents, tasks, cron)
├── swarm/          # Multi-agent: mailbox, registry, backends, worktrees
├── coordinator/    # Agent definitions: system prompts with behavioral constraints
├── services/       # Compact (context compression), LSP (AST-based), sessions
├── prompts/        # System prompt assembly + CLAUDE.md discovery
├── permissions/    # Multi-level safety: default/auto/plan modes
├── hooks/          # PreToolUse/PostToolUse lifecycle events
├── plugins/        # Plugin system (commands, hooks, agents, MCP servers)
├── skills/         # On-demand .md knowledge loading
├── memory/         # MEMORY.md persistent cross-session knowledge
├── tasks/          # Background task manager (local_bash / local_agent)
├── commands/       # 54 slash commands (/help, /commit, /plan, /resume, ...)
├── config/         # Multi-layer settings with migrations
├── mcp/            # Model Context Protocol client
├── api/            # Anthropic + OpenAI API clients with streaming
├── bridge/         # Cross-process agent communication
├── ui/             # Backend host + React TUI launcher
├── state/          # Runtime state management
├── types/          # Shared type definitions
├── utils/          # Shared utilities
├── keybindings/    # Keyboard shortcut registry
├── output_styles/  # Text/JSON/stream-JSON formatters
├── vim/            # Vim mode support
└── voice/          # Voice input support
```

## KEY PATTERNS

- **Agent identity**: `name@team` format enforced throughout swarm/
- **Environment-based discovery**: agents read `CLAUDE_CODE_TEAM_NAME`, `CLAUDE_CODE_AGENT_ID` from env
- **Atomic file I/O**: `.tmp` → `os.rename` pattern everywhere (mailbox, team.json, permissions)
- **LLM prompts as module constants**: coordinator/ and services/compact/ bake prompts as top-level strings
- **Sub-packages as single files**: `services/compact/__init__.py` (492 lines), `services/lsp/__init__.py` (216 lines)

## ANTI-PATTERNS (REFERENCE CODE)

- `coordinator/agent_definitions.py` contains CRITICAL/NEVER/ALWAYS blocks — these are runtime LLM constraints, not code warnings
- `services/compact/__init__.py` line 156: `CRITICAL: Respond with TEXT ONLY` — compaction runs model tool-free
- `prompts/system_prompt.py`: `IMPORTANT: You must NEVER generate or guess URLs` — anti-hallucination guard
- `services/lsp/` is Python-only AST parsing, not a real language server
- `services/oauth/` is an empty stub
