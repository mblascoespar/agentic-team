# Architecture

Living document. Updated as the system evolves.

---

## System Overview

A production-grade multi-agent system where:
- Workflows are modeled as **DAGs** (Directed Acyclic Graphs)
- Each node is a **productized capability** with a clear API
- All data flows through **versioned artifacts**
- **Claude Code** is the conversational interface and orchestrator

---

## DAG

```
[User Idea]
     │
     ▼
┌─────────────────┐
│  Brainstormer   │  idea → Brief artifact            [IMPLEMENTED]
│     Agent       │
└────────┬────────┘
         │ brief.json (approved)
         ▼
┌─────────────────┐
│  Product Agent  │  Brief → PRD artifact             [IMPLEMENTED]
└────────┬────────┘
         │ prd.json (approved)
         ▼
┌─────────────────┐
│  Domain Agent   │  PRD → Domain Model artifact      [IMPLEMENTED]
└────────┬────────┘
         │ domain.json (approved)
         ▼
┌─────────────────┐
│ Architecture    │  Domain Model → Design artifact   [IMPLEMENTED]
│    Agent        │
└────────┬────────┘
         │ design.json (approved)
         ▼
┌─────────────────┐
│ Tech Stack      │  Design → Tech Stack artifact     [IMPLEMENTED]
│    Agent        │
└────────┬────────┘
         │ tech_stack.json (approved)
         ▼
┌─────────────────┐
│ Execution Agent │  Tech Stack → Code + Tests        [NOT YET BUILT]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Evaluation      │  Artifacts → Quality Signals      [NOT YET BUILT]
│    Agent        │
└─────────────────┘
```

Human approval gates at: Brief, PRD, Domain Model, Architecture, Tech Stack.

---

## Interface

**Claude Code** is the interface and session loop. No separate Python orchestrator.
The conversation IS the execution sta11te. No stdin loop, no external process.

---

## Current State: Brainstormer Agent (implemented)

### Responsibilities
Transform a raw user idea into an approved Brief artifact through structured exploration. Runs competitive research, challenges the idea, presents alternatives with tradeoffs, and records the chosen direction with rationale.

### Session model

| Phase | Mechanism | Trigger |
|-------|-----------|---------|
| Context exploration | Read CLAUDE.md, design docs, existing artifacts | Automatic on start |
| Competitive scan | WebSearch for existing solutions | Automatic after context |
| Challenge | One question at a time — purpose, constraints, target user | User responses |
| Alternatives | Present ≥2 directions with tradeoffs; recommend one | Challenge resolved |
| Direction selection | User confirms a direction | "go with option X" or equivalent |
| Complexity assessment | Agent assesses scope + decomposition_needed | Automatic after direction |
| Draft | `write_brief` | User signals readiness |
| Refine | Loop on open_questions | After write_brief returns |
| Approve | `approve_brief` | User signals approval |

Hard gate: `write_brief` is never called until the user has explicitly confirmed a direction.

### Artifact schema

```
artifacts/<slug>/brief/v<n>.json

{
  id: "brief-<uuid>",        stable across versions
  slug: "deploy-rollback",
  version: n,
  parent_version: n-1,
  created_at: <iso8601>,     set once on v1
  updated_at: <iso8601>,     set on every write
  status: "draft" | "approved",
  references: [],            entry node — no upstream artifact
  decision_log: [...],
  content: {
    idea: <verbatim from user>,
    alternatives: [{ description, tradeoffs }],
    chosen_direction: { direction, rationale },
    competitive_scan: <string>,
    complexity_assessment: { scope: "small"|"medium"|"large", decomposition_needed: bool },
    open_questions: [...]
  }
}
```

### MCP tools

| Tool | Input | Action |
|------|-------|--------|
| `get_available_artifacts` | `stage` | Returns in_progress / approved / ready_to_start buckets for that stage |
| `read_artifact` | `slug`, `stage`, `version` (optional) | Returns full artifact JSON. Omit version for latest. Replaces direct file reads. |
| `write_brief` | slug, idea, alternatives, chosen_direction, competitive_scan, complexity_assessment, open_questions | Writes `artifacts/<slug>/brief/v<n>.json`, returns rendered Brief |
| `approve_brief` | `artifact_path` | Sets `status: "approved"` in artifact |

### Brief tenets (what makes a Brief useful)

