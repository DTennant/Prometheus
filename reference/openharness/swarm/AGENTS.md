# reference/openharness/swarm/

Multi-agent coordination layer. 10 files, ~4,000 lines. The most stateful module.

## ARCHITECTURE

```
types.py (Protocols + dataclasses)
    ↓
registry.py (BackendRegistry singleton — tmux > subprocess > in_process)
    ↓
in_process.py       subprocess_backend.py
    ↓                       ↓
mailbox.py (file-based async message queue)
    ↓
permission_sync.py (dual-transport permission flow — 1,185 lines, largest file)
    ↓
team_lifecycle.py (TeamFile persistence, session cleanup)
    ↓
worktree.py (per-agent git worktrees, symlink dedup)
    ↓
spawn_utils.py (CLI flag inheritance + env propagation)
```

## KEY PATTERNS

- **Identity**: `name@team` format; agents discover identity from env vars, not args
- **File I/O**: all async via `run_in_executor` + `fcntl.flock` for cross-process safety
- **Mailbox**: `~/.openharness/teams/<team>/agents/<id>/inbox/<ts>_<uuid>.json`
- **Atomic writes**: `.tmp` → `os.rename` everywhere
- **Leader/worker**: absence of `CLAUDE_CODE_AGENT_ID` = leader
- **Cancellation**: `TeammateAbortController` — dual-signal (graceful event + force asyncio cancel)
- **ContextVar isolation**: each `asyncio.create_task()` gets its own `TeammateContext`

## GOTCHAS

- `permission_sync.py` (1,185 lines) handles both file-based AND mailbox-based permission flow — two transports, one module
- `__init__.py` exports 26 symbols but hides `in_process`, `team_lifecycle`, `worktree`, `spawn_utils` — these are internal
- `BackendRegistry` is a singleton via `get_backend_registry()` — not injected
- Env vars: `CLAUDE_CODE_TEAM_NAME`, `CLAUDE_CODE_AGENT_ID`, `CLAUDE_CODE_AGENT_NAME`, `CLAUDE_CODE_AGENT_COLOR`
