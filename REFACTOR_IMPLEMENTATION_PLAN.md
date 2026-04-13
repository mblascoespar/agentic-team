# Agentic Team — Refactor Implementation Plan
## Archetype Model + Layered DAG + Artifact Template System

**Status:** Design complete — ready for implementation
**Last design session:** 2026-04-12
**Resume from:** Implementation Steps section

---

## Why This Refactor Exists

The current engine assumes a single decomposition strategy:

```
Brief → PRD → Domain Model → Architecture → Tech Stack
```

This only works for domain-heavy systems. It fails for:
- data pipelines
- integrations and migrations
- internal tooling
- onboarding and installation systems

**Root cause:** The engine uses a single-model decomposition, while real problems require different or multiple modeling strategies.

**Example failure:** `existing-project-onboarding` produced DDD artifacts (CQRS, aggregates, bounded contexts) for an integration/install problem.

---

## Three Axes of Intelligence (What Changed)

The refactor introduces three orthogonal capabilities that must all be present:

| Axis | Question answered | Mechanism |
|------|------------------|-----------|
| Archetype selection | What kind of problem is this? | PRD classification |
| Layered modeling | How many models are needed? | DAG topology per combination |
| Artifact extensibility | What structure is needed to express it? | Mandatory/optional/proposed field system |

Miss any one → system breaks.

---

## Supported Archetypes

```
domain_system       — rich business rules, aggregates, bounded contexts
data_pipeline       — data transformation, stages, failure handling
system_integration  — integration constraints, adapters, ownership boundaries
process_system      — workflow execution, actors, state transitions
```

---

## Valid Archetype Combinations (Engine-Enforced)

Derived from real scenarios. Engine rejects anything not in this list.

```python
_VALID_COMBINATIONS = {
    ("domain_system",),
    ("data_pipeline",),
    ("system_integration",),
    ("process_system",),
    ("system_integration", "process_system"),  # order is load-bearing
    # ("data_pipeline", "process_system"),     # provisional — add when scenario confirmed
}
```

**Error when rejected:**
```
ERROR [write_model]: archetype combination (X, Y) is not supported.
Supported combinations: [...]. If your scenario does not fit, raise it as an open question in the PRD.
```

**Source scenarios:**
- `existing-project-onboarding` → `system_integration + process_system`
- `data deduplication engine` → `data_pipeline`
- `accounting engine` → `domain_system`

---

## DAG Structure

### One DAG per archetype combination (engine-owned)

```python
_DAG_TOPOLOGIES = {
    ("domain_system",): [
        "brief", "prd", "model_domain", "design", "tech_stack"
    ],
    ("data_pipeline",): [
        "brief", "prd", "model_data_flow", "design", "tech_stack"
    ],
    ("system_integration",): [
        "brief", "prd", "model_system", "design", "tech_stack"
    ],
    ("process_system",): [
        "brief", "prd", "model_workflow", "design", "tech_stack"
    ],
    ("system_integration", "process_system"): [
        "brief", "prd", "model_system", "model_workflow", "design", "tech_stack"
    ],
}
```

Engine reads archetype from the approved PRD for each slug. That selects the topology. All upstream resolution, `get_available_artifacts`, and next-stage routing derive from the topology.

### Layered case (system_integration + process_system)

```
PRD → Model (system) → Model (workflow) → Design → Tech Stack
```

- System Model is generated first. Human approves it (separate gate).
- Workflow Model Agent reads the approved System Model as upstream input.
- Workflow Model encodes System Model constraints — so Architecture Agent reads only `model_workflow/` and still has full context via `references`.
- Two approval gates in layered case.

### Artifact storage — separate stage directory per model type

```
artifacts/<slug>/model_domain/v1.json
artifacts/<slug>/model_data_flow/v1.json
artifacts/<slug>/model_system/v1.json
artifacts/<slug>/model_workflow/v1.json
```

Each model type maps to its own stage directory. The DAG topology defines which stages exist for a given slug.

---

## New Stage: Model Agent

Replaces the current Domain Agent. Produces model artifacts instead of domain model artifacts.

### Stage name mapping

