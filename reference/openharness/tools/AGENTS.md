# reference/openharness/tools/

43 built-in tools in 42 files. One file = one tool class + one Pydantic input model.

## TAXONOMY

| Category | Tools | Files |
|----------|-------|-------|
| File I/O | Read, Write, Edit, Glob, Grep | 5 |
| Shell | Bash | 1 |
| Search + Intel | WebFetch, WebSearch, LSP (5 ops), ToolSearch | 4 |
| Multi-Agent | Agent, SendMessage, TeamCreate, TeamDelete | 4 |
| Background Tasks | TaskCreate/Get/List/Stop/Output/Update | 6 |
| MCP | McpTool, McpAuth, ListMcpResources, ReadMcpResource | 4 |
| Cron/Remote | CronCreate/List/Delete/Toggle, RemoteTrigger | 5 |
| Workflow | EnterPlanMode, ExitPlanMode, EnterWorktree, ExitWorktree | 4 |
| Meta | Skill, Config, Brief, Sleep, AskUser, TodoWrite, NotebookEdit | 7 |

## CONVENTIONS

- Inherit `BaseTool` from `base.py`; define `name`, `description`, `input_model` class attrs
- `execute()` is async, returns `ToolResult(output=..., is_error=...)`
- `to_api_schema()` outputs Anthropic Messages API format via `model_json_schema()`
- Override `is_read_only()` to bypass permission checks (defaults `False`)
- Register in `__init__.py` → `create_default_tool_registry()`
- Tools are stateless — instantiated once at registry creation, not per-call

## CROSS-MODULE BRIDGES

- `agent_tool.py` → `swarm/registry.py` (only tool that crosses into swarm)
- `task_create_tool.py` → `tasks/manager.py` (background task lifecycle)
- `mcp_tool.py` — dynamically generates Pydantic models from MCP JSON schemas at runtime via `create_model()`

## GOTCHAS

- `bash_tool.py` truncates output at 12,000 chars — not configurable
- `lsp_tool.py` dispatches 5 operations (document_symbol, workspace_symbol, go_to_definition, find_references, hover) — most complex single tool
- MCP tools are registered conditionally, after all built-in tools
