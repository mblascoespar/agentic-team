# Domain Agent — Design

## Status
PRD approved. Ready for system prompt and implementation.
PRD artifact: `artifacts/domain-agent/prd/v2.json`

---

## Use Case
Transform an approved PRD artifact into a structured Domain Model artifact through iterative agent-driven refinement.
Supports multi-session continuity: draft → human feedback → agent refines → repeat → approved.
Approval advances the DAG to the Architecture Agent.

---

## DAG Position
Second node. Upstream: Product Agent (consumes approved `prd.json`).
Downstream: Architecture Agent consumes the approved `domain.json`.

Input path:  `artifacts/<slug>/prd/v<n>.json` (status: `"approved"`)
Output path: `artifacts/<slug>/domain/v<n>.json` (status: `"draft"` | `"approved"`)

---

## Session Model

Identical to the Product Agent session model.

| Phase | Mechanism | Tool call |
|-------|-----------|-----------|
| Challenge | Claude Code conversation (prose) | None |
| Draft | User signals "draft it" | `write_domain_model` MCP tool |
| Refine | User answers open questions | `write_domain_model` MCP tool |
| Approve | User signals "approve" | `approve_domain_model` MCP tool |

### Two-layer continuity

| Layer | Scope | Content |
|-------|-------|---------|
| **domain.json artifact** | Cross-session (durable) | All accumulated refinements, `open_questions`, `status` |
| **Messages array** | Within-session (ephemeral) | Discarded after session ends |

**Core invariant:** `open_questions` in the domain model signals where things left off. Each new session reads the current domain.json + the source prd.json and reconstructs full context from artifacts alone.

### Session flow

**Session 1 — Creation (PRD just approved):**
```
1. Agent reads approved prd.json
2. Agent reasons over features, goals, scope → identifies candidate contexts, behaviors, ambiguities
3. Agent challenges human on ownership ambiguities (one question at a time)
4. Human signals "draft it"
5. Agent → write_domain_model → domain.json v1 (status: "draft", open_questions: [...])
6. Session ends. Messages discarded.
```

**Session N+1 — Resume:**
```
1. Orchestrator loads current domain.json + source prd.json
2. Presents open_questions to human
3. Human provides plain-text feedback
4. Agent → write_domain_model → domain.json v_next
5. Repeat until approved.
```

---

## Challenge Criteria

The agent challenges the human (in prose, one question at a time) when:

1. **Ownership ambiguity** — a PRD feature implies multiple possible domain owners or context assignments.
   - Example: "Users manage their team" — is `Team` a first-class aggregate or a collection of `User`?
2. **Context boundary unclear** — a behavior could belong to two different bounded contexts.
   - Example: "Payment is processed" — does `Payment` live in an `Order` context or a `Billing` context?
3. **Invariant not determinable** — a business rule cannot be inferred from PRD language alone.
   - Example: "Orders can be cancelled" — under what conditions? Is there a time window or state constraint?

The agent does NOT challenge on:
- Technology choices (Architecture Agent's job)
- UX/UI details (already in PRD)
- Storage or performance characteristics (Architecture Agent's job)

---

## Transformation Rules

PRD language → domain language. Never re-express PRD content verbatim.

| PRD content | Domain model transformation |
|---|---|
| Feature: "user can approve an expense" | Command: `ApproveExpense` on `Expense` aggregate in `Approval` context |
| Goal: "reduce approval latency" | Influences context relationship type (e.g. async event over sync call) — surfaced as open_question if ambiguous |
| User: "Finance manager" | Role constraint on a command — not a domain entity |
| Scope out: "no multi-currency" | Invariant on `Money` value object or explicit exclusion in context |

The domain model must contain zero PRD language. All features must be traceable to at least one domain behavior (command, query, or event).

---

## Quality Bar

A domain model is **useful** when the Architecture Agent can read it and:
- Decide service/module decomposition without guessing context boundaries
- Derive API surface (commands and queries) directly from the model
- Choose integration patterns between contexts from the typed context map
- Identify enforcement points for invariants

A domain model is **shallow** when:
- It lists entities without bounded context assignments
- It has no behaviors (commands/queries/events)
- Context relationships are absent or untyped
- The Architecture Agent must ask domain questions to proceed

---

## Tool Schema: `write_domain_model`

Canonical input schema: [`engine/schemas/domain.input.json`](../engine/schemas/domain.input.json)

---

## Tool Schema: `approve_domain_model`

```json
{
  "name": "approve_domain_model",
  "input_schema": {
    "type": "object",
    "required": ["artifact_path"],
    "properties": {
      "artifact_path": {
        "type": "string",
        "description": "Relative path to the domain model JSON file. Example: artifacts/deploy-rollback/domain/v1.json"
      }
    }
  }
}
```

---

## Artifact Schema: `domain.json`

Written by the tool handler. Metadata added by handler, not by the agent.

```json
{
  "id": "domain-<uuid>",
  "slug": "deploy-rollback",
  "version": 1,
  "parent_version": null,
  "created_at": "<iso8601>",
  "updated_at": "<iso8601>",
  "status": "draft",
  "references": ["artifacts/deploy-rollback/prd/v2.json"],
  "decision_log": [
    {
      "version": 1,
      "timestamp": "<iso8601>",
      "author": "agent:domain-agent",
      "trigger": "initial_draft",
      "summary": "<what was modeled and what was left as open questions>",
      "changed_fields": ["bounded_contexts", "context_map", "open_questions"]
    }
  ],
  "content": {
    "bounded_contexts": [
      {
        "name": "string",
        "responsibility": "single-sentence description",
        "aggregates": [
          {
            "name": "string",
            "root_entity": "string",
            "entities": ["string"],
            "invariants": ["string — business rules only"]
          }
        ],
        "commands": [{ "name": "string", "description": "string" }],
        "queries":  [{ "name": "string", "description": "string" }],
        "events":   [{ "name": "string", "description": "string" }]
      }
    ],
    "context_map": [
      {
        "upstream": "string",
        "downstream": "string",
        "relationship": "shared-kernel | customer-supplier | anti-corruption-layer | open-host | conformist"
      }
    ],
    "open_questions": ["string"]
  }
}
```

Notes:
- `id` is stable across all versions — identifies the domain model, not the version.
- `created_at` is set once on v1 and carried forward unchanged.
- `updated_at` is set on every write.
- `references` contains the path to the approved prd.json that produced this domain model. Set by the handler on v1 from the tool input context; carried forward unchanged.
- `decision_log` is append-only. Agent provides `decision_log_entry`; handler appends with orchestrator metadata.
- `open_questions` is the cross-session continuity signal.
- `status` is always `"draft"` on agent write. Set to `"approved"` by `approve_domain_model`.
- Orchestrator owns: `id`, `version`, `parent_version`, `created_at`, `updated_at`. Agent owns: all `content` fields.
- Entity lifecycle characteristics (read/write patterns, consistency levels) are **not** in this artifact — Architecture Agent derives them.

---

## Explicitly Out of Scope

- Storage strategy, service decomposition, API protocols — Architecture Agent
- Entity lifecycle characteristics (read/write patterns, consistency) — Architecture Agent
- Technology choices of any kind
- UI/UX modeling
- Non-functional requirements (latency, throughput, availability)
- Access to inputs other than `prd.json` (no code, schemas, external signals)
- Nested contexts or sub-domain hierarchies (v1: flat context map only)
- Invariants that are technical constraints (e.g. "ID must be UUID") — business rules only
