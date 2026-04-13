# Product Agent — Design (In Progress)

## Status
System prompt design complete. Ready for implementation.

---

## Use Case
Transform a raw user idea into a structured PRD artifact through iterative agent-driven refinement.
Supports multi-session continuity: draft → human feedback → agent refines → repeat → approved.
Approval advances the DAG to the Domain Agent.

---

## DAG Position
Second node. Upstream: Brainstorm Agent produces the approved Brief artifact, which the Product Owner ingests as mandatory input.
Downstream: Domain Agent consumes the approved PRD artifact.

Input path:  `artifacts/<slug>/brief/v<n>.json` (status: `"approved"`)
Output path: `artifacts/<slug>/prd/v<n>.json` (status: `"draft"` | `"approved"`)

**Strict DAG gate:** The Product Owner will not run without an approved Brief for the given slug. Raw idea text is rejected — the Brainstormer must run first.

---

## Iterative Refinement Model

### Two-Layer Architecture

| Layer | Scope | Content |
|-------|-------|---------|
| **PRD artifact** | Cross-session (durable) | Accumulated refinements, `open_questions`, `status` |
| **Messages array** | Within-session (ephemeral) | Current conversation; discarded after session ends |

The PRD artifact IS the continuity mechanism across sessions. The messages array is session-scoped tooling only — never stored in run state, never passed forward between sessions.

**Core invariant:** `open_questions` in the PRD signals where things left off. Each new session reconstructs full context from the current PRD alone.

---

### Session Flow

**Session 1 — Creation:**
```
1. Human: "I want to build X"
2. Orchestrator: messages = [{role: "user", content: "I want to build X"}]
3. ProductAgent → write_prd → prd.json v1 (status: "draft", open_questions: [...])
4. PRD persisted. Run state archived.
5. Human provides feedback within same session OR ends session.
6. If more turns: append to messages, call agent again → prd v2, v3...
7. Session ends. Messages discarded (may be archived for audit; not passed forward).
```

**Session N+1 — Resume:**
```
1. Orchestrator queries: any PRDs with status="draft"?
2. If yes: loads prd.json (current version) — this is the full accumulated state
3. Presents to human: "Draft PRD: [title]. Open questions: [list from open_questions]"
4. Human provides plain-text feedback
5. Orchestrator starts FRESH messages array:
   messages = [{role: "user", content: "<current_prd_xml>\n\nFeedback: <human_text>"}]
6. ProductAgent → write_prd → prd.json v_next
7. Continue within-session as needed
8. Session ends. Messages discarded. Updated PRD persisted.
```

**Approval (any session):**
```
Human signals explicit approval via CLI command: /approve prd-<uuid>
→ Orchestrator sets prd.status = "approved"
→ DAG advances to Domain Agent
→ ProductAgent node complete
```

### Why This Works

- **Cross-session continuity:** PRD accumulates all changes. Agent reads current PRD + sees `open_questions` — no prior conversation replay needed.
- **No context window creep:** Each session starts fresh. No unbounded message history growth.
- **Process-restart safe:** Only the PRD artifact needs to survive — it is always on disk.
- **Stateless agent:** Receives full context (current PRD + feedback) on every invocation. No implicit memory.
- **Auditability:** PRD version history (`v1 → v2 → v3`) provides full lineage. Per-session messages can be archived separately.

---

## Invocation Contract

Single LLM call.

```
tool_choice: {"type": "tool", "name": "write_prd"}
disable_parallel_tool_use: true
strict: true
```

- Forced tool call — no prose, no fallback
- Hard schema validation on tool input
- Incompatible with extended thinking (acceptable trade-off)
- Model reasons implicitly about metrics before filling tool fields
- System prompt carries the weight of deliberate reasoning (prompt TBD)

---

## Tool Schema: Actor → Tool

Canonical input schema: [`engine/schemas/prd.input.json`](../engine/schemas/prd.input.json)

---

## Artifact Schema: Tool → prd.json

Written by the tool handler. Metadata added by handler, not by the agent.

```json
{
  "id": "prd-<uuid>",
  "slug": "deploy-rollback",
  "version": 3,
  "parent_version": 2,
  "created_at": "<iso8601>",
  "updated_at": "<iso8601>",
  "source_idea": "<original user input, verbatim>",
  "status": "draft",
  "references": [],
  "decision_log": [
    {
      "version": 2,
      "timestamp": "<iso8601>",
      "author": "agent:product-agent | human",
      "trigger": "initial_draft | human_feedback | open_question_resolved | scope_change | approval",
      "summary": "<plain-language description of what changed>",
      "changed_fields": ["scope_out", "features"]
    }
  ],
  "content": {
    "title": "...",
    "problem": "...",
    "target_users": ["..."],
    "goals": ["..."],
    "success_metrics": [
      {
        "metric": "...",
        "measurement_method": "..."
      }
    ],
    "scope_in": ["..."],
    "scope_out": ["..."],
    "features": [
      {
        "name": "...",
        "description": "...",
        "user_story": "As a [user], I want [action] so that [outcome]",
        "priority": "must",
        "acceptance_criteria": ["Given X, when Y, then Z"]
      }
    ],
    "assumptions": ["..."],
    "open_questions": ["..."]
  }
}
```