| Archetype | Stage directory | Model type |
|-----------|----------------|------------|
| `domain_system` | `model_domain/` | Domain Model (DDD — unchanged) |
| `data_pipeline` | `model_data_flow/` | Data Flow Model |
| `system_integration` | `model_system/` | System Model |
| `process_system` | `model_workflow/` | Workflow Model |

### Model schemas

**Domain Model** (unchanged from current domain artifact)
```yaml
mandatory:
  bounded_contexts: [{name, responsibility, aggregates, commands, queries, events}]
  context_map: [{upstream, downstream, relationship}]
optional:
  assumptions:
  open_questions:
```

**Data Flow Model**
```yaml
mandatory:
  inputs:
  outputs:
  stages:
optional:
  invariants:
  failure_modes:
  retry_strategy:
  idempotency:
  performance:
```

**System Model**
```yaml
mandatory:
  components:
  integration_points:
  constraints:
    hard:
    soft:
  control_map:
    can_modify:
    can_extend:
    read_only:
optional:
  ownership:
  invariants:
  failure_modes:
```

**Workflow Model**
```yaml
mandatory:
  actors:
  steps:
optional:
  decision_points:
  inputs_outputs:
  metrics:
  failure_modes:
```

### MCP tool — single parameterized tool

```
write_model(slug, model_type, content, decision_log_entry)
approve_model(artifact_path)
```

`model_type` determines:
1. Which stage directory the artifact is written to
2. Which schema validates `content`
3. Which upstream stage the engine resolves (from `_DAG_TOPOLOGIES`)

Engine validates that `model_type` matches the archetype declared in the approved PRD for this slug. Mismatch → hard error.

### Session model (STILL TO DESIGN — one archetype at a time)

Model Agent session models have not yet been specified. Design these next, one per archetype:
- [ ] `domain_system` — adapt current domain agent challenge loop
- [ ] `data_pipeline` — new challenge loop
- [ ] `system_integration` — new challenge loop
- [ ] `process_system` — new challenge loop
- [ ] Layered case — System Model first, then Workflow Model within its constraints

---

## Archetype Classification — PRD Stage

### Where it lives

Archetype classification is added to the **PRD** by the **Product Owner agent**. Not in the Brief.

- Brief = competitive scan, direction exploration, complexity assessment (unchanged)
- PRD = problem framing, features, scope + archetype classification (new)

### New PRD fields

```yaml
primary_archetype: domain_system | data_pipeline | system_integration | process_system
secondary_archetype: process_system | null   # only valid secondary today
archetype_confidence: high | medium | low
archetype_reasoning: <string>               # agent must justify the classification
```

### Lock behavior

`primary_archetype` and `secondary_archetype` are locked on PRD v1 — carried forward unchanged on all subsequent versions (same as `slug`, `id`, `created_at`). Agent cannot change them on refinement. If the classification was wrong, go back and re-draft the PRD.

### Engine validation

On `write_prd` v1: engine validates the archetype combination is in `_VALID_COMBINATIONS`. Hard error if not.

On `write_model`: engine reads the approved PRD for the slug, extracts archetype, validates that `model_type` matches. Hard error if mismatch.

### PRD schema still to be formally specified

- [ ] Add `primary_archetype`, `secondary_archetype`, `archetype_confidence`, `archetype_reasoning` to `engine/schemas/prd.input.json`
- [ ] Add archetype lock enforcement to `handle_write_prd`
- [ ] Add combination validation to `handle_write_prd` v1
- [ ] Update Product Owner system prompt with classification challenge criteria

---

## Architecture Agent — Refactored

Kept as a separate stage. Correct separation:
- Architecture Agent = **system design** (technology-agnostic: patterns, structure, boundaries)
- Tech Stack Agent = **tool selection** (specific technologies for each design decision)

### Design artifact — common envelope + archetype-specific body

```yaml
# Common envelope — all archetypes
id, slug, version, status, references, decision_log
model_type: <archetype>
nfrs: [...]
cross_cutting: {auth, observability, error_propagation}
testing_strategy: [...]
open_questions: [...]

# Archetype-specific body
body:
  # domain_system (current behavior — unchanged)
  layering_strategy, aggregate_consistency, integration_patterns, storage

  # data_pipeline
  pipeline_stages, processing_strategy, storage_strategy, failure_handling, idempotency

  # system_integration
  adapter_map, boundary_contracts, event_contracts, ownership_map

  # process_system
  workflow_components, state_transitions, automation_strategy, trigger_mechanisms
```

