# DAG flows

## Stage sequence

```
brief
  → prd
    → model_domain / model_data_flow / model_evolution / model_system / model_workflow
      → design
        → tech_stack
          → execution
            → evaluation
```

## Rules

- **Writes create a draft.** Every `write_artifact` call produces a new version in `status: draft`.
- **Approval required to advance.** A stage's output must be approved before the next stage can begin.
- **References are engine-owned.** Cross-artifact references (e.g. `prd_ref`) are resolved and validated by the engine, not by agents.
- **Artifacts are versioned.** Each write increments the version; the full chain is preserved at `artifacts/<slug>/<stage>/v<n>.json`.

## Agent session start

| Situation | Tool |
|-----------|------|
| Slug known | `get_work_context(slug, stage)` → returns `{upstream: {artifact, schema}, current_draft: {artifact, schema} \| null}` |
| Slug unknown | `get_available_artifacts(stage)` → user picks slug → `get_work_context(slug, stage)` |

`get_work_context` raises `ValueError` if the stage is `"brief"`, the topology cannot be resolved (no approved PRD), the stage is not in the slug's topology, or the upstream artifact is not yet approved.
