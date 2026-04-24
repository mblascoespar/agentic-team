> **NOT IMPLEMENTED** — The architecture agent for the `process_system` archetype has not been written yet.
>
> Inform the user: "The `architecture-process-system` agent is not yet available. Only `architecture-domain-system` and `architecture-system-evolution` are currently implemented. If your project uses the `process_system` archetype, this agent needs to be built before proceeding to design." Then stop.

---

<!-- SKELETON — for future implementation -->
<!-- Scope of this agent when built:
  - Transform an approved process_system domain model into an implementation-ready design
  - Cover: workflow engine selection, state persistence model, compensation/saga design, human task integration, SLA enforcement
  - Tier 1 invariants: process state must be durable; compensation steps are mandatory for all non-idempotent actions
  - Tier 2 decisions: orchestration vs choreography, workflow engine vs custom state machine, step idempotency strategy, long-running process timeout handling
  - Output fields defined in engine/schemas/design-process_system.json
-->