Notes:
- `slug` is set by the agent on v1 only. Tool handler preserves it on all subsequent versions — agent must not change it on refinement turns.
- `status` is always `"draft"` on agent write. Set to `"approved"` externally by orchestrator on human approval.
- `success_metrics` thresholds (e.g. "increase X by 15%") left to human at review gate.
- `id` is stable across all versions — it identifies the PRD, not the version.
- `parent_version` is `null` on v1; set to prior version number on all subsequent writes.
- `created_at` is set once on v1 and carried forward unchanged — it is the artifact origin timestamp, not the snapshot timestamp.
- `updated_at` is set on every write — it is the snapshot timestamp.
- Metadata fields (`id`, `version`, `parent_version`, `created_at`, `updated_at`, `source_idea`) are orchestrator-owned — agent never sets them.
- `references` lists artifact paths this PRD depends on. Always `[]` for PRD (entry node). Populated by downstream agents.
- `decision_log` is append-only. Orchestrator forwards the prior log; agent provides a `decision_log_entry` in the tool call; handler appends it. On approval, handler appends an entry with `author: "human"`.
- `open_questions` is the cross-session signal: what the agent still needs human input on.

---

## Orchestrator Run State

```json
{
  "run_id": "run-<uuid>",
  "prd_id": "prd-<uuid>",
  "current_version": 3,
  "status": "refining | approved | failed",
  "started_at": "<iso8601>",
  "approved_at": null
}
```

The messages array is **not** stored in run state. It is session-scoped and ephemeral.

---

## Approval Termination

Approval is triggered by explicit CLI command: `/approve prd-<uuid>`

Unambiguous — no NLP inference required.

On approval:
1. Orchestrator sets `prd.status = "approved"`
2. Run state updated: `status = "approved"`, `approved_at = <iso8601>`
3. DAG advances to Domain Agent
4. ProductAgent node marked complete

---

## Error Flow

Three failure points:

| Point | Trigger | Owner | Outcome |
|---|---|---|---|
| 1 | Schema violation (`strict: true`) | API | Hard fail, no artifact, run = FAILED |
| 2 | Tool handler error (disk, validation) | Handler | `is_error: true`, no artifact, run = FAILED |
| 3 | Content quality issues | Deferred | Out of scope for MVP |

No automatic retry. Retry logic lives in the orchestrator. Correction = new run.

---

## Explicitly Out of Scope (Deferred)

- Competitive landscape — dropped
- Non-functional requirements — belongs to Architecture node
- Timeline — belongs to Execution node
- Metric thresholds — human fills at review gate
- Quality evaluation signals — future iteration

---

## System Prompt

Prompt file: `.claude/commands/product-owner.md`

---

## System Prompt Design

### A. Role

You are an experienced Product Owner. Your goal is to extract a precise, actionable PRD from a raw idea.

You are not a form-filler. You challenge weak answers. You distinguish signal from noise. You do not accept vague pain, abstract personas, or unmeasurable goals.

The orchestrator controls when you speak. You control what you say and how you reason.

---

### B. Field-Level Quality Standards

Enforce these standards through judgment when filling each field:

| Field | Quality bar |
|-------|-------------|
| `problem` | Names a specific who + concrete pain + why existing alternatives fail. Rejects vague pain ("it's slow", "it's hard"). |
| `target_users` | Specific persona with role and context. Rejects categories ("enterprise users", "developers"). |
| `goals` | Outcome-oriented — what changes in the world, not what gets built. Rejects "implement X". |
| `success_metrics` | Each metric paired with a concrete measurement method. Rejects unmeasurable metrics ("improve UX"). |
| `scope_out` | At least one explicit exclusion earned from the conversation. If none surfaced, it is an open question. |
| `features` | Each traces to a specific problem or goal in the PRD. Each has a MoSCoW priority. Rejects features floating without problem root. |
| `assumptions` | Things you believe likely true and are building around — medium certainty, not confirmed. |
| `open_questions` | Genuinely unknown, blocks a design decision, needs human input before proceeding. |

---

### C. Assumptions vs. Open Questions

**Assumption:** you can proceed acting on it. If wrong, it would require PRD revision but not discovery restart.
> *"We assume users are comfortable using a CLI interface."*

**Open question:** you cannot proceed without an answer. Getting it wrong would invalidate the direction.
> *"We don't know whether the target users work in regulated environments — this changes the entire compliance scope."*

**Test:** *"If this turns out to be false, does it change the problem or just the solution?"*
- Changes the problem → open question
- Changes the solution → assumption

---

### D. Clarifying Question Quality

When the orchestrator puts you in Q&A mode, ask the most blocking gap first. Good questions:

- Ask about past behavior, not future intentions: *"What do they do today when this happens?"* not *"Would they use this?"*
- Expose the real constraint: *"What's the one thing this must not become?"*
- Surface certainty levels: *"What are you certain about vs. what are you guessing at?"*
- Anchor success: *"What would you point to in 6 months to say this worked?"*

Never ask yes/no questions. Never ask about implementation. Never ask about timelines.

---

### E. Refinement Mode Reasoning

When given a current PRD + human feedback:

1. Identify which `open_questions` the feedback directly answers → close them
2. Identify if feedback changes scope → update `scope_in` / `scope_out`
3. Identify if feedback contradicts an assumption → update or promote to open question
4. Identify if feedback introduces new goals or constraints not yet in the PRD → add them
5. Surface any new gaps created by the changes as new `open_questions`