1. **Rationale on every choice and rejection** — a chosen direction without rationale is noise; rejected alternatives without rationale get re-debated later.
2. **Market-grounded** — `competitive_scan` is not optional flavor text; it anchors the Brief in what already exists and what is different.
3. **One chosen direction, clearly stated** — vague direction means the PO cannot challenge it effectively.
4. **Open questions are PO's first agenda** — whatever the Brainstormer left unresolved, the PO closes first before opening new challenges.
5. **Exploration record, not a spec** — the Brief captures what was considered, not how to build it.

---

## Current State: Product Agent (implemented)

### Responsibilities
Transform an approved Brief artifact into an approved PRD artifact through iterative human-driven challenge and refinement. The Brief informs the PO's challenge — it does not bypass it. The PO reads the Brief to understand what was already explored, then runs its own full challenge loop before drafting.

### Session model

| Phase | Mechanism | Tool call |
|-------|-----------|-----------|
| Challenge | Claude Code conversation (prose) | None |
| Draft | User signals "draft it" | `write_prd` MCP tool |
| Refine | User answers open questions | `write_prd` MCP tool |
| Approve | User signals "approve" | `approve_prd` MCP tool |

### Two-layer continuity

| Layer | Scope | Content |
|-------|-------|---------|
| PRD artifact | Cross-session (durable) | All accumulated refinements |
| Conversation | Within-session (ephemeral) | Discarded after session ends |

The PRD artifact IS the continuity mechanism. Each new session reconstructs full context from the current PRD alone.

### Artifact schema

```
artifacts/<slug>/prd/v<n>.json

{
  id: "prd-<uuid>",          stable across versions
  slug: "deploy-rollback",   2–3 word human-readable folder name
  version: n,
  parent_version: n-1,
  created_at: <iso8601>,
  source_idea: <verbatim>,
  status: "draft" | "approved",
  content: {
    title, problem, target_users, goals,
    success_metrics: [{metric, measurement_method}],
    scope_in, scope_out,
    features: [{name, description, user_story, priority, acceptance_criteria: [...]}],
    assumptions, open_questions
  }
}
```

### MCP tools

| Tool | Input | Action |
|------|-------|--------|
| `get_available_artifacts` | `stage` | Returns in_progress / approved / ready_to_start buckets for that stage |
| `read_artifact` | `slug`, `stage`, `version` (optional) | Returns full artifact JSON. Omit version for latest. Replaces direct file reads. |
| `write_prd` | slug + PRD content fields | Writes `artifacts/<slug>/prd/v<n>.json`, returns rendered PRD. Engine resolves upstream Brief from slug. |
| `approve_prd` | `artifact_path` | Sets `status: "approved"` in artifact |

### Key files

| File | Purpose |
|------|---------|
| `engine/mcp_server.py` | MCP server — exposes all tools to Claude Code |
| `engine/tool_handler.py` | Deterministic artifact write/approve logic; DAG topology (`_UPSTREAM_STAGE`); `find_latest`; `get_available_artifacts` |
| `engine/renderer.py` | Human-readable artifact formatters |
| `.claude/commands/brainstorm.md` | Brainstormer Agent system prompt |
| `.claude/commands/product-owner.md` | Product Agent system prompt — includes archetype classification challenge |
| `.claude/commands/model-domain.md` | Model Agent (domain_system) — DDD specialist, plain-language challenge loop |
| `design/product-agent.md` | Tool schema, artifact schema, session model |

### Test structure

Tests live in `engine/tests/` and are organized by type, not by class under test.
Run a specific type with `pytest -m <mark>`.

| File | Mark | What it tests |
|------|------|---------------|
| `test_invariants.py` | `invariant` | Handler enforces orchestrator ownership of all metadata fields (id, slug, created_at, references, status, content isolation) **and** rejects invalid inputs before any file write (schema validation, slug format, nested field constraints) |
| `test_lifecycle.py` | `lifecycle` | Correct v1/v2/approve versioning chain — structure, file writes, decision log; approve guards (missing file, already approved, path outside artifacts dir) |
| `test_contracts.py` | `contract` | DAG node boundary handoffs — producing node output consumable by consuming node; handoff guards (unapproved PRD, missing PRD file, slug/path mismatch) |
| `test_renderer.py` | `renderer` | Every content field appears in rendered output |