`nfrs`, `cross_cutting`, `testing_strategy` are in the envelope because every archetype has these. Tech Stack always derives observability stack, auth library, and test framework from the envelope.

### Archetype-specific derivation rules (one system prompt per archetype)

| Archetype | Architecture Agent derives |
|-----------|---------------------------|
| `domain_system` | Layering (hexagonal/CQRS), aggregate consistency, context integration patterns, storage per aggregate — current behavior unchanged |
| `data_pipeline` | Stage topology, processing strategy (batch/stream/micro-batch), failure+retry architecture, storage layer (hot/cold/archive) |
| `system_integration` | Adapter map, owned vs read-only boundaries, event/API contract strategy, translation layer ownership |
| `process_system` | Workflow component design, state machine, trigger architecture, automation boundaries |
| Layered | Integration architecture first (constraints), then workflow execution within those constraints |

---

## Tech Stack Agent — Refactored

Reads `model_type` from Design artifact envelope. Applies archetype-specific decision dimensions.

### Decision dimensions per archetype

| Archetype | Decision dimensions |
|-----------|---------------------|
| `domain_system` | API framework, DB + ORM, message broker, auth, observability, test framework — current behavior |
| `data_pipeline` | Processing engine, queue/topic layer, storage tech, pipeline orchestrator, data quality tooling |
| `system_integration` | Constrained choices only (what external systems impose); adapter SDK, API gateway if needed, contract testing tool |
| `process_system` | Workflow engine, automation runtime, state storage, notification mechanism |
| Layered | Respect System Model constraints first; fill workflow execution gaps only |

---

## Artifact Template System (New — Cross-Cutting)

Every artifact stage uses a three-layer field model. This is not a side feature — it sits at the core of every stage.

### Why needed

Current schemas are fully predefined. This breaks when:
- A use case needs slightly different structure
- An agent discovers a missing concept mid-reasoning
- Different archetypes require different depth

### Three field kinds

| Kind | Schema source | Validation | Presence |
|------|--------------|------------|---------|
| `mandatory` | Base schema | Validated strictly; must be present at approval | Required |
| `optional` | Base schema | Validated if present; ignored if absent | Not required |
| `proposed` | Agent + human approval | name + description + value (unvalidated) accepted | Not required |

> **Note:** There is no "custom" kind. When an agent proposes a new field, it must declare it as either `mandatory` or `optional`. The classification is a real design decision the agent makes and the human approves.

### Instance schema

Every artifact stage for every slug has an instance schema stored alongside the artifact:

```
artifacts/<slug>/model_data_flow/schema.json   ← instance schema
artifacts/<slug>/model_data_flow/v1.json
artifacts/<slug>/model_data_flow/v2.json
```

The instance schema starts as a copy of the base schema from `engine/schemas/`. It grows as the agent proposes and the human approves new fields.

```json
{
  "base": "model-data-flow",
  "fields": {
    "inputs":                 { "kind": "mandatory" },
    "outputs":                { "kind": "mandatory" },
    "stages":                 { "kind": "mandatory" },
    "retry_strategy":         { "kind": "optional" },
    "matching_heuristics":    { "kind": "optional", "added_at_version": 2,
                                "description": "fuzzy deduplication rules when exact match fails" }
  }
}
```

### Schema update flow (human-in-the-loop)

```
Agent discovers missing concept mid-reasoning
    ↓
Agent proposes in conversation:
"I need a `matching_heuristics` field — fuzzy deduplication rules when exact match fails.
I'd classify it as optional. Do you want to add it?"
    ↓
Human approves
    ↓
Agent calls: update_schema(slug, stage, field_name, kind, description)
    ↓
Instance schema updated at artifacts/<slug>/<stage>/schema.json
Decision log entry auto-generated by handler
    ↓
Agent includes field in next write_* call — accepted
```

### Mandatory validation — at approval only

Validation of mandatory field presence does **not** run on every `write_*` call. Agent can work incrementally.

