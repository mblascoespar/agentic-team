# Refactor Implementation Plan
## Multi-Archetype DAG + Model Stage + Artifact Template System

**Branch:** `refactor/step-2-dag-topology`
**Design record:** `docs/architecture.md` → "Refactor: Multi-Archetype System" section

---

## The Problem

The current engine assumes every initiative is a domain-heavy system and routes all slugs through:

```
brief → prd → domain → design → tech_stack
```

This breaks for data pipelines, integrations, migrations, and process workflows — all of which produce wrong artifacts (DDD bounded contexts, CQRS) for problems that don't need them.

**Root cause:** Single-topology DAG. The engine cannot route differently based on problem type.

---

## What This Refactor Delivers (End State)

- PRDs declare what kind of problem they are (archetype)
- The engine selects the correct DAG topology per archetype
- Model agents produce the correct model artifact for the problem type
- Architecture and Tech Stack agents apply archetype-appropriate rules
- Artifact schemas can grow per-initiative without changing the base schema
- Instance schema pattern (base schema → per-initiative evolution → approval validation) is universal across all stages
- Single generic `write_artifact` / `approve_artifact` replaces all stage-specific handlers

---

## Phase 1: Multi-Archetype Foundation (Steps 1–8)

---

### Step 1 — PRD Archetype Fields `DONE`

**Milestone:** PRDs declare problem type. Archetype fields locked after v1.

#### Tasks
- [x] Add `primary_archetype`, `secondary_archetype`, `archetype_confidence`, `archetype_reasoning` to `engine/schemas/prd.input.json`
- [x] Add `_VALID_COMBINATIONS` to `tool_handler.py`
- [x] Add combination validation to `handle_write_prd` v1
- [x] Add archetype lock to `handle_write_prd` v2+
- [x] Add `_read_archetype(slug)` helper
- [x] Update Product Owner system prompt with archetype classification challenge
- [x] Tests: invariant (invalid combination rejected, lock enforcement), lifecycle (archetype in v1/v2)

---

### Step 2 — DAG Topology System `DONE`

**Milestone:** Engine routes each slug through the correct stage sequence. `get_available_artifacts` is forward-looking via `_next_stage`.

#### Tasks
- [x] Replace `_UPSTREAM_STAGE` dict with `_DAG_TOPOLOGIES`
- [x] Add `_resolve_topology(slug)`
- [x] Add `_next_stage(slug)`
- [x] Rewrite `get_available_artifacts` to use `_next_stage`
- [x] Tests: `TestTopologyResolution`, `TestNextStage`, `TestTopologyAwareGetAvailableArtifacts`

---

### Step 3 — Instance Schema System `DONE`

**Milestone:** Every artifact stage for every slug has a live `schema.json`. Agents can propose new fields via `update_schema`. `read_artifact` returns `{artifact, schema}`. Mandatory field validation deferred to approval time.

#### Tasks
- [x] Base schema files: `model-domain.json`, `model-data-flow.json`, `model-system.json`, `model-workflow.json`, `model-evolution.json`
- [x] `_ensure_instance_schema(slug, stage)` — creates `schema.json` on first write
- [x] `handle_update_schema` — add only; rejects duplicate field
- [x] `update_schema` exposed in `mcp_server.py`
- [x] `read_artifact` returns `{"artifact": {...}, "schema": {...}}`
- [x] Tests: lifecycle (schema.json created on v1), invariant (duplicate rejected), contract (read_artifact includes schema)

---

### Step 4 — Model Agent: `write_model` + `approve_model` `DONE`

**Milestone:** Agents write and approve model artifacts for any archetype. `approve_model` validates mandatory schema fields.

#### Tasks
- [x] `handle_write_model` — validates model_type via topology, derives upstream, creates instance schema on first write
- [x] `handle_approve_model` — validates mandatory fields; lists missing on rejection
- [x] `write_model`, `approve_model` exposed in MCP server
- [x] `render_model` — generic renderer for all model types
- [x] Tests: invariants, lifecycle (all 4 types + layered reference chain), contracts, renderer

---

### Step 5 — Model Agent Session Models `DONE`

**Milestone:** Human-runnable agents for each archetype.