**Scalability rule:** when a new DAG node is implemented, add its handlers to `test_invariants.py` and `test_lifecycle.py` following the existing pattern, and add one new class to `test_contracts.py` for the new edge.

---

---

## Current State: Model Agent (implemented)

### Responsibilities
Transform an approved PRD into the correct model artifact for the problem archetype. One specialist command per archetype — no branching within a command. Engine routes the slug to the correct stage; the command handles exactly that stage.

| Archetype | Command | Stage | Model |
|---|---|---|---|
| `domain_system` | `/model-domain` | `model_domain` | Bounded-context domain model |
| `data_pipeline` | `/model-data-flow` | `model_data_flow` | Data flow model |
| `system_integration` | `/model-system` | `model_system` | System integration model |
| `process_system` | `/model-workflow` | `model_workflow` | Workflow model |

### Session model

| Phase | Mechanism | Tool call |
|-------|-----------|-----------|
| Challenge | Plain business language — DDD translation internal | None |
| Draft | User signals "draft it" | `write_model(slug, model_type, content, decision_log_entry)` |
| Refine | User answers open questions | `write_model` — refinement consistency check before write |
| Schema evolution | Agent discovers missing concept | `update_schema(slug, stage, field_name, kind, description)` |
| Approve | User signals "approve" | `approve_model(artifact_path)` |

### Artifact schema

Schema defined in `engine/schemas/model-<type>.json`. Artifact stored at `artifacts/<slug>/model_<type>/v<n>.json`. Common envelope:

```
id, slug, version, parent_version, created_at, updated_at,
status: "draft" | "approved",
references: ["artifacts/<slug>/prd/v<n>.json"],
decision_log: [...],
content: { <model-type-specific fields> }
```

Instance schema at `artifacts/<slug>/model_<type>/schema.json` — starts from base schema, grows via `update_schema`. Mandatory fields validated at approval time.

### MCP tools

| Tool | Input | Action |
|------|-------|--------|
| `write_model` | `slug`, `model_type`, `content`, `decision_log_entry` | Writes `artifacts/<slug>/model_<type>/v<n>.json`; validates model_type against PRD archetype |
| `approve_model` | `artifact_path` | Validates mandatory schema fields; sets `status: "approved"` |
| `update_schema` | `slug`, `stage`, `field_name`, `kind`, `description` | Adds field to instance schema with decision log entry |

---

## Current State: Tech Stack Agent (implemented)

### Responsibilities
Transform an approved Design artifact into a versioned tech stack artifact through structured human-driven deliberation. The agent identifies technology decision dimensions from design artifact signals, presents a confirmed agenda, runs sequential per-decision deliberation (2–3 candidates, constraint capture, confirmed choice), and drafts a tech stack artifact with full ADR records. Supports re-open of any closed decision post-draft.

### Session model

| Phase | Mechanism | Tool call |
|-------|-----------|-----------|
| Load + identify | Agent reads design artifact, maps sections to decision dimensions | `read_artifact` |
| Agenda confirmation | Agent presents decision list with architectural signals; human confirms | None |
| Sequential deliberation | One decision at a time — candidates, constraints, confirmed choice | None |
| Draft | Human signals "draft it" after all decisions resolved | `write_tech_stack` |
| Re-open | Human names a prior decision; agent re-deliberates using prior constraints | `write_tech_stack` |
| Approve | Human signals "approve" | `approve_tech_stack` |

### Decision dimensions

| Dimension | Design artifact signal |
|---|---|
| API framework | `integration_patterns[*].api_surface_type: REST or GraphQL` |
| Database + ORM | `storage[*].type: relational, document, or event-store` — one per distinct type |
| Message broker | `integration_patterns[*].integration_style: async or api_surface_type: event-driven` |
| Auth library / provider | `cross_cutting.auth` present |
| Observability stack | `cross_cutting.observability` present |
| Test framework | `testing_strategy` has at least one entry |

### Artifact schema

```
artifacts/<slug>/tech_stack/v<n>.json

{
  id: "tech-stack-<uuid>",    stable across versions
  slug: "deploy-rollback",
  version: n,
  parent_version: n-1,
  created_at: <iso8601>,      set once on v1
  updated_at: <iso8601>,      set on every write
  status: "draft" | "approved",
  references: ["artifacts/<slug>/design/v<n>.json"],
  decision_log: [...],
  content: {
    adrs: [{
      decision_point: <string>,
      architectural_signal: <string>,
      candidates: [{ name, tradeoffs }],       minItems: 2
      constraints_surfaced: [...],             may be []
      chosen: <string>,
      rationale: <string>,
      rejections: [{ candidate, rejection_reason }]  minItems: 1, rejection_reason non-empty
    }],
    open_questions: [...]
  }
}
```