```
write_* (v1, v2, v3...)  →  structure validation only (correct types, no reserved field conflicts)
approve_*                →  mandatory validation runs against instance schema
                            missing mandatory fields → approval rejected with list
                            all present → artifact approved, schema frozen for this slug/stage
```

### read_artifact — returns artifact + schema

`read_artifact(slug, stage, version?)` always returns both:
```json
{
  "artifact": { ...full artifact content... },
  "schema":   { ...instance schema for this slug/stage... }
}
```

Downstream agents always have the schema when they have the artifact. No separate `read_schema` tool needed. This is the deterministic behavior guarantee.

### Schema promotion (human-approved evolution)

When the same proposed field appears across multiple initiatives of the same archetype:

1. Agent or human notices the pattern in conversation
2. Agent proposes: "I've seen `matching_heuristics` needed in three `data_pipeline` initiatives. Should we promote it to the base schema as optional?"
3. Human approves
4. Engine updates `engine/schemas/model-data-flow.json`
5. Future initiatives of that archetype get the field in their base schema automatically

### new MCP tool: `update_schema`

```
update_schema(slug, stage, field_name, kind, description)

Inputs:
  slug: string
  stage: string
  field_name: string        — must not conflict with existing mandatory or optional field names
  kind: "mandatory" | "optional"
  description: string       — non-empty, plain language explanation

Behavior:
  - Validates field_name does not already exist in instance schema
  - Validates kind is mandatory or optional
  - Validates description is non-empty
  - Appends field to artifacts/<slug>/<stage>/schema.json
  - Auto-generates decision_log entry:
      trigger: "schema_field_added"
      summary: "Added <field_name> (<kind>): <description>"
      changed_fields: ["schema"]

Error cases:
  - Field already exists in schema → hard error
  - kind not in {mandatory, optional} → hard error
  - description empty → hard error
```

---

## Mutability Model

**Approved artifacts are immutable.** No re-open, no stale detection, no downstream invalidation.

**To change anything:** go back to the appropriate upstream stage, re-draft, approve, then regenerate all downstream stages forward.

```
Brief → PRD → Model → Design → Tech Stack
                ↑
  need to change model?
  re-draft here → approve → regenerate Design → regenerate Tech Stack
```

`find_latest(slug, stage, status="approved")` always returns the latest approved version. Any agent re-running a downstream stage automatically picks up the newly approved upstream artifact.

### get_available_artifacts — informational staleness signal

When a downstream artifact is older than the latest approved upstream, surface it as information (not a blocker):

```json
{
  "approved": [{
    "slug": "data-dedup",
    "stage": "design",
    "version": 1,
    "upstream_changed": true,
    "note": "model_data_flow was re-approved at v2 after this design was approved at v1"
  }]
}
```

Human decides whether to regenerate. Engine does not block.

---

## Engine Changes Summary

### New / changed: `tool_handler.py`

| Change | What it does |
|--------|-------------|
| `_DAG_TOPOLOGIES` replaces `_UPSTREAM_STAGE` | One topology list per archetype combination |
| `_read_archetype(slug)` | Reads approved PRD for slug, returns `(primary, secondary)` tuple |
| `_resolve_topology(slug)` | Calls `_read_archetype`, returns the DAG topology for this slug |
| `handle_write_model(tool_input, existing_model)` | New handler. Validates model_type matches PRD archetype. Routes to correct stage dir. |
| `handle_approve_model(artifact_path)` | Validates mandatory fields against instance schema before approving. |
| `handle_update_schema(tool_input)` | Adds a field (mandatory/optional) to the instance schema. Auto-generates decision_log entry. |
| `handle_write_prd` — archetype lock | On v1: validate combination in `_VALID_COMBINATIONS`. On v2+: carry forward archetype fields unchanged. |
| `read_artifact` | Now returns `{artifact, schema}` wrapper. Reads `schema.json` alongside artifact file. |
| `get_available_artifacts` | Must be topology-aware. Reads archetype from PRD to determine which model stages to query. Adds `upstream_changed` signal. |

### New schema files: `engine/schemas/`

```
model-domain.json      (field metadata for Domain Model — mandatory/optional)
model-data-flow.json   (field metadata for Data Flow Model)
model-system.json      (field metadata for System Model)
model-workflow.json    (field metadata for Workflow Model)
```

