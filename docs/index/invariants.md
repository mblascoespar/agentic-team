# Artifact invariants

These are engine-enforced. Any code change that violates them is a breaking change.

| Invariant | Rule |
|-----------|------|
| Slug immutable | `slug` is set at v1 and never changes |
| Version monotonic | Each write increments `version`; no gaps, no resets |
| Parent chain correct | `parent_version` on v(n) equals `version` of v(n-1) |
| `created_at` fixed | Set at v1; never overwritten on subsequent writes |
| `updated_at` changes | Updated on every write |
| Status transitions | `draft` on write; `approved` only via approval call; no reversal |
| References engine-owned | Cross-artifact `*_ref` fields are set and validated by the engine |
| Writes confined | All artifact writes go to `artifacts/`; no writes outside that directory |