#### Tasks
- [x] `/model-domain` command written
- [x] `/model-data-flow` command written
- [x] `/model-evolution` command written
- [x] `/model-system` command written
- [x] `/model-workflow` command written (includes layered case: loads model_system when secondary_archetype present)

---

### Step 6 — Architecture Agent Refactor `DONE`

**Milestone (engine):** `handle_write_design` resolves upstream model stage from topology. Design artifacts chain correctly for every archetype.

**Milestone (agent):** Archetype-aware derivation rules. Per-archetype body structure.

#### Tasks
- [x] `handle_write_design` resolves upstream model stage from topology
- [x] Tests: stale `domain/v1.json` references updated
- [x] Per-archetype Design artifact body schemas — absorbed into Step 10 (all 5 design schemas exist)
- [x] Update `handle_write_design` for archetype-specific body — absorbed into Step 13 (generic `write_artifact`)
- [x] Rewrite Architecture Agent system prompt — absorbed into Step 15 (per-archetype agents)

---

### Step 7 — Tech Stack Agent Refactor `DONE`

**Milestone:** Tech stack decisions use correct decision dimensions per archetype.

#### Tasks
- [x] Tool name updates (`write_tech_stack` → `write_artifact`, etc.) — absorbed into Step 14
- [x] Per-archetype decision dimensions + agent rewrite — absorbed into Step 17 (DESIGN REQUIRED, tracked there)

---

### Step 8 — Decision Log Coverage `DONE`

**Milestone:** All model stages have full audit trail. `update_schema` auto-logs schema evolution.

#### Tasks
- [x] `handle_write_model` appends decision_log entry
- [x] `handle_approve_model` appends approval entry
- [x] `handle_update_schema` appends `trigger: "schema_field_added"`

---

## Phase 2: Generic Engine + Per-Archetype Design

These steps emerged from design review (2026-04-20). They are sequenced by dependency.

---

### Step 9 — `update_schema` Extension `DONE`

**Milestone:** Agents can add, update, and delete fields from the instance schema mid-session. Rename (field_name change) invalidates content at the old key in the latest draft.

**Why here:** Unblocks full schema lifecycle for all stages. Isolated change, no downstream dependencies.

**Gates:** Step 10 (base schemas reference the final update_schema contract)

#### Tasks
- [x] Replace `handle_update_schema` with 3 handlers: `handle_add_schema_field`, `handle_update_schema_field`, `handle_delete_schema_field`
- [x] `add`: kind + description required; rejects duplicate; logs `schema_field_added`
- [x] `update`: kind/description/new_field_name (at least one); rename clears old key in draft; logs `schema_field_updated`
- [x] `delete`: justification required; clears key in draft; logs `schema_field_deleted`
- [x] Replace `update_schema` MCP tool with 3 tools (`add_schema_field`, `update_schema_field`, `delete_schema_field`); rich descriptions per Option A
- [x] Updated all 5 model agent commands: tool list + output discipline note; detailed "when to call" moved to MCP tool descriptions
- [x] Tests: all invariants and lifecycle cases; 294 passing

---

### Step 10 — Base Schemas for All Stages `DONE`

**Milestone:** Every stage has a base schema that `_init_schema` can copy on first write. The instance schema pattern is no longer model-only — it is universal.

**Why here:** Prerequisite for Steps 11 and 13. The generic handler needs base schemas to exist for all stages before it can call `_init_schema` universally.

**Gates:** Steps 11, 13

#### Tasks
- [ ] Create `engine/schemas/brief.base.json` — mandatory/optional field map for brief stage
- [ ] Create `engine/schemas/prd.base.json` — mandatory/optional field map for prd stage
- [ ] Create `engine/schemas/tech_stack.base.json` — mandatory/optional field map for tech_stack stage
- [ ] Create `engine/schemas/design-domain_system.json` — archetype-specific body schema; semantic guards as JSON Schema `if/then`; mandatory/optional per design from this session
- [ ] Create `engine/schemas/design-data_pipeline.json` — per mandatory/optional table from this session
- [ ] Create `engine/schemas/design-system_integration.json`
- [ ] Create `engine/schemas/design-process_system.json`
- [ ] Create `engine/schemas/design-system_evolution.json`
- [ ] Update `_BASE_SCHEMAS_BY_STAGE` in `tool_handler.py` to include all stages; design stage lookup is `"design-{archetype}"` keyed