Each schema file format:
```json
{
  "fields": {
    "field_name": { "kind": "mandatory" | "optional" }
  }
}
```

### Removed

- `_UPSTREAM_STAGE` dict (replaced by `_DAG_TOPOLOGIES`)
- Path-based schema references (replaced by archetype-based)
- `handle_write_domain_model` (replaced by `handle_write_model`)
- `handle_approve_domain_model` (replaced by `handle_approve_model`)

### Artifact storage changes

| Old | New |
|-----|-----|
| `artifacts/<slug>/domain/vN.json` | `artifacts/<slug>/model_domain/vN.json` |
| (new) | `artifacts/<slug>/model_data_flow/vN.json` |
| (new) | `artifacts/<slug>/model_system/vN.json` |
| (new) | `artifacts/<slug>/model_workflow/vN.json` |
| (new) | `artifacts/<slug>/<stage>/schema.json` (instance schema, all stages) |

Existing `domain/` artifacts → archived (moved to `artifacts/<slug>/domain/_archived/`). Not deleted.

---

## MCP Tool Changes

### New tools

| Tool | Input | Action |
|------|-------|--------|
| `write_model` | slug, model_type, content, decision_log_entry | Writes `artifacts/<slug>/model_<type>/vN.json`. Validates model_type matches PRD archetype. |
| `approve_model` | artifact_path | Validates mandatory fields against instance schema. Sets status: approved. |
| `update_schema` | slug, stage, field_name, kind, description | Adds field to instance schema. Rejects conflicts. Auto-logs decision. |

### Changed tools

| Tool | Change |
|------|--------|
| `read_artifact` | Returns `{artifact, schema}` instead of artifact dict directly |
| `write_prd` | Validates archetype combination on v1. Locks archetype fields on v2+. |
| `get_available_artifacts` | Topology-aware. Reads archetype from PRD per slug. Adds `upstream_changed` signal. |

### Removed tools

| Tool | Replaced by |
|------|-------------|
| `write_domain_model` | `write_model` with model_type: "domain_system" |
| `approve_domain_model` | `approve_model` |

---

## Prompt Changes

### Product Owner prompt (`.claude/commands/product-owner.md`)

Add classification challenge criteria:
- Agent must classify `primary_archetype` and optionally `secondary_archetype`
- Agent presents reasoning: "This looks like a `system_integration` because X. Do you agree?"
- Human confirms or overrides
- Agent records `archetype_reasoning` in the PRD
- Classification challenge runs after problem/scope challenge, before drafting

### Model Agent prompts (new — one per archetype)

```
.claude/commands/model-agent-domain.md
.claude/commands/model-agent-data-flow.md
.claude/commands/model-agent-system.md
.claude/commands/model-agent-workflow.md
```

Session models still to be designed (see Open Work section).

### Architecture Agent prompt (`.claude/commands/architecture-agent.md`)

- Replace single DDD derivation rule table with archetype-aware rules
- Agent reads `model_type` from Design artifact envelope
- Applies the appropriate derivation rules for that archetype
- Separate prompts per archetype OR single prompt with archetype-conditional rule sections (decide during implementation)

### Tech Stack Agent prompt (`.claude/commands/tech-stack-agent.md`)

- Replace fixed decision dimension table with archetype-aware tables
- Agent reads `model_type` from Design artifact envelope
- Applies appropriate decision dimensions for that archetype

---

## Test Implications

### `test_invariants.py` — new invariants

- `write_model`: archetype mismatch (model_type vs PRD archetype) → rejected
- `write_model`: model_type not in supported types → rejected
- `write_prd` v1: invalid archetype combination → rejected
- `write_prd` v2+: archetype fields carried forward unchanged (agent cannot change them)
- `update_schema`: field_name conflicts with existing field → rejected
- `update_schema`: kind not in {mandatory, optional} → rejected
- `update_schema`: description empty → rejected
- `approve_model`: mandatory field missing in content → rejected with field list

### `test_lifecycle.py` — new lifecycle classes

- `TestModelDomainV1`, `TestModelDomainV2`, `TestApproveModelDomain`
- `TestModelDataFlowV1`, `TestModelDataFlowV2`, `TestApproveModelDataFlow`
- `TestModelSystemV1`, `TestApproveModelSystem`
- `TestModelWorkflowV1`, `TestApproveModelWorkflow`
- `TestInstanceSchemaCreated` — schema.json created alongside v1 artifact
- `TestInstanceSchemaUpdated` — schema.json updated on update_schema call

