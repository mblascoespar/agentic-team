# agentic-team

A production-grade multi-agent system where workflows are modeled as DAGs, each step is a productized capability, and all data flows through versioned artifacts.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Claude Code](https://claude.ai/code) — conversational interface and orchestrator
- Python ≥ 3.10

## Setup

```bash
uv sync
bash install.sh
```

`install.sh` registers the MCP server globally (user scope) and symlinks the agent commands into `~/.claude/commands/agentic-team/`. Run once after cloning. Re-running is safe — it is idempotent. After this, every Claude Code session on your machine has access to the agents and tools, regardless of which project directory you open.

## Running with Claude Code

The system runs entirely through Claude Code. No separate server startup needed.

### 1. Open Claude Code in your project directory

```bash
cd /your/project
claude
```

The MCP server connects automatically. Agent commands are available as `/agentic-team:<command>`.

### 2. Explore the idea (Brainstormer)

```
/agentic-team:brainstorm I want to build a deploy rollback tool for backend engineers
```

Claude runs a competitive scan, challenges the idea one question at a time, presents ≥2 directions with tradeoffs, and waits for you to confirm a direction before drafting. Approve when satisfied — DAG advances to Product Owner.

### 3. Create a PRD (Product Owner)

```
/agentic-team:product-owner <slug>
```

Claude reads the approved Brief and runs its own challenge loop — one question at a time — before drafting. The PRD declares the problem archetype (`domain_system`, `data_pipeline`, `system_integration`, `process_system`, or `system_evolution`). The engine routes the slug to the correct model stage. Approve when satisfied.

### 4. Model the problem (Model Agent)

The command depends on the archetype declared in the approved PRD:

| Archetype | Command | Produces |
|---|---|---|
| `domain_system` | `/model-domain <slug>` | Bounded-context domain model |
| `data_pipeline` | `/model-data-flow <slug>` | Data flow model |
| `system_integration` | `/model-system <slug>` | System integration model |
| `process_system` | `/model-workflow <slug>` | Workflow model |

Each agent is a specialist for its problem type. It challenges in plain business language, translates internally into the correct model structure, and drafts on signal. Approve when satisfied — DAG advances to Architecture Agent.

### 5. Design the architecture (Architecture Agent)

The command depends on the archetype:

| Archetype | Command |
|---|---|
| `domain_system` | `/agentic-team:architecture-domain-system <slug>` |
| `system_evolution` | `/agentic-team:architecture-system-evolution <slug>` |
| `data_pipeline` | `/agentic-team:architecture-data-pipeline <slug>` _(stub)_ |
| `system_integration` | `/agentic-team:architecture-system-integration <slug>` _(stub)_ |
| `process_system` | `/agentic-team:architecture-process-system <slug>` _(stub)_ |

Claude reads the approved model, derives architectural decisions, and challenges you only on inputs it cannot derive (NFRs, compliance, deployment constraints). Approve when satisfied — DAG advances to Tech Stack Agent.

### 6. Choose the tech stack (Tech Stack Agent)

```
/agentic-team:tech-stack-agent <slug>
```

Claude reads the approved design artifact, identifies which technology decision dimensions apply, and runs sequential per-decision deliberation — 2–3 candidates with honest tradeoffs, constraint capture, confirmed choice — one decision at a time. Approve when the full tech stack is correct.

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
│       ├── brainstorm.md                    # /agentic-team:brainstorm
│       ├── product-owner.md                 # /agentic-team:product-owner
│       ├── model-domain.md                  # /agentic-team:model-domain (domain_system)
│       ├── model-data-flow.md               # /agentic-team:model-data-flow (data_pipeline)
│       ├── model-system.md                  # /agentic-team:model-system (system_integration)
│       ├── model-workflow.md                # /agentic-team:model-workflow (process_system)
│       ├── model-evolution.md               # /agentic-team:model-evolution (system_evolution)
│       ├── architecture-domain-system.md    # /agentic-team:architecture-domain-system
│       ├── architecture-system-evolution.md # /agentic-team:architecture-system-evolution
│       ├── architecture-data-pipeline.md    # stub
│       ├── architecture-system-integration.md # stub
│       ├── architecture-process-system.md   # stub
│       └── tech-stack-agent.md              # /agentic-team:tech-stack-agent
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
