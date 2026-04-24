> **NOT IMPLEMENTED** — The architecture agent for the `data_pipeline` archetype has not been written yet.
>
> Inform the user: "The `architecture-data-pipeline` agent is not yet available. Only `architecture-domain-system` and `architecture-system-evolution` are currently implemented. If your project uses the `data_pipeline` archetype, this agent needs to be built before proceeding to design." Then stop.

---

<!-- SKELETON — for future implementation -->
<!-- Scope of this agent when built:
  - Transform an approved data_pipeline domain model into an implementation-ready design
  - Cover: pipeline topology, stage-level storage, failure handling, scaling/backpressure, observability, testing strategy
  - Tier 1 invariants: ordering guarantees per stage, exactly-once vs at-least-once delivery derived from pipeline model
  - Tier 2 decisions: batch vs stream execution, partitioning strategy, checkpointing model, failure isolation boundaries
  - Output fields defined in engine/schemas/design-data_pipeline.json
-->