### `test_contracts.py` — new DAG edges

- `TestPRDToModelDomain` — PRD archetype `domain_system` → model_domain stage
- `TestPRDToModelDataFlow` — PRD archetype `data_pipeline` → model_data_flow stage
- `TestPRDToModelSystem` — PRD archetype `system_integration` → model_system stage
- `TestModelSystemToModelWorkflow` — layered case: model_workflow reads approved model_system
- `TestModelToDesign` — architecture agent reads model artifact (any type), produces design with model_type in envelope
- `TestReadArtifactReturnsSchema` — read_artifact response includes schema key

### `test_renderer.py` — new renderers

- Model artifact renderers: all mandatory + optional fields appear in output
- Instance schema section: rendered distinctly (mandatory vs optional fields labeled)
- Design artifact: common envelope fields + archetype-specific body fields all appear
- `upstream_changed` signal appears in `get_available_artifacts` output when applicable

---

## Implementation Steps (Ordered)

### Step 1 — PRD archetype fields (unblocks everything else)

- [ ] Add archetype fields to `engine/schemas/prd.input.json`
- [ ] Add archetype lock to `handle_write_prd` (carry forward on v2+)
- [ ] Add `_VALID_COMBINATIONS` and combination validation to `handle_write_prd` v1
- [ ] Add `_read_archetype(slug)` helper to `tool_handler.py`
- [ ] Update Product Owner system prompt with archetype challenge criteria
- [ ] Tests: invariant (invalid combination, lock enforcement), lifecycle (archetype fields in v1/v2)

### Step 2 — DAG topology system (unblocks model stage)

- [ ] Replace `_UPSTREAM_STAGE` with `_DAG_TOPOLOGIES` in `tool_handler.py`
- [ ] Add `_resolve_topology(slug)` that reads archetype from PRD
- [ ] Update `get_available_artifacts` to be topology-aware
- [ ] Add `upstream_changed` signal to `get_available_artifacts` response
- [ ] Tests: contract tests for topology resolution per archetype combination

### Step 3 — Instance schema system (unblocks write_model and update_schema)

- [ ] Define base schema file format (field + kind metadata)
- [ ] Create `engine/schemas/model-domain.json`, `model-data-flow.json`, `model-system.json`, `model-workflow.json`
- [ ] Add instance schema creation: `schema.json` written alongside `v1` artifact
- [ ] Implement `handle_update_schema` in `tool_handler.py`
- [ ] Expose `update_schema` in `mcp_server.py`
- [ ] Update `read_artifact` to return `{artifact, schema}` wrapper
- [ ] Tests: lifecycle (schema.json created at v1, updated on update_schema), invariant (conflict/invalid rejection), contract (read_artifact returns schema)

### Step 4 — Model Agent (write_model + approve_model)

- [ ] Implement `handle_write_model` — routes to correct stage dir, validates model_type vs PRD archetype
- [ ] Implement `handle_approve_model` — validates mandatory fields against instance schema before approving
- [ ] Expose `write_model`, `approve_model` in `mcp_server.py`
- [ ] Remove `write_domain_model`, `approve_domain_model` from MCP server (keep handler for migration)
- [ ] Create model renderers for each model type
- [ ] Archive existing `domain/` artifacts (move to `_archived/`)
- [ ] Tests: full invariant/lifecycle/contract/renderer suite for each model type

### Step 5 — Model Agent session models (one archetype at a time)

*Still to be designed — see Open Work section*

- [ ] Design `domain_system` challenge loop (adapt current Domain Agent)
- [ ] Design `data_pipeline` challenge loop
- [ ] Design `system_integration` challenge loop
- [ ] Design `process_system` challenge loop
- [ ] Design layered case session flow
- [ ] Write system prompts per archetype

### Step 6 — Architecture Agent refactor

- [ ] Rewrite Design artifact schema — common envelope + archetype-specific body
- [ ] Update `handle_write_design` to accept new schema structure
- [ ] Rewrite Architecture Agent system prompt — archetype-aware derivation rules
- [ ] Tests: contract (model artifact of each type → design artifact with correct body)

