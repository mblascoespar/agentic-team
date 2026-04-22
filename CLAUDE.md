# agentic-team

Multi-agent system where user ideas flow through a DAG of agents, each producing a versioned artifact. Engine enforces artifact lifecycle (draft → approved), schema validation, and reference resolution.

## Key locations

| Path | Purpose |
|------|---------|
| `engine/mcp_server.py` | MCP tool registration and routing |
| `engine/tool_handler.py` | Core artifact CRUD logic |
| `engine/renderer.py` | Artifact rendering utilities |
| `engine/schemas/` | JSON schemas per artifact type (see `docs/index/schema-map.md`) |
| `engine/tests/` | Invariant, lifecycle, contract, renderer tests |
| `.claude/commands/` | Agent system prompts (slash commands) |
| `artifacts/` | Versioned outputs: `<slug>/<stage>/v<n>.json` |
| `.mcp.json` | MCP server registration |
| `docs/index/` | Concise AI-navigation docs (read these first) |

## Task routing

| Problem area | Where to look |
|-------------|--------------|
| Schema validation / field errors | `docs/index/schema-map.md` → then target file |
| Version chain / approval / status | `engine/tool_handler.py` + `docs/index/invariants.md` |
| Rendering output wrong | `engine/renderer.py` |
| MCP tool missing / misrouted | `engine/mcp_server.py` + `.mcp.json` |
| Test failures | `engine/tests/` + `docs/index/tests.md` |

## Read protocol

1. Read `docs/index/` files first — they cover flows, invariants, and file map concisely.
2. Inspect symbols (grep/glob) before opening full files.
3. Read minimum viable scope — a function, not a module.
4. Summarize what you found before editing.

## Expensive files — do not load unless required

- `docs/architecture.md` — full living architecture doc; load only when redesigning a subsystem
- `engine/tool_handler.py` — large core file; grep for the specific handler before opening

## Rules

- Preserve artifact semantics: slug immutable, version monotonic, status transitions one-way.
- Prefer the smallest safe edit. No refactors bundled with bug fixes.
- Do not load `docs/architecture.md` unless the task explicitly requires architectural context.
- After any behavior change, update `docs/index/` files that describe it before reporting done.

## Available MCP tools (all agents)

- `get_available_artifacts` — query artifacts by DAG stage (`"brief"`, `"prd"`, `"domain"`, `"design"`, `"tech_stack"`). Call at session start when no argument provided.
- `read_artifact` — read artifact by `slug`, `stage`, optional `version` (defaults to latest). Do not use file tools to read artifacts.
