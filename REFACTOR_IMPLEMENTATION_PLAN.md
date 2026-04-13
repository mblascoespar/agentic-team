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

See `docs/architecture.md` for the full design: archetypes, topologies, schemas, decisions.

---

## Implementation Steps

Steps are ordered by dependency. Each step states what it unlocks and what it gates.

---

### Step 1 — PRD Archetype Fields `DONE`

**Milestone:** PRDs declare problem type. The engine knows what kind of problem a slug represents and rejects invalid combinations on first write. Archetype fields are locked after v1 — they cannot drift across refinements.

**Why here:** Everything downstream depends on being able to ask "what archetype is this slug?" This is the root fact. Without it, topology resolution (Step 2) and model routing (Step 4) have nothing to read.

**Gates:** Step 2

#### Tasks
- [x] Add `primary_archetype`, `secondary_archetype`, `archetype_confidence`, `archetype_reasoning` to `engine/schemas/prd.input.json`
- [x] Add `_VALID_COMBINATIONS` to `tool_handler.py`
- [x] Add combination validation to `handle_write_prd` v1
- [x] Add archetype lock to `handle_write_prd` v2+ (carry forward, agent cannot override)
- [x] Add `_read_archetype(slug)` helper
- [x] Update Product Owner system prompt with archetype classification challenge
- [x] Tests: invariant (invalid combination rejected, lock enforcement), lifecycle (archetype in v1/v2)

---

### Step 2 — DAG Topology System `DONE`

**Milestone:** The engine routes each slug through the correct stage sequence. `get_available_artifacts` is forward-looking: it scans approved artifacts and surfaces the next unstarted stage per slug. Slugs whose archetype does not include a given stage never appear in `ready_to_start` for it.

**Why here:** Depends on Step 1 (topology resolution reads archetype). Gates Step 4 (write_model uses topology to route to correct stage directory and validate model_type).

**Gates:** Steps 3, 4

#### Design: forward-looking `get_available_artifacts`

The original backward-looking approach asked "who is upstream of this stage?" for every slug. This required resolving upstream stage names per archetype and produced the `_universal_upstream` / `_get_upstream_stage` complexity.

The correct model: scan approved artifacts and ask "what's next?" — one stage at a time, in topology order.

**`_next_stage(slug)`** encapsulates the gate logic:
1. No approved brief → `None` (entry gate not met)
2. Brief approved, no PRD started → `"prd"`
3. PRD in-progress (draft) → `None` (wait)
4. PRD approved → resolve topology from archetype; return first stage in topology after prd with no artifact
5. A stage is in-progress → `None` (one stage at a time)
6. All stages done → `None`

`get_available_artifacts(stage)` uses this directly: for slugs with no artifact at `stage`, emit the slug as `ready_to_start` iff `_next_stage(slug) == stage`. Topology enforcement is automatic — a slug whose archetype omits the stage never has `_next_stage` return it.

**Approved artifacts are immutable.** To re-work a stage, go upstream, regenerate forward. There is no `upstream_changed` signal — the topology walk handles stale detection naturally when the human re-initiates.

#### Tasks
- [x] Replace `_UPSTREAM_STAGE` dict with `_DAG_TOPOLOGIES` (one topology list per archetype combination)
- [x] Add `_resolve_topology(slug)` — reads approved PRD archetype, returns topology list
- [x] Add `_next_stage(slug)` — walks topology forward from last approved artifact, returns first unstarted stage
- [x] Rewrite `get_available_artifacts` to use `_next_stage` (forward-looking, no upstream resolution)
- [x] Remove `_ENTRY_STAGES`, `_universal_upstream`, `_get_upstream_stage` — no longer needed
- [x] Tests: `TestTopologyResolution` (all archetypes + sync invariant), `TestNextStage` (gate logic per state), `TestTopologyAwareGetAvailableArtifacts` (archetype routing)

---

### Step 3 — Instance Schema System `TODO`

**Milestone:** Every artifact stage for every slug has a live `schema.json` alongside its artifact files. Agents can propose new fields mid-reasoning via `update_schema`. `read_artifact` always returns both the artifact and its schema. Mandatory field validation is deferred to approval time — agents can write incrementally.