### Step 7 — Tech Stack Agent refactor

- [ ] Update Tech Stack Agent system prompt — archetype-specific decision dimension tables
- [ ] Tests: contract (design artifact of each type → tech stack with correct dimensions)

### Step 8 — Decision log across all stages

*Already implemented for existing stages. Verify and extend to new model stages.*

- [ ] All new handlers append decision_log entries
- [ ] update_schema auto-generates decision_log entry
- [ ] Tests: lifecycle tests verify decision_log structure for all new handlers

---

## Open Work (Still To Design)

These require a design session before implementation:

### A — Model Agent session models (Step 5)

What does the challenge loop look like for each archetype? The Domain Agent has a DDD challenge loop. Need equivalent for:
- `data_pipeline`: what does the agent challenge? (input schema, stage boundaries, failure modes, idempotency requirements)
- `system_integration`: (what systems, what you control vs don't, what the contracts are)
- `process_system`: (who are the actors, what are the steps, what can fail, what needs automation)
- Layered case: System Model first (constraints), then Workflow Model within those constraints

### B — PRD archetype challenge criteria

What questions does the Product Owner ask to determine archetype? What signals distinguish `domain_system` from `system_integration`? Design the classification rubric.

### C — `update_schema` tool formal specification

Inputs, error cases, and edge behaviors written in detail (partially done above — formalize).

---

## What Does NOT Change

- Artifact lifecycle structure (id, slug, version, parent_version, created_at, updated_at, status, references, decision_log)
- Human approval gates pattern
- MCP server architecture
- Claude Code as the conversational interface
- `find_latest` helper (still used, now called with archetype-specific stage names)
- Brief artifact and Brainstormer Agent (no changes)
- PRD content fields (problem, features, scope, etc.) — archetype fields are additions only
- Design artifact stage name (`design/`) and Tech Stack artifact stage name (`tech_stack/`)
- Execution Agent and Evaluation Agent (not yet built, not affected)

---

## Validation Test Cases

### `existing-project-onboarding`

```
PRD: primary_archetype: system_integration, secondary_archetype: process_system
DAG: brief → prd → model_system → model_workflow → design → tech_stack

Expected:
- System Model: project constraints, MCP integration points, control_map
- Workflow Model: install steps, validation, rollback (within system constraints)
- Design: integration architecture + workflow execution plan
- Tech Stack: constrained by existing system; only workflow execution gaps filled
```

### `data deduplication engine`

```
PRD: primary_archetype: data_pipeline
DAG: brief → prd → model_data_flow → design → tech_stack

Expected:
- Data Flow Model: input records, dedup stages, output
- Design: pipeline stage topology, processing strategy, storage layer
- Tech Stack: processing engine, queue layer, storage tech
```

### `accounting engine`

```
PRD: primary_archetype: domain_system
DAG: brief → prd → model_domain → design → tech_stack

Expected:
- Domain Model: Account, Transaction, Journal Entry aggregates; Ledger/Reporting/Reconciliation contexts
- Design: hexagonal layering, aggregate consistency, storage per context
- Tech Stack: full stack (API framework, DB, auth, observability)
```

---

## Success Criteria

- Different archetypes produce different model artifacts in different stage directories
- Layered case produces two sequential model artifacts; second references first
- No DDD artifacts (bounded contexts, aggregates, CQRS) outside `domain_system` archetype
- Architecture Agent produces different design body structure per archetype
- Tech Stack Agent applies different decision dimensions per archetype
- Agents can propose new schema fields; human approves; instance schema grows
- Mandatory field validation blocks approval (not intermediate writes)
- `read_artifact` always returns both artifact and instance schema
- Going back upstream and regenerating produces fresh downstream artifacts without engine conflict
- Onboarding case produces install + integration logic — no CQRS, no aggregates

---

## Key Design Constraints

> No new archetypes until repeated failure occurs.

> No new archetype combinations until a real scenario requires it.

> Artifact approved = immutable. To change: go upstream, regenerate forward.

> The DAG orchestrator (engine) is the ONLY component allowed to manage run state, assign versions, and update execution progress. Agents are stateless outside their output artifacts.
