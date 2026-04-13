# agentic-team

A production-grade multi-agent system where workflows are modeled as DAGs, each step is a productized capability, and all data flows through versioned artifacts.

## DAG Nodes

| Node | Input | Output |
|------|-------|--------|
| Brainstormer Agent | user idea | Brief artifact |
| Product Agent | Brief (approved) | PRD artifact |
| Domain Agent | PRD | Domain Model artifact |
| Architecture Agent | Domain Model | Design artifact |
| Tech Stack Agent | Design | Tech Stack artifact |
| Execution Agent | Tech Stack | Code + Tests |
| Evaluation Agent | any artifact | quality signals |

## Key files

- `design/` — capability design docs
- `.claude/commands/` — agent system prompts (slash commands)
- `engine/` — Python implementation (tool handler, renderer, MCP server)
- `artifacts/` — versioned output artifacts (`<slug>/brief/v<n>.json`, `<slug>/prd/v<n>.json`, `<slug>/domain/v<n>.json`, `<slug>/design/v<n>.json`, `<slug>/tech_stack/v<n>.json`, …)
- `.mcp.json` — MCP server registration

## Available MCP tools (all agents)

- `get_available_artifacts` — query in-progress, approved, and ready-to-start artifacts for a DAG stage. Required parameter: `stage` (`"brief"`, `"prd"`, `"domain"`, `"design"`, or `"tech_stack"`). Call at session start when no argument is provided to populate the opening menu.
- `read_artifact` — read the full content of an artifact by `slug`, `stage`, and optional `version` (defaults to latest). Use this to load an existing artifact before entering refinement mode. Do not use Claude Code file tools to read artifacts.