---

### Step 11 — Universal `_init_schema` + Approve Validation `DONE`

**Milestone:** `_init_schema` (renamed from `_ensure_instance_schema`) is called on every first write for every stage. `approve_artifact` validates mandatory fields for every stage, not just model stages.

**Why here:** Depends on Step 10 (base schemas must exist). Prerequisite for Step 13 (generic handler calls `_init_schema`).

**Gates:** Step 13

#### Tasks
- [ ] Rename `_ensure_instance_schema` → `_init_schema` in `tool_handler.py`
- [ ] Verify `_init_schema` falls back to `{"fields": {}}` for stages with no base schema (already does — confirm still correct)
- [ ] Extract mandatory-field approval validation into `_validate_mandatory_fields(slug, stage, content)` helper
- [ ] Call `_validate_mandatory_fields` in: `handle_approve_prd`, `handle_approve_brief`, `handle_approve_design`, `handle_approve_tech_stack` (and `handle_approve_model` already does it)
- [ ] Tests:
  - Lifecycle: `_init_schema` called for brief, prd, design, tech_stack on first write (schema.json created)
  - Lifecycle: `approve_*` for each non-model stage validates mandatory fields; missing field → rejection with list

---

### Step 12 — `get_work_context` Tool `DONE`

**Milestone:** Agents stop orchestrating upstream resolution. A single `get_work_context(slug, stage)` call returns everything needed to start or resume work: the approved upstream artifact and the current draft (if any). Engine owns topology lookup, upstream stage resolution, and draft detection — agents own nothing about routing.

**Why here:** Depends on Step 2 (topology resolution in place). Prerequisite for Step 13 (generic handler reads archetype from PRD directly — no envelope propagation needed). Supersedes the earlier archetype-in-envelope + richer `ready_to_start` design.

**Gates:** Step 13

#### Return shape
```json
{
  "upstream": { ...approved upstream artifact with schema... },
  "current_draft": { ...current draft artifact with schema... }  // null if starting fresh
}
```

#### Error cases
- Upstream not yet approved → `"ERROR [get_work_context]: <upstream_stage> for '<slug>' is not approved. Resume with /<upstream-agent>."`
- Stage not in slug's topology → `"ERROR [get_work_context]: stage '<stage>' is not in the topology for '<slug>'."`
- No approved PRD (topology unknown) → `"ERROR [get_work_context]: cannot determine topology for '<slug>'. Approve the PRD first."`

#### Agent entry point pattern (replaces multi-call navigation in all agents)
- User provides slug → `get_work_context(slug, stage)` directly
- No slug → `get_available_artifacts(stage)` for overview, user picks slug, then `get_work_context`

#### Tasks
- [x] Add `handle_get_work_context(slug, stage)` to `tool_handler.py`: resolve topology, find upstream stage, load upstream via `read_artifact_with_schema`, load current draft if exists
- [x] Register `get_work_context` in `mcp_server.py`
- [x] Tests:
  - Contract: `get_work_context` returns upstream + null draft for ready-to-start slug
  - Contract: `get_work_context` returns upstream + draft for in-progress slug
  - Invariant: stage not in topology → error
  - Invariant: upstream not approved → error

---

### Step 13 — Generic `write_artifact` + `approve_artifact` `DONE`

**Milestone:** All stage-specific write and approve handlers are replaced by a single `handle_write_artifact` and `handle_approve_artifact`. One MCP tool for all writes, one for all approvals. No content key filtering, no hardcoded semantic guards, no stage-specific branching in the handler.

**Why here:** Depends on Steps 10, 11, 12. Step 12 (`get_work_context`) removes the need for archetype-in-envelope — the generic handler reads archetype from the PRD directly. This is the largest single change in Phase 2.

**Gates:** Steps 14, 15, 16

#### Handler design