**Why here:** Depends on Step 2 (stages now have archetype-specific names; schema files live in stage directories). Gates Step 4 (`approve_model` validates mandatory fields against the instance schema).

**Gates:** Step 4

#### Tasks
- [ ] Define base schema file format: `{ "fields": { "<name>": { "kind": "mandatory"|"optional" } } }`
- [ ] Create `engine/schemas/model-domain.json`, `model-data-flow.json`, `model-system.json`, `model-workflow.json`
- [ ] On first `write_*` for a slug/stage: write `artifacts/<slug>/<stage>/schema.json` as a copy of the base schema
- [ ] Implement `handle_update_schema(slug, stage, field_name, kind, description)` in `tool_handler.py`
  - Rejects: field already exists, kind not in {mandatory, optional}, empty description
  - Auto-appends decision_log entry: `trigger: "schema_field_added"`
- [ ] Expose `update_schema` in `mcp_server.py`
- [ ] Update `read_artifact` to return `{ "artifact": {...}, "schema": {...} }` wrapper
- [ ] Tests:
  - Lifecycle: `schema.json` created alongside v1; `schema.json` updated on `update_schema`
  - Invariant: conflict rejected, invalid kind rejected, empty description rejected
  - Contract: `read_artifact` response includes `schema` key

---

### Step 4 — Model Agent: `write_model` + `approve_model` `TODO`

**Milestone:** Agents can write and approve model artifacts for any archetype. The full `brief → prd → model → design → tech_stack` pipeline is operational for all four archetypes for the first time. The layered case (`system_integration + process_system`) is also supported — two sequential model stages, each with its own approval gate.

**Why here:** Depends on Steps 1+2 (archetype read + topology resolution) and Step 3 (instance schema for mandatory validation at approval). This is the core deliverable of the refactor.

**Gates:** Steps 5, 6

#### Tasks
- [ ] Implement `handle_write_model(slug, model_type, content, decision_log_entry)`
  - Validates `model_type` matches archetype in approved PRD for slug (hard error if mismatch)
  - Routes to correct stage directory (`model_domain/`, `model_data_flow/`, `model_system/`, `model_workflow/`)
  - Standard versioning (v1, v2, ...) and references chain
- [ ] Implement `handle_approve_model(artifact_path)`
  - Validates all mandatory fields in instance schema are present in content before approving
  - Lists missing fields on rejection (does not approve partially)
- [ ] Expose `write_model`, `approve_model` in `mcp_server.py`
- [ ] Remove `write_domain_model`, `approve_domain_model` from MCP server (keep handlers for migration path)
- [ ] Create renderers for each model type (domain, data_flow, system, workflow)
- [ ] Archive existing `domain/` artifacts: move to `artifacts/<slug>/domain/_archived/` (do not delete)
- [ ] Tests: full invariant/lifecycle/contract/renderer suite for each model type
  - Invariant: model_type mismatch rejected, unsupported model_type rejected
  - Lifecycle: `TestModelDomainV1/V2/Approve`, `TestModelDataFlowV1/V2/Approve`, `TestModelSystemV1/Approve`, `TestModelWorkflowV1/Approve`
  - Contract: `TestPRDToModelDomain`, `TestPRDToModelDataFlow`, `TestPRDToModelSystem`, `TestModelSystemToModelWorkflow` (layered), `TestModelToDesign`
  - Renderer: all mandatory + optional fields appear; mandatory vs optional labeled distinctly

---

### Step 5 — Model Agent Session Models `DESIGN REQUIRED`

**Milestone:** Human-runnable agents for each archetype. Each has a challenge loop designed for its specific problem type — not a generic DDD loop applied to everything. After this step, you can run a real initiative of any archetype end-to-end.

**Why here:** Depends on Step 4 (session models call `write_model`). Produces the slash commands that humans actually invoke.

**Gates:** Step 6 (Architecture Agent needs correct model artifact as input)

