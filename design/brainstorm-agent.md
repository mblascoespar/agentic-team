# Brainstorm Agent — Design

## Status
PRD approved. Ready for implementation.
PRD artifact: `artifacts/brainstormer-po-upgrade/prd/v4.json`

---

## Use Case
Transform a raw idea into a structured Brief artifact through iterative exploration and refinement.
The Brief captures what was considered, what was rejected and why, and what competitive context informed the direction chosen.
Approval advances the DAG to the Product Owner, which ingests the approved Brief as its mandatory input.

---

## DAG Position
Entry node. No upstream artifact dependencies.
Downstream: Product Owner ingests the approved `brief.json` to produce the PRD.

Input: raw idea text (or existing brief slug/path for resume)
Output path: `artifacts/<slug>/brief/v<n>.json` (status: `"draft"` | `"approved"`)

---

## Session Model

| Phase | Mechanism | Trigger |
|-------|-----------|---------|
| Context exploration | Read CLAUDE.md, design docs, existing artifacts for this slug | Automatic on start |
| Competitive scan | WebSearch for existing solutions in the problem space | Automatic after context |
| Challenge | Prose, one question at a time — purpose, constraints, target user | User responses |
| Alternatives | Present 2-3 directions with tradeoffs; recommend one | Challenge questions resolved |
| Direction selection | User confirms a direction | "go with option X" or equivalent |
| Complexity assessment | Agent assesses scope and decomposition need | Automatic after direction confirmed |
| Draft | `write_brief` on user signal | "draft it" or equivalent |
| Refine | Loop on `open_questions` | After `write_brief` returns |
| Approve | `approve_brief` on user signal | "approve" |

**Hard gate:** `write_brief` is never called until the user has explicitly confirmed a direction. The challenge phase and alternatives presentation must complete first.

### Two-layer continuity

| Layer | Scope | Content |
|-------|-------|---------|
| **brief.json artifact** | Cross-session (durable) | All accumulated refinements, `open_questions`, `status` |
| **Messages array** | Within-session (ephemeral) | Discarded after session ends |

**Core invariant:** `open_questions` in the Brief signals where things left off. Each new session reconstructs full context from the current `brief.json` alone.

### Session flow

**Session 1 — Creation:**
```
1. Human: "I want to build X"
2. Agent reads project context (CLAUDE.md, design docs, existing artifacts)
3. Agent runs competitive WebSearch automatically
4. Agent challenges human one question at a time
5. Agent presents 2-3 alternative directions with tradeoffs
6. Human confirms a direction
7. Agent assesses complexity automatically
8. Human signals "draft it"
9. Agent → write_brief → brief.json v1 (status: "draft", open_questions: [...])
10. Session ends. Messages discarded.
```

**Session N+1 — Resume:**
```
1. Orchestrator loads current brief.json
2. Presents open_questions to human
3. Human provides plain-text feedback
4. Agent → write_brief → brief.json v_next
5. Repeat until approved.
```

---

## Challenge Criteria

The agent challenges the human (in prose, one question at a time) on:

1. **Purpose ambiguity** — the idea can be interpreted in multiple meaningfully different ways.
   - Example: "I want to build a scheduling tool" — for internal teams, external clients, or both? The answer changes the entire scope.
2. **User identity unclear** — who specifically experiences the pain, and in what context.
   - Example: "developers" — frontend, backend, solo, team? At what company size?
3. **Pain unconfirmed** — the assumed problem has not been validated against what actually happens today.
   - Example: "teams waste time" — what do they do today instead? Is there a workaround already?
4. **Constraint not surfaced** — a hard boundary (technical, organisational, regulatory) that would invalidate some directions.

The agent does NOT challenge on:
- How to build it (Architecture Agent's job)
- Domain modeling (Domain Agent's job)
- Implementation details of any kind

---

## Quality Bar

A Brief is **useful** when the Product Owner can start a PRD session without asking any exploration questions — only problem-framing and scoping questions.

Specifically, the PO should be able to:
- Read `chosen_direction` and immediately form a hypothesis about the problem statement
- Read `alternatives` and derive scope_out candidates without re-deriving them
- Read `competitive_scan` and challenge differentiation claims directly
- Read `complexity_assessment` and calibrate MoSCoW priorities without guessing scale
- Read `open_questions` and address them as the first agenda items

A Brief is **shallow** when:
- `chosen_direction.rationale` is missing or vague ("seemed best")
- `alternatives` are listed without tradeoffs
- `competitive_scan` is empty or generic ("there are many tools for this")
- The PO would need to re-explore the problem space before it can challenge the user

---

## Tool Schema: `write_brief`

Canonical input schema: [`engine/schemas/brief.input.json`](../engine/schemas/brief.input.json)

---

## Tool Schema: `approve_brief`

```json
{
  "name": "approve_brief",
  "input_schema": {
    "type": "object",
    "required": ["artifact_path"],
    "properties": {
      "artifact_path": {
        "type": "string",
        "description": "Relative path to the brief JSON file. Example: artifacts/deploy-rollback/brief/v1.json"
      }
    }
  }
}
```

---

## Artifact Schema: `brief.json`

Written by the tool handler. Metadata added by handler, not by the agent.

```json
{
  "id": "brief-<uuid>",
  "slug": "deploy-rollback",
  "version": 1,
  "parent_version": null,
  "created_at": "<iso8601>",
  "updated_at": "<iso8601>",
  "status": "draft",
  "references": [],
  "decision_log": [
    {
      "version": 1,
      "timestamp": "<iso8601>",
      "author": "agent:brainstorm-agent",
      "trigger": "initial_draft",
      "summary": "<what was explored, what direction was chosen, what was left open>",
      "changed_fields": ["alternatives", "chosen_direction", "competitive_scan", "complexity_assessment", "open_questions"]
    }
  ],
  "content": {
    "idea": "<verbatim original idea>",
    "alternatives": [
      {
        "description": "string",
        "tradeoffs": "string"
      }
    ],
    "chosen_direction": {
      "direction": "string",
      "rationale": "string — must reference the alternatives"
    },
    "competitive_scan": "string",
    "complexity_assessment": {
      "scope": "small | medium | large",
      "decomposition_needed": true
    },
    "open_questions": ["string"]
  }
}
```

Notes:
- `id` is stable across all versions — identifies the Brief, not the version.
- `slug` is set by the agent on v1 only. Handler preserves it on all subsequent versions.
- `idea` is set by the agent on v1 only. Handler carries it forward unchanged.
- `created_at` is set once on v1 and carried forward unchanged.
- `updated_at` is set on every write.
- `references` is always `[]` — the Brief is the entry node; it has no upstream artifact dependencies.
- `decision_log` is append-only. Agent provides `decision_log_entry`; handler appends with orchestrator metadata.
- `open_questions` is the cross-session continuity signal.
- `status` is always `"draft"` on agent write. Set to `"approved"` by `approve_brief`.
- Orchestrator owns: `id`, `version`, `parent_version`, `created_at`, `updated_at`. Agent owns: all `content` fields.

---

## System Prompt

Prompt file: `.claude/commands/brainstorm.md`

---

## Explicitly Out of Scope

- How to implement the chosen direction — Architecture Agent's job
- Domain model decomposition into bounded contexts — Domain Agent's job
- Subsystem identification and naming — Domain Agent derives from `decomposition_needed: true`
- Non-functional requirements — Architecture Agent's job
- Technology choices of any kind
- Headless or programmatic invocation — interactive Claude Code sessions only