### Handler semantic guards

Beyond JSON schema validation, the handler enforces:
- Every `rejection` entry must have non-empty `rejection_reason` (handler-level, with clear error message)

### MCP tools

| Tool | Input | Action |
|------|-------|--------|
| `get_available_artifacts` | `stage: "tech_stack"` | Returns in_progress / approved / ready_to_start buckets |
| `read_artifact` | `slug`, `stage: "tech_stack"`, `version` (optional) | Returns full artifact JSON |
| `write_tech_stack` | slug + adrs + open_questions + decision_log_entry | Writes `artifacts/<slug>/tech_stack/v<n>.json`. Engine resolves upstream design from slug. |
| `approve_tech_stack` | `artifact_path` | Sets `status: "approved"`. Advances DAG to Execution Agent. |

---

## Current State: Architecture Agent (implemented)

### Responsibilities
Transform an approved Domain Model artifact into a structured Design artifact through derivation-first reasoning. The agent applies explicit signal-to-decision rules to derive layering strategy, CQRS applicability, aggregate consistency model, integration patterns, API surface type, storage/persistence, cross-cutting concerns, and layer-level testing strategy from domain model signals. Human input is scoped to NFRs, compliance constraints, deployment constraints, and genuine domain model ambiguities only.

### Session model

| Phase | Mechanism | Tool call |
|-------|-----------|-----------|
| Load + derive | Agent reads domain model, applies derivation rules | `read_artifact` |
| Challenge | NFRs and ambiguities only — one question at a time | None |
| Draft | User signals "draft it" | `write_design` MCP tool |
| Refine | User provides feedback, cascade recomputed | `write_design` MCP tool |
| Approve | User signals "approve" | `approve_design` MCP tool |

### Derivation rules (prompt-encoded, Option A)

All architectural decisions are derived from domain model signals using explicit IF→THEN rules in the system prompt. The derivation order is: layering → CQRS → aggregate consistency → integration patterns → API surface → storage → cross-cutting → testing strategy. Changing layering cascades to CQRS, cross-cutting, and testing strategy.

### Artifact schema

```
artifacts/<slug>/design/v<n>.json

{
  id: "design-<uuid>",         stable across versions
  slug: "deploy-rollback",
  version: n,
  parent_version: n-1,
  created_at: <iso8601>,       set once on v1
  updated_at: <iso8601>,       set on every write
  status: "draft" | "approved",
  references: ["artifacts/<slug>/domain/v<n>.json"],
  decision_log: [...],
  content: {
    layering_strategy: [{context, pattern, cqrs_applied, cqrs_read_models?, rationale}],
    aggregate_consistency: [{context, aggregate, within_aggregate, cross_aggregate_events, rationale}],
    integration_patterns: [{source_context, target_context, relationship_type, integration_style,
                            api_surface_type, acl_needed, translation_approach?, consistency_guarantee, rationale}],
    storage: [{context, aggregate, type, transaction_boundary, rationale}],
    cross_cutting: {
      auth: {authentication_layer, authorization_layer, rationale},
      error_propagation: {domain_exceptions, application_exceptions, infrastructure_exceptions, translation_rules},
      observability: {trace_boundaries, logging_per_layer, metrics_exposure}
    },
    testing_strategy: [{layer, test_type, what_to_test, what_not_to_test}],
    nfrs: [{category, constraint, scope, source}],
    open_questions: [...]
  }
}
```

Every derived decision carries a `rationale` object: `{source_signal, rule_applied, derived_value, override_reason?}`.

### MCP tools

| Tool | Input | Action |
|------|-------|--------|
| `get_available_artifacts` | `stage: "design"` | Returns in_progress / approved / ready_to_start buckets |
| `read_artifact` | `slug`, `stage: "design"`, `version` (optional) | Returns full artifact JSON |
| `write_design` | slug + design content fields | Writes `artifacts/<slug>/design/v<n>.json`, returns rendered design. Engine resolves upstream domain model from slug. |
| `approve_design` | `artifact_path` | Sets `status: "approved"` in artifact. Advances DAG to Execution Agent. |

