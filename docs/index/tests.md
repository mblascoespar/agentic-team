# Test map

| File | Intent |
|------|--------|
| `test_invariants.py` | Orchestrator field ownership and input validation; verifies engine rejects malformed or unauthorized writes |
| `test_lifecycle.py` | Correct versioning through the v1 → v2 → approve chain; verifies version, parent_version, created_at, updated_at, and status at each step |
| `test_contracts.py` | DAG edge handoffs; verifies that node N's output is consumable by node N+1; a failure here means a DAG boundary is broken |
| `test_renderer.py` | Renderer output correctness; verifies rendered artifact matches expected shape for agent consumption |

## Running tests

```bash
cd engine && pytest tests/
```
