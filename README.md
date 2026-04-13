# agentic-team

A production-grade multi-agent system where workflows are modeled as DAGs, each step is a productized capability, and all data flows through versioned artifacts.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Claude Code](https://claude.ai/code) — conversational interface and orchestrator
- Python ≥ 3.10

## Setup

```bash
uv sync
```

## Running with Claude Code

The system runs entirely through Claude Code. No separate server startup needed.

### 1. Start Claude Code in this directory

```bash
claude
```

On startup, Claude Code automatically discovers and connects to the MCP server defined in `.mcp.json`. You should see `product-agent` listed in the available tools.

### 2. Explore the idea (Brainstormer)

```
/brainstorm I want to build a deploy rollback tool for backend engineers
```

Claude runs a competitive scan, challenges the idea one question at a time, presents ≥2 directions with tradeoffs, and waits for you to confirm a direction before drafting. When ready:

```
draft it
```

Claude calls `write_brief` → artifact written to `artifacts/<slug>/brief/v1.json` → rendered Brief shown.

Refine by answering open questions, then approve:

```
approve
```

Claude calls `approve_brief` → `status: "approved"` set. DAG advances to Product Agent.

### 3. Create a PRD (Product Agent)

```
/product-owner <slug>
```

Claude reads the approved Brief and runs its own challenge loop — one question at a time — before drafting. The Brief informs but does not replace the PO's challenge. When ready:

```
draft it
```

Claude calls `write_prd` → artifact written to `artifacts/<slug>/prd/v1.json` → rendered PRD shown.

Refine by answering open questions, then approve:

```
approve
```

Claude calls `approve_prd` → `status: "approved"` set. DAG advances to Domain Agent.

### 4. Model the domain (Domain Agent)

```
/domain-agent <slug>
```

Claude reads the approved PRD, challenges ownership ambiguities, then drafts a bounded-context domain model on signal. Approve when satisfied — DAG advances to Architecture Agent.

### 5. Design the architecture (Architecture Agent)

```
/architecture-agent <slug>
```

Claude reads the approved domain model, derives architectural decisions, and challenges you only on inputs it cannot derive (NFRs, compliance, deployment constraints). Approve when satisfied — DAG advances to Tech Stack Agent.

### 6. Choose the tech stack (Tech Stack Agent)

```
/tech-stack-agent <slug>
```

Claude reads the approved design artifact, identifies which technology decision dimensions apply (API framework, database + ORM, auth, observability, test framework, and optionally message broker), and presents a numbered agenda for confirmation. It then runs **sequential per-decision deliberation** — 2–3 candidates with honest tradeoffs, constraint capture, confirmed choice — one decision at a time. When all decisions are resolved:

```
draft it
```

Claude calls `write_tech_stack` → artifact written to `artifacts/<slug>/tech_stack/v1.json` → rendered Tech Stack shown.

After drafting, any closed decision can be re-opened by name:

```
let's re-open the API framework decision
```

Claude re-enters deliberation for that decision using prior constraints as context. Approve when the full tech stack is correct:

```
approve
```

Claude calls `approve_tech_stack` → `status: "approved"` set. DAG advances to Execution Agent.

### 7. Design a new capability

```
/design <what you want to design>
```

Activates the Principal Systems Architect agent with the full DAG design methodology. Every design session produces a **test impact statement** as part of its output — a named list of tests that must be written before the design is considered implemented:

| Design output | Test file |
|---|---|
| New orchestrator-owned field | `test_invariants.py` |
| New handler / versioning behavior | `test_lifecycle.py` |
| New DAG edge | `test_contracts.py` |
| New renderer | `test_renderer.py` |

---

## Running tests

```bash
# Full suite
uv run --group dev pytest

# By type
uv run --group dev pytest -m invariant   # orchestrator field ownership
uv run --group dev pytest -m lifecycle   # v1/v2/approve version chain
uv run --group dev pytest -m contract    # DAG node boundary handoffs
uv run --group dev pytest -m renderer    # artifact-to-text rendering
```

Tests are organized by **what they protect**, not by the file they test. The four types map directly to the four categories in every `/design` session's test impact statement. When a design session ends, the test impact statement tells you exactly which files to update and what to add.

---

## Project structure

```
.
├── CLAUDE.md                      # Project context for Claude Code
├── README.md                      # This file
├── pyproject.toml                 # Python dependencies and pytest config (uv)
├── .mcp.json                      # MCP server registration
│
├── .claude/
│   └── commands/
│       ├── brainstorm.md          # /brainstorm slash command
│       ├── product-owner.md       # /product-owner slash command
│       ├── domain-agent.md        # /domain-agent slash command
│       ├── architecture-agent.md  # /architecture-agent slash command
│       ├── tech-stack-agent.md    # /tech-stack-agent slash command
│       └── design.md              # /design slash command (Systems Architect)
│
├── design/                        # Capability design documents
│   ├── brainstorm-agent.md        # Brainstormer: tool schema, artifact schema, session model
│   ├── product-agent.md           # Product Agent: tool schema, artifact schema, session model
│   └── domain-agent.md            # Domain Agent: tool schema, artifact schema, session model
│
├── engine/                        # Python engine: MCP server, handlers, renderers
│   ├── mcp_server.py              # MCP server (exposes all tools to Claude Code)
│   ├── tool_handler.py            # Deterministic artifact write/approve logic
│   ├── renderer.py                # Human-readable artifact formatters
│   └── tests/
│       ├── conftest.py            # Shared fixtures and input factories
│       ├── test_invariants.py     # Orchestrator field ownership enforcement
│       ├── test_lifecycle.py      # v1/v2/approve versioning chain
│       ├── test_contracts.py      # DAG node boundary handoffs
│       └── test_renderer.py       # Artifact-to-text rendering output
│
├── artifacts/                     # Versioned output artifacts
│   └── <slug>/
│       ├── brief/
│       │   └── v1.json
│       ├── prd/
│       │   ├── v1.json
│       │   └── v2.json
│       ├── domain/
│       │   └── v1.json
│       ├── design/
│       │   └── v1.json
│       └── tech_stack/
│           └── v1.json
│
└── docs/
    └── architecture.md            # Living architecture document
```

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the current system architecture, design decisions, and evolution log.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | ≥1.26.0 | MCP server SDK for Claude Code tool integration |
| `jsonschema` | ≥4.0 | Engine-level input validation against tool schemas |
| `pytest` | ≥8.0 | Test runner (dev only) |