### Handler-level guards

Beyond JSON schema validation, the handler enforces:
- `acl_needed=true` requires non-empty `translation_approach`
- `cqrs_applied=true` requires non-empty `cqrs_read_models`

---

## Key Design Decisions

### Engine-owned validation (not API-level)
**Decision:** The tool handler validates all inputs — full schema structure, slug format, PRD file existence, PRD approval status, slug/path consistency, approve path containment — before writing any artifact.
**Why:** Validation is deterministic work and belongs in the engine. `strict: true` in the tool schema is a UX hint for the agent, not an enforcement mechanism. The engine must be correct regardless of which caller invokes it.
**Tradeoff:** Some checks are duplicated between the schema definition and the handler. Acceptable because the schema is loaded at runtime to drive `jsonschema.validate`, so a schema change automatically updates validation — no separate validation code to maintain.
**Error contract:** Handlers raise `ValueError` with actionable messages. MCP `call_tool` catches `ValueError` and returns it as `TextContent` so the agent can correct and retry.

### Claude Code as interface (not a Python CLI)
**Decision:** Use Claude Code conversation as the session loop.
**Why:** The back-and-forth exchange IS the challenge/refinement loop. No stdin needed.
**Tradeoff:** Tied to Claude Code as the interface. A headless/API mode would need a separate entry point.

### Forced tool call (`tool_choice: write_prd`)
**Decision:** Agent always calls `write_prd` when drafting — no free-form prose output.
**Why:** Guarantees structured artifact on every invocation. Schema validation at API level.
**Tradeoff:** Incompatible with extended thinking mode.

### Slug agent-generated
**Decision:** Agent provides the `slug` field (2–3 word folder name) on first write.
**Why:** Agent understands the idea; mechanical title truncation produces poor results.
**Tradeoff:** Agent could change slug across versions — tool handler must enforce preservation.

### Single artifact file per version
**Decision:** Each version is a complete snapshot (`v1.json`, `v2.json`…), not a diff.
**Why:** Enables recomputation from any version. Simpler to read and debug.
**Tradeoff:** Larger storage footprint than diff-based versioning.

### open_questions as cross-session signal
**Decision:** `open_questions` in the PRD is how the agent signals "where we left off."
**Why:** The messages array is ephemeral (session-scoped). The artifact must carry all state.
**Tradeoff:** Relies on prompt guidance to correctly populate; not structurally enforced.

### DAG topology is engine-private; agents work in slugs only
**Decision:** The DAG edge ordering (`_UPSTREAM_STAGE`) lives exclusively in `tool_handler.py`. It is never exposed in any API response or agent prompt. Agents pass only a `slug` to `write_*` tools; the engine resolves the upstream artifact path internally using `find_latest(slug, upstream_stage, status="approved")`.
**Why:** Path resolution is topology knowledge. Encoding it in agent prompts duplicates it N times and makes every prompt a maintenance surface for DAG structure changes. The engine is the right owner.
**Consequence:** `brief_path` removed from `write_prd` input schema; `prd_path` removed from `write_domain_model` input schema. `references` is now always engine-populated. PRD `references` field was previously always `[]` — this is also fixed.
**Tradeoff:** The engine must read upstream artifacts on every `write_*` v1 call to derive the reference. This is a trivial I/O cost; correctness is the priority.

### `get_available_artifacts` — DAG state query
**Decision:** A single MCP tool that, given a `stage`, returns three buckets: `in_progress` (draft artifacts at that stage), `approved` (approved artifacts), and `ready_to_start` (slugs where upstream is approved but this stage has no artifact yet).
**Why:** Every agent's no-argument entry point needs to show the human what's actionable. Previously each agent did ad-hoc globbing in its prompt — topology knowledge scattered across N prompts. The tool centralises discovery. Agents call it once and render the result; they add no topology logic of their own.
**Tradeoff:** Agents still format the result for display — that's display logic, not topology. The brief stage never has `ready_to_start` entries (it is the entry node); the tool returns an empty list, which agents omit from display.

