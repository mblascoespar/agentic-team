# Schema map

## Naming conventions

| Suffix | Role | Used by |
|--------|------|---------|
| `<stage>.input.json` | JSON Schema; validates MCP tool call arguments at write time | `tool_handler.py` — loaded at module init, applied on every `write_artifact` call |
| `<stage>.mcp.json` | JSON Schema; MCP-layer input shape (may differ from internal input) | `mcp_server.py` |
| `<stage>.base.json` | Field registry for the artifact body (not a JSON Schema); defines mandatory/optional fields per stage | `tool_handler.py` — copied to `artifacts/<slug>/<stage>/schema.json` on first write |
| `design-<archetype>.json` | Per-archetype design body field registry; replaces `design.base.json` at runtime | `tool_handler.py` — selected by `primary_archetype` on the approved PRD |
| `model-<type>.json` | Per-type model body field registry | `tool_handler.py` — selected by `model_type` argument |

## File → stage mapping

| Schema file | Stage | Validated by |
|-------------|-------|-------------|
| `brief.base.json` | `brief` | artifact body registry |
| `prd.base.json` | `prd` | artifact body registry |
| `model-domain.json` | `model_domain` | artifact body registry |
| `model-data-flow.json` | `model_data_flow` | artifact body registry |
| `model-system.json` | `model_system` | artifact body registry |
| `model-workflow.json` | `model_workflow` | artifact body registry |
| `model-evolution.json` | `model_evolution` | artifact body registry |
| `design-domain_system.json` | `design` (archetype: domain_system) | artifact body registry |
| `design-data_pipeline.json` | `design` (archetype: data_pipeline) | artifact body registry |
| `design-system_integration.json` | `design` (archetype: system_integration) | artifact body registry |
| `design-process_system.json` | `design` (archetype: process_system) | artifact body registry |
| `design-system_evolution.json` | `design` (archetype: system_evolution) | artifact body registry |
| `tech_stack.base.json` | `tech_stack` | artifact body registry |

## Key runtime behaviors

- `*.input.json` schemas are loaded once at module init in `tool_handler.py` (lines 17–21).
- Base schemas are registered in `_BASE_SCHEMAS_BY_STAGE` (lines 66–83) and copied to `artifacts/<slug>/<stage>/schema.json` on first write.
- Design body schema is selected dynamically from `primary_archetype` on the approved PRD; key format is `"design-{primary_archetype}"`.
- Model body schema is selected from the `stage` argument to `write_artifact`; `_MODEL_TYPE_TO_STAGE` maps stage name → stage directory.
