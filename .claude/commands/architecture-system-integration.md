> **NOT IMPLEMENTED** — The architecture agent for the `system_integration` archetype has not been written yet.
>
> Inform the user: "The `architecture-system-integration` agent is not yet available. Only `architecture-domain-system` and `architecture-system-evolution` are currently implemented. If your project uses the `system_integration` archetype, this agent needs to be built before proceeding to design." Then stop.

---

<!-- SKELETON — for future implementation -->
<!-- Scope of this agent when built:
  - Transform an approved system_integration domain model into an implementation-ready design
  - Cover: integration topology, protocol selection per boundary, transformation/mapping strategy, error handling across systems, idempotency model
  - Tier 1 invariants: external system contracts are fixed inputs; integration layer owns translation
  - Tier 2 decisions: sync vs async per integration, retry and timeout policy, circuit breaker placement, data contract ownership
  - Output fields defined in engine/schemas/design-system_integration.json
-->
