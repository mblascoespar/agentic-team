# Repo map

| Path | Purpose |
|------|---------|
| `engine/mcp_server.py` | Exposes MCP tools; routes calls to tool_handler |
| `engine/tool_handler.py` | All artifact CRUD: write, approve, read, list; enforces lifecycle rules |
| `engine/renderer.py` | Converts raw artifact JSON into rendered output for agent consumption |
| `engine/schemas/` | JSON Schema files per artifact type and sub-type (base, input, mcp, design variants) |
| `engine/tests/` | Test suite: invariants, lifecycle, contracts, renderer |
| `design/` | Human-readable capability design documents (not loaded by agents) |
| `prompts/` | Reusable prompt fragments referenced by agent commands |
| `.claude/commands/` | Per-agent system prompts; invoked as slash commands |
| `artifacts/` | Runtime output; structure: `<slug>/<stage>/v<n>.json` |
| `.mcp.json` | MCP server registration config |