### Agent tool scope: MCP-only for artifact access
**Decision:** Agent prompts are scoped to MCP tools only for all artifact reads and writes. The tools are: `get_available_artifacts`, `read_artifact`, `write_*`, `approve_*`. Claude Code file tools (Read, Glob, Write, Bash) are not used by agents for artifact operations.
**Why:** Agents going around the MCP layer to read files directly bypass the engine's validation, path resolution, and error contracts. It also makes the agent's surface area unpredictable — any file on disk becomes accessible.
**Ad-hoc exceptions:** If an agent genuinely needs a file operation outside the MCP layer (e.g. reading a design doc for context), it must be granted explicitly in the session, not baked into the prompt.
**Consequence:** `read_artifact(slug, stage, version?)` was added as the MCP-native replacement for direct `Read` calls against artifact files.

### /product-owner resume mechanism (argument polymorphism)
**Decision:** Single command handles creation, resume-by-path, resume-by-slug, and no-arg scan. Argument type is detected at runtime by the command prompt.
**Why:** Single command is more ergonomic. Detection is unambiguous: paths match `artifacts/*/v*.json`, slugs match existing artifact folders, everything else is an idea. No-arg lists existing drafts with "new idea" as last option — avoids silent creation when drafts exist.
**Tradeoff:** No new tools, no artifact schema changes — all routing lives in the command prompt. Relies on Claude Code's ability to glob/read at session start.

---

## Cross-Cutting Artifact Conventions

All artifacts in the system share these fields and semantics. Every new artifact schema must conform.

### Required metadata fields (orchestrator-owned)

| Field | Type | Semantics |
|---|---|---|
| `id` | string | Stable across all versions (`<type>-<uuid>`). Identifies the artifact, not the version. |
| `slug` | string | Human-readable folder name. Set on v1, never changed. Must match `^[a-z0-9][a-z0-9-]*[a-z0-9]$` (lowercase, min 2 chars, hyphens allowed, no leading/trailing hyphens). |
| `version` | int | Increments on every write. |
| `parent_version` | int \| null | `null` on v1; prior version number on all subsequent writes. |
| `created_at` | iso8601 | Set on v1. **Carried forward unchanged** on all subsequent versions. Artifact origin timestamp. |
| `updated_at` | iso8601 | Set on every write. Snapshot timestamp. |
| `status` | string | `"draft"` on agent write; `"approved"` on explicit human approval. |
| `references` | array | Explicit paths of upstream artifacts this artifact was derived from. Entry node artifacts use `[]`. |
| `decision_log` | array | Append-only log of decisions. See schema below. |

### decision_log entry schema

```json
{
  "version": 2,
  "timestamp": "<iso8601>",
  "author": "agent:<agent-name> | human",
  "trigger": "initial_draft | human_feedback | open_question_resolved | scope_change | approval",
  "summary": "<plain-language description of what was decided or changed>",
  "changed_fields": ["scope_out", "features"]
}
```

**Ownership rules:**
- Orchestrator forwards the prior `decision_log` array when constructing a new snapshot.
- Agent provides a `decision_log_entry` object in the tool call; handler appends it with orchestrator-assigned `version`, `timestamp`, and `author`.
- On approval, handler appends an entry with `author: "human"`, `trigger: "approval"`.

**Purpose:** Reading the latest vN.json gives both current state and full decision history. Older snapshots exist for recomputation, not for human navigation.

---

## Explicitly Out of Scope (for now)

- Headless / API-only mode (no Claude Code)
- DAG orchestrator as a separate process
- Execution Agent, Evaluation Agent
- Documentation Agent and Handoff Package (team-ready deliverable)
- Metric thresholds on PRD (set by human at review gate)
- Quality evaluation signals (future iteration)
- Version compatibility validation between chosen technologies (tech stack scope_out)
- Technology market pricing or cost comparison (tech stack scope_out)
- Custom decision dimensions beyond the fixed enumeration (future tech stack extension)

---

## Evolution Log