```
handle_write_artifact(slug, stage, body, decision_log_entry, existing):
  1. validate slug format
  2. verify upstream artifact approved (safety gate — topology already resolved at session start)
  3. read archetype from PRD via _read_prd_archetype(slug)
  4. load base schema: engine/schemas/<stage>-<archetype>.json (or <stage>.base.json)
  5. jsonschema.validate(body, base_schema)  ← structural validation; semantic guards in base schema as if/then
  6. _init_schema(slug, stage)
  7. write artifact, body as content

handle_approve_artifact(artifact_path):
  1. validate path + not-already-approved
  2. load instance schema from artifacts/<slug>/<stage>/schema.json
  3. _validate_mandatory_fields(slug, stage, content)
  4. set status: approved, append decision_log entry
```

#### Stage config dict (engine-private)
```python
_STAGE_CONFIG = {
    "brief":      { "upstream": None,       "locked_fields": ["idea"],                      "author": "agent:brainstorm-agent" },
    "prd":        { "upstream": "brief",    "locked_fields": _ARCHETYPE_LOCKED_KEYS,        "author": "agent:product-agent" },
    "model_*":    { "upstream": topology,   "locked_fields": [],                             "author": "agent:model-agent-{type}" },
    "design":     { "upstream": topology,   "locked_fields": [],                             "author": "agent:architecture-agent" },
    "tech_stack": { "upstream": "design",   "locked_fields": [],                             "author": "agent:tech-stack-agent" },
}
```

#### Tasks
- [ ] Implement `handle_write_artifact` in `tool_handler.py` (see design above)
- [ ] Implement `handle_approve_artifact` in `tool_handler.py`
- [ ] Remove: `handle_write_prd`, `handle_write_brief`, `handle_write_design`, `handle_write_tech_stack`, `handle_write_model`, `handle_write_domain_model`
- [ ] Remove: `handle_approve_prd`, `handle_approve_brief`, `handle_approve_design`, `handle_approve_tech_stack`, `handle_approve_model`, `handle_approve_domain_model`
- [ ] Remove: `_BRIEF_CONTENT_KEYS`, `_PRD_CONTENT_KEYS`, `_DESIGN_CONTENT_KEYS`, `_TECH_STACK_CONTENT_KEYS`
- [ ] Update `mcp_server.py`:
  - Add `write_artifact` tool: `{ slug, stage, body, decision_log_entry? }`
  - Add `approve_artifact` tool: `{ artifact_path }`
  - Remove: `write_prd`, `write_brief`, `write_design`, `write_tech_stack`, `write_model`, `write_domain_model`
  - Remove: `approve_prd`, `approve_brief`, `approve_design`, `approve_tech_stack`, `approve_model`, `approve_domain_model`
- [ ] Update `renderer.py`: `render_design` dispatches by archetype (one render function per archetype body shape)
- [ ] Tests:
  - Invariant: archetype mismatch (domain_system body sent for data_pipeline slug) → rejected; body structural validation fails → rejected before write
  - Lifecycle: all existing v1/v2/approve tests rewritten against `write_artifact` / `approve_artifact`
  - Contract: all existing DAG edge tests rewritten; `TestGetAvailableArtifactsRichContext`
  - Renderer: `render_design` per archetype — all mandatory body fields appear in output

---

### Step 14 — Update All Existing Agent Commands `DONE`

**Milestone:** All agent commands use `write_artifact` / `approve_artifact` / updated `update_schema` syntax. No command references the old per-stage tools.

**Why here:** Depends on Step 13 (tools must exist before commands reference them). Step 9 must also be done (update_schema syntax changed).

#### Tasks
- [x] `.claude/commands/brainstorm.md` — `write_brief` → `write_artifact(stage: "brief")`, `approve_brief` → `approve_artifact`
- [x] `.claude/commands/product-owner.md` — `write_prd` → `write_artifact(stage: "prd")`, `approve_prd` → `approve_artifact`, add `get_work_context`, apply two-path entry point
- [x] `.claude/commands/model-domain.md` — `write_model` → `write_artifact(stage: "model_domain")`, `approve_model` → `approve_artifact`, add `get_work_context`, apply two-path entry point
- [x] `.claude/commands/model-data-flow.md` — same pattern for `model_data_flow`
- [x] `.claude/commands/model-evolution.md` — same pattern for `model_evolution`
- [x] `.claude/commands/model-system.md` — same pattern for `model_system`
- [x] `.claude/commands/model-workflow.md` — same pattern for `model_workflow`
- [x] `.claude/commands/architecture-agent.md` — `write_design` → `write_artifact(stage: "design")`, `approve_design` → `approve_artifact`, add `get_work_context`, apply two-path entry point
- [x] `.claude/commands/tech-stack-agent.md` — `write_tech_stack` → `write_artifact(stage: "tech_stack")`, `approve_tech_stack` → `approve_artifact`, add `get_work_context`, apply two-path entry point
- [x] Update CLAUDE.md tool reference table if it lists individual tool names (no changes needed — CLAUDE.md does not reference per-stage tool names)

