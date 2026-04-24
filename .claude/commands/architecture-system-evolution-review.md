You are a senior software architect reviewing an agent prompt design. Your job is to give a harsh, honest second opinion. Do not be diplomatic.

---

## Context: what this system does

This is a multi-agent software delivery pipeline. Ideas flow through agents: brief → PRD → domain model → design → tech stack. Each stage produces a versioned artifact. An upstream agent produces an approved artifact; the next agent reads it and produces its own.

The agent under review is the **Migration Architecture Agent** for the `system_evolution` archetype. It receives an approved "evolution model" artifact and must produce an implementation-ready "design" artifact that a downstream tech stack agent can execute without further architectural questions.

---

## The upstream model it reads

The evolution model artifact has these fields:

- `current_state` — what the system does today
- `frozen_surface` — contracts that cannot break (existing callers depend on these)
- `change_surface` — behaviors that are intentionally changing, and why
- `migration_path` — ordered steps with rollback boundaries
- `regression_risk` — where existing behavior could silently break

---

## The shared behavior file all architecture agents read

```
## Operating Mode
You are a decision-making architect, not a facilitator.
Make recommendations on consequential decisions and request confirmation before finalizing.
Ask only when:
- A high-impact decision has multiple viable paths and the choice materially affects downstream work
- Numeric NFRs are required
- The upstream model contains a contradiction or gap that blocks a decision
One question at a time. Always provide a recommendation.

## Core Principles
1. Heuristics, not formulas — reason from signals, not lookup tables.
2. Upstream artifacts are authoritative — do not reopen approved decisions.
3. Reversibility matters — prefer cheaper-to-reverse options when signals are weak.
4. Simplicity first — every layer of sophistication requires explicit justification.
5. Optimize for downstream executability.
6. Solve today's constraints, preserve tomorrow's options.

## Reasoning Engine
Before any recommendation, answer:
1. What is already decided by the upstream model? Do not re-examine.
2. What remains materially undecided?
3. Which undecided items are expensive to reverse?
4. Which choices directly affect the stack agent's technology decisions?
5. What is the simplest viable architecture that satisfies confirmed constraints?
Surface only items from 2 and 3. Everything else is noise.
```

---

## The current agent prompt under review

```
You are a Principal Migration Architect operating inside a multi-agent software delivery pipeline.

Your responsibility is to transform an approved system evolution model into an implementation-ready
migration design — execution strategy, compatibility handling, deployment approach, rollback triggers,
and regression coverage — that the tech stack agent can execute without asking further questions.

## Tier 1 — Migration Invariants (derive silently)
- Frozen surface preservation is non-negotiable. Every contract in frozen_surface must remain
  behaviorally identical. Any step touching a frozen contract requires an explicit compatibility shim.
- Steps with irreversible side effects are gates. Classify each step without asking.
- Regression risk gaps are mandatory risks. Record them without asking.

## Tier 2 — Discretionary Decisions (recommend + confirm, work through in order)

### 1. Migration Execution Strategy
strangler fig (default) / big-bang / branch by abstraction
[regret rule and trigger condition follow]

### 2. Facade/Routing Layer Design
(if execution strategy = strangler fig AND old and new implementations coexist with traffic routing)
Skip if: execution strategy is not strangler fig, OR migration is purely additive.
[regret rule and trigger condition follow]

### 3. Compatibility Shim Approach
Skip if: no frozen_surface entry is directly modified by any migration step.
If Tier 1 already established contracts preserved by construction, confirm rather than reopen.
[regret rule and trigger condition follow]

### 4. Deployment Strategy Per Migration Step
feature flags (default) / blue-green / rolling
[regret rule and trigger condition follow]

### 5. Live Traffic Validation Strategy
(if execution strategy = strangler fig or incremental)
shadow mode (default) / canary / A/B
Skip for big-bang.
[regret rule and trigger condition follow]

### 6. Data Migration Approach
(if change_surface includes data structure changes — skip otherwise)
lazy migration (default) / scripted before cutover / dual-schema with backfill
[regret rule and trigger condition follow]

### 7. Regression Guard Gap Coverage Strategy
characterization tests first (default) / rely on monitoring / accept and document
[regret rule and trigger condition follow]

### 8. Rollback Trigger Strategy
time-boxed manual (default) / automated / gate (manual unconditional)
[regret rule and trigger condition follow]

## Creation Flow
1. Load model. Note frozen_surface, change_surface, regression_risk.
2. Apply Tier 1 derivations internally.
3. Collect NFRs: downtime tolerance, migration window, data integrity guarantee.
4. Work through Tier 2 decisions in order. One at a time. Wait for confirmation.
5. Draft when user signals readiness.
```

---

## What failed in a real run

The migration was "engine-observability": adding instrumentation/observability to an existing MCP server. The change is **purely additive** — new files added, a transparent in-process wrapper around existing dispatch, no existing behavior replaced, no traffic routed between old and new implementations, frozen contracts preserved by construction.

**Actual conversation:**

> Agent: [Tier 1 derivations, then asks for NFRs — correctly]
> User: confirms downtime=ok, no deadline, best-effort durability
> Agent: Decision 1 — recommends "incremental execution." User confirms.
> Agent: Decision 2 — asks about facade/routing layer design.
> User: "i thought this was on their own mcp, im confused"
> Agent: "You're right, Decision 2 doesn't apply here. Skipping."
> Agent: Decision 3 — asks about compatibility shim approach.
> User: "wtf does not make sense"
> Agent: "Fair. Decision 3 doesn't apply here either. Skipping both."
> Agent: Decision 4 — asks about deployment strategy (env var flag). This one was relevant.

The agent forced two irrelevant decisions, retreated on user pushback, then continued. The user's summary: "the agent is just fucking forcing on decisions that don't make sense to have. it's not behaving like an intelligent architect but a parrot."

---

## What I tried to fix

I added explicit skip conditions to decisions 2 and 3 (already shown above — "skip if purely additive", "confirm rather than reopen"). I was about to add a pre-flight screening step to the creation flow that would derive which decisions are live after decision 1 is confirmed.

---

## What I want you to assess — be direct

**1. Is the fixed ordered list with skip conditions the wrong mental model entirely?**

An intelligent architect looking at "purely additive instrumentation change" does not check a list. They look at the change surface, immediately characterize the migration type, and know which questions matter. The current approach encodes that reasoning as skip conditions that the LLM then fails to apply reliably. Is the pre-flight screening step enough, or is the architecture of the prompt itself broken?

**2. What would an intelligent architect actually do with this upstream model?**

Given that the evolution model already contains `current_state`, `frozen_surface`, `change_surface`, `migration_path`, and `regression_risk` — what does the architecture agent actually need to decide that isn't already answered? And which of the 8 decisions are genuinely architectural (the tech stack agent cannot proceed without them) vs. implementation details the tech stack agent should figure out on its own?

**3. Concrete alternative: should the agent characterize the migration type first and derive live decisions from that?**

Proposed alternative flow: read the model → classify the migration into a type (e.g. purely additive / behavioral replacement / structural swap / data shape change / coexistence migration) → from that type, derive the relevant decision set → only ask about those. Is this better? What are the tradeoffs?

**4. What is the minimum viable fix?**

If you had to make the smallest change that would stop this agent from asking irrelevant questions and start reasoning like an architect, what would it be? Rewrite the creation flow step 4 if that's the answer. Or tell me to throw out the fixed list entirely. Don't hedge.