| Date | Change |
|------|--------|
| 2026-04-14 | Step 5 (model-domain): `/model-domain` command written — DDD specialist, plain-language challenge loop, complexity calibration from Brief scope, `update_schema` support, refinement consistency check, decision log discipline. `domain-agent.md` retired. Product Owner updated with archetype classification: signal-to-archetype table, confidence rules, four required PRD fields locked after v1. |
| 2026-03-27 | Tech Stack Agent implemented: `write_tech_stack` + `approve_tech_stack` MCP tools, handler with rejection_reason semantic guard, renderer, `/tech-stack-agent` slash command with full deliberation session model (agenda confirmation, sequential deliberation, re-open flow). `_UPSTREAM_STAGE` updated with `tech_stack → design`. 73 new tests (378 total). |
| 2026-03-20 | Product Agent implemented (MCP tools, tool handler, renderer, system prompt) |
| 2026-03-20 | Designer Agent extracted as `/design` slash command |
| 2026-03-20 | 8 behavioral design principles added to design methodology |
| 2026-03-20 | /product-owner resume mechanism added (argument polymorphism: path / slug / no-arg scan / idea) |
| 2026-03-21 | Domain Agent designed: PRD approved, tool schemas, artifact schema, session model, challenge criteria, quality bar documented in design/domain-agent.md |
| 2026-03-21 | Artifact subfolder convention: each DAG step writes to `artifacts/<slug>/<step>/v<n>.json` (e.g. `prd/`, `domain/`, `design/`). Existing PRD artifacts migrated. All path references updated across agent, design doc, CLAUDE.md, and command prompts. |
| 2026-03-21 | Cross-cutting artifact conventions established: `created_at` (origin, stable), `updated_at` (snapshot), `references` (upstream deps), `decision_log` (append-only history with author/trigger/summary/changed_fields). All existing artifacts migrated. tool_handler, renderer, and design/product-agent.md updated. |
| 2026-03-21 | Domain Agent implemented: `write_domain_model` + `approve_domain_model` MCP tools, tool handler, renderer, `/domain-agent` slash command with full DDD session model. |
| 2026-03-21 | `agent/` renamed to `engine/` — the folder contains the deterministic execution engine (MCP server, handlers, renderers), not agents. |
| 2026-03-21 | Tests added: 106 tests across 4 files organized by type (invariant / lifecycle / contract / renderer) with pytest marks. Handler invariant violations fixed: slug locked from v1, PRD content uses explicit whitelist, domain prd_path only read on v1. |
| 2026-03-21 | Engine-owned validation layer added: handlers validate full input schema (via `jsonschema` against design doc schemas), slug format, PRD existence and approval status (H1), slug/path consistency (H2), approve path containment. MCP server returns `ValueError` as `TextContent` for agent recovery. 25 new tests (131 total). `domain_artifacts_dir` fixture introduced — domain tests now require pre-approved PRDs as a real precondition. |
| 2026-03-23 | Brainstormer Agent implemented: `write_brief` + `approve_brief` MCP tools, tool handler, renderer, `/brainstorm` slash command with 9-phase session model and hard gate before `write_brief`. Brief is now the mandatory upstream input for the Product Agent (strict DAG gate — approved Brief required). `acceptance_criteria` added as required field per PRD feature. 196 tests total. |
| 2026-03-25 | `read_artifact(slug, stage, version?)` MCP tool added — returns full artifact JSON by slug + stage + optional version (defaults to latest). Enables agent prompts to be scoped to MCP tools only for all artifact access; direct Claude Code file reads against artifacts are no longer needed or permitted. 9 new tests in `TestReadArtifact` (test_contracts.py). Architecture doc updated: MCP tools tables for all three agents, agent tool scope decision added. |
| 2026-03-25 | Architecture Agent implemented: `write_design` + `approve_design` MCP tools, tool handler with semantic guards (acl_needed + cqrs_applied), renderer, `/architecture-agent` slash command with derivation rules table, auto-derived decisions, cascade refinement sequence, and all four test suites updated (invariant/lifecycle/contract/renderer). Option A (rules in prompt) adopted; Option C (hybrid engine derivation) planned as future pipeline project. |
| 2026-03-25 | DAG topology made engine-private: `_UPSTREAM_STAGE` constant and `find_latest(slug, stage, status)` added to `tool_handler.py`. `brief_path` removed from `write_prd` schema; `prd_path` removed from `write_domain_model` schema — engine resolves upstream artifacts from slug automatically. `references` field now correctly populated on PRD v1 (was always `[]`). `get_available_artifacts(stage)` MCP tool added — returns in_progress/approved/ready_to_start buckets. All three agent prompts updated to use `get_available_artifacts` for no-argument entry point; no-arg menus now surface ready-to-start items from upstream. Tests need updating: `test_invariants.py` (remove brief_path/prd_path inputs), `test_lifecycle.py` (pre-approved upstream fixtures), `test_contracts.py` (new `TestGetAvailableArtifacts` class). |