---

### Step 15 — Architecture Agent Refactor (Full) `DONE`

**Milestone:** Architecture Agent applies the correct derivation rules for the problem type. Design artifact body is archetype-specific. Agent reads archetype from the upstream artifact returned by `get_work_context` — no PRD read needed.

**Why here:** Depends on Steps 12 (get_work_context), 13 (generic write_artifact), 10 (per-archetype body schemas exist).

**Approach taken:** Split monolithic `architecture-agent.md` into per-archetype specialists rather than a single branching file. Shared behavior extracted to `architecture-shared.md`.

#### Tasks
- [x] `.claude/commands/architecture-agent.md` — retired; replaced with routing stub directing users to archetype-specific agents
- [x] `.claude/commands/architecture-shared.md` — shared operating mode, reasoning engine, principles, decision framework
- [x] `.claude/commands/architecture-domain-system.md` — full implementation: 9 Tier 2 decisions (Bounded Context Canvas dimensions), derivation rules, regret minimization, classification-first flow
- [x] `.claude/commands/architecture-system-evolution.md` — full implementation: migration classification taxonomy, decision library (not a sequence), classification-first creation flow
- [x] `.claude/commands/architecture-data-pipeline.md` — stub (not yet implemented)
- [x] `.claude/commands/architecture-system-integration.md` — stub (not yet implemented)
- [x] `.claude/commands/architecture-process-system.md` — stub (not yet implemented)
- [x] `engine/schemas/design-domain_system.json` — updated with `cross_context_query` and `contract_versioning` fields
- [x] `engine/schemas/design-system_evolution.json` — rewritten: `decision_object_shape`, migration-specific fields, `open_decisions`

---

### Step 16 — New Model Agent Commands `TODO`

**Milestone:** `/model-system` and `/model-workflow` are runnable. The layered case (`system_integration + process_system`) is fully supported end-to-end.

**Why here:** Depends on Step 13 (commands reference `write_artifact`). Design is complete from this session.

#### Tasks
- [ ] Write `.claude/commands/model-system.md`:
  - Identity: System Integration Modeler
  - PRD scan: 5 questions (system inventory, contract, imposed constraints, availability, schema ownership)
  - Complexity calibration table
  - 5 challenge criteria with trigger/bad/good/anti-pattern/question
  - Agent failure modes (treating integration as function call, ignoring rate limits, assuming availability, schema ownership blindness)
  - Plain language principle + example summary
  - Quality bar: Architecture Agent can choose protocol, ACL depth, error handling, sync pattern without asking
  - Uses `write_artifact(stage: "model_system")`, `approve_artifact`, `update_schema`
- [ ] Write `.claude/commands/model-workflow.md`:
  - Identity: Process System Modeler
  - PRD scan: 5 questions (process boundaries, actors, step conditions, timeout/abandonment, audit)
  - Complexity calibration table
  - 5 challenge criteria with trigger/bad/good/anti-pattern/question
  - Layered case detection: if PRD `secondary_archetype` present, load approved `model_system` artifact; add integration coupling challenge criterion
  - Agent failure modes (workflow as function sequence, skipping actors, missing timeout, audit as optional)
  - Plain language principle + example summary
  - Quality bar: Architecture Agent can design state machine, persistence, human tasks, timeout/escalation without asking
  - Uses `write_artifact(stage: "model_workflow")`, `approve_artifact`, `update_schema`
- [ ] Tests:
  - Lifecycle: `TestModelSystemV1`, `TestModelSystemV2`, `TestApproveModelSystem`
  - Lifecycle: `TestModelWorkflowV1`, `TestModelWorkflowV2`, `TestApproveModelWorkflow`
  - Lifecycle: `TestLayeredModelChain` — model_workflow `references` points to model_system, not PRD
  - Contract: `TestModelSystem→Design`, `TestModelWorkflow→Design`
  - Contract: `TestLayeredGate` — model_workflow cannot start until model_system is approved