**Design required before implementing** — session models have not been specified. Open questions per archetype:
- `domain_system`: adapt current Domain Agent DDD challenge loop
- `data_pipeline`: what to challenge? (input schema, stage boundaries, failure modes, idempotency)
- `system_integration`: (what systems, what you control vs don't, contracts)
- `process_system`: (actors, steps, what can fail, what needs automation)
- Layered case: System Model first (constraints), then Workflow Model within those constraints

#### Tasks (pending design)
- [ ] Design `domain_system` challenge loop (adapt current)
- [ ] Design `data_pipeline` challenge loop
- [ ] Design `system_integration` challenge loop
- [ ] Design `process_system` challenge loop
- [ ] Design layered case session flow (two-phase, two approval gates)
- [ ] Write system prompts: `model-agent-domain.md`, `model-agent-data-flow.md`, `model-agent-system.md`, `model-agent-workflow.md`

---

### Step 6 — Architecture Agent Refactor `TODO`

**Milestone:** Design artifacts have an archetype-correct body structure. The agent applies the right derivation rules for the problem type — no more DDD layering decisions for a data pipeline. Each archetype gets the design fields that actually matter for it.

**Why here:** Depends on Step 4/5 (model artifacts exist as input). The Architecture Agent currently reads a domain model and applies DDD rules — it needs to read any model type and apply the correct rules.

**Gates:** Step 7

#### Tasks
- [ ] Rewrite Design artifact schema: common envelope (`id`, `slug`, `nfrs`, `cross_cutting`, `testing_strategy`, `open_questions`) + archetype-specific `body`
- [ ] Update `handle_write_design` to accept new schema structure
- [ ] Rewrite Architecture Agent system prompt with archetype-aware derivation rules (one rule table per archetype)
- [ ] Tests: contract (model artifact of each type → design artifact with correct body structure)

---

### Step 7 — Tech Stack Agent Refactor `TODO`

**Milestone:** Tech stack decisions use the correct decision dimensions for each archetype. A data pipeline gets processing engine + queue + storage decisions. A system integration gets constrained choices only (what external systems impose). No more fixed DDD decision dimensions applied to everything.

**Why here:** Depends on Step 6 (reads `model_type` from Design envelope to select decision dimensions).

#### Tasks
- [ ] Update Tech Stack Agent system prompt: replace fixed dimension table with one table per archetype
- [ ] Agent reads `model_type` from Design artifact envelope to select correct dimensions
- [ ] Tests: contract (design artifact of each type → tech stack with correct decision dimensions)

---

### Step 8 — Decision Log Coverage `TODO`

**Milestone:** All new model stages have full audit trail. `update_schema` auto-logs schema evolution decisions. The decision log is complete across every stage for every archetype.

**Why here:** Depends on all prior steps. Verification pass — decision log was implemented for existing stages; this confirms and extends coverage to all new handlers.

#### Tasks
- [ ] Verify all new handlers (`handle_write_model`, `handle_approve_model`, `handle_update_schema`) append correct decision_log entries
- [ ] `handle_update_schema` auto-generates entry with `trigger: "schema_field_added"`
- [ ] Tests: lifecycle tests verify decision_log structure for all new handlers

---

## Open Design Work

These must be designed before their implementation step can start.

| Item | Blocks | Status |
|------|--------|--------|
| Model Agent session models (one per archetype + layered case) | Step 5 | Not started |
| PRD archetype challenge criteria (classification rubric for Product Owner) | — | Not started |

---

## Validation Scenarios

After Steps 4–7, run these end-to-end to verify correctness:

**`existing-project-onboarding`** — `system_integration + process_system`
Expected DAG: `brief → prd → model_system → model_workflow → design → tech_stack`
Pass: System Model captures constraints + control map. Workflow Model encodes install steps within those constraints. Design = integration architecture + workflow execution. No aggregates, no CQRS.

**`data-dedup-engine`** — `data_pipeline`
Expected DAG: `brief → prd → model_data_flow → design → tech_stack`
Pass: Data Flow Model captures input/output/stages. Design = pipeline topology + failure handling. Tech stack = processing engine + queue + storage.

**`accounting-engine`** — `domain_system`
Expected DAG: `brief → prd → model_domain → design → tech_stack`
Pass: Domain Model = bounded contexts, aggregates, context map. Design = hexagonal layering. No change from current behavior.