---

### Step 17 — Tech Stack Agent Refactor `DONE`

**Milestone:** Tech stack decisions use correct decision dimensions per archetype.

#### Tasks
- [x] Design per-archetype decision dimension tables
- [x] `.claude/commands/tech-stack-agent.md`:
  - Archetype detection from design body (top-level key presence)
  - Tier 1 silent derivations per archetype (forced by design, no deliberation)
  - Per-archetype technology decision library with "live when" conditions and regret rules
  - Phase structure updated: detect → derive → state live/not-live → agenda → deliberate
  - `domain_system`: 24 decisions covering data, communication, auth, observability, testing, compliance
  - `system_evolution`: 14 decisions covering migration execution, schema, validation, deployment, operations
  - `data_pipeline`, `system_integration`, `process_system`: stubbed with "not yet implemented" message
- [ ] Tests: contract (design artifact of each archetype type → tech_stack with correct decision dimensions) — agent-side behavior, not engine-enforced; deferred

---

### Step 18 — PRD Archetype Challenge Criteria `DESIGN REQUIRED`

**Milestone:** Product Owner has a clear rubric for challenging archetype classification — what signals a misclassification, how to push back on `domain_system` when evidence points elsewhere.

**Design required before implementation:**
- Signal-to-archetype mapping (what PRD content signals which archetype)
- Challenge criteria for classification confidence (when to push back, when to accept)
- Anti-patterns per archetype (e.g., "domain_system" chosen because it's familiar, not because it fits)

#### Tasks (after design)
- [ ] Design challenge criteria for classification
- [ ] `.claude/commands/product-owner.md` — add/update archetype classification challenge section

---

### Step 19 — Documentation Updates `TODO`

**Milestone:** `docs/architecture.md` and `README.md` reflect all Phase 2 decisions. Plan file reflects completion.

#### Tasks
- [ ] `docs/architecture.md`:
  - Add: universal instance schema pattern (all stages, not model-only)
  - Add: generic `write_artifact` / `approve_artifact` decision and rationale
  - Add: archetype-in-envelope decision
  - Add: richer `get_available_artifacts` context decision
  - Add: per-archetype design body schemas (one section per archetype)
  - Add: model-system and model-workflow agent entries (session model, schema, tools)
  - Update: Evolution Log with 2026-04-20 entry covering all Phase 2 decisions
- [ ] `REFACTOR_IMPLEMENTATION_PLAN.md` — mark steps as done as they complete
- [ ] `README.md` — add `/model-system` and `/model-workflow` usage; update tool table if generic tools listed

---

## Open Design Work

| Item | Blocks | Status |
|------|--------|--------|
| Per-archetype Tech Stack decision dimensions | Step 17 | Not started |
| PRD archetype challenge criteria refinement | Step 18 | Partial (basic table exists in product-owner.md) |

---

## Validation Scenarios

After Steps 13–16, run these end-to-end to verify correctness:

**`existing-project-onboarding`** — `system_integration + process_system`
Expected DAG: `brief → prd → model_system → model_workflow → design → tech_stack`
Pass: System Model captures constraints + control map. Workflow Model encodes install steps within those constraints. Design = integration architecture + workflow execution. No aggregates, no CQRS.

**`data-dedup-engine`** — `data_pipeline`
Expected DAG: `brief → prd → model_data_flow → design → tech_stack`
Pass: Data Flow Model captures input/output/stages. Design = pipeline topology + failure handling. Tech stack = processing engine + queue + storage.

**`accounting-engine`** — `domain_system`
Expected DAG: `brief → prd → model_domain → design → tech_stack`
Pass: Domain Model = bounded contexts, aggregates, context map. Design = hexagonal layering. No change from current behavior.

**`engine-archetype-refactor`** — `system_evolution`
Expected DAG: `brief → prd → model_evolution → design → tech_stack`
Pass: Evolution Model captures current routing behavior, frozen MCP tool surface, intentional behavioral deltas, ordered migration steps with gates, and silent regression risk surface.
