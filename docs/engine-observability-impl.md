# Implementation Plan — engine-observability

**Goal:** Add a structured observability layer to the MCP engine to detect agent
misbehavior and token waste: revision loops, redundant reads, premature approvals,
and error patterns across sessions.

**Archetype:** system_evolution — strangler fig, 5 sequential steps, gate-verified.
**Frozen surface:** tool names, return values, exceptions, artifact file format — all unchanged.
**Rollback:** git revert + server restart at any step. No feature flag.

Approved artifacts:
- Design: `artifacts/engine-observability/design/v1.json`
- Tech stack: `artifacts/engine-observability/tech_stack/v1.json`

---

## Migration map

```
[Step 1: engine/logs/event_schema.md]   ← human review gate
         │
         ▼
[Step 2: engine/logger.py]              ← writer + session tests MUST pass first
         │
         ▼
[Step 3: mcp_server.py wrapper]         ← exception-propagation + context-bleed tests MUST pass first
         │
         ▼
[Step 4: get_journey / get_session]     ← recursive-emission exclusion test MUST pass first
         │
         ▼
[Step 5: observe.py]                    ← output tests MUST pass first
```

---

## Step 1 — Event schema document

**File:** `engine/logs/event_schema.md` ✓ (committed)

**Gate:** human review — schema document exists, all fields named with types, versioned.
No code change. No server restart.

Event schema summary — see the file for full specification.

Entry event fields: `event_type`, `tool_name`, `session_id`, `slug`, `stage`, `timestamp`

Exit event fields (all entry fields, plus):

| Field | Value |
|---|---|
| `latency_ms` | `(time.monotonic() - start) * 1000` |
| `result_status` | `"ok"` or `"error"` |
| `error_class` | `f"{type(e).__name__}: {str(e)[:120]}"` on error; null on ok |
| `result_version` | version written by `write_artifact` on ok; null otherwise |
| `read_version` | version returned by `read_artifact` on ok; null otherwise |

`slug` and `stage` for `approve_artifact` are parsed from `artifact_path`:
`artifacts/<slug>/<stage>/v<n>.json` → `parts[1]`, `parts[2]`.

`get_journey` and `get_session` are excluded from instrumentation by tool name check at
wrapper entry — they never appear as events.

---

## Step 2 — `engine/logger.py`

**New dependency:** `structlog` — added in this commit.

**Public interface:**

```python
def configure(log_path: Path) -> None
    # Sets up structlog processor chain (contextvars → JSON → JSONL file).
    # Called once at server startup from mcp_server.py. Idempotent.

def get_session_id() -> str
    # Returns module-level UUID4 string. Initialized on first call.
    # Stable for process lifetime.

def bind_tool_context(tool_name: str, slug: str | None, stage: str | None) -> None
    # structlog.contextvars.bind_contextvars(tool_name=..., slug=..., stage=...)

def clear_tool_context() -> None
    # structlog.contextvars.clear_contextvars()
    # Called in finally block — runs even on exception.

def emit_entry() -> float
    # Emits entry event using bound context + session_id.
    # Returns time.monotonic() start time for latency calculation.
    # Non-throwing: OSError → sys.stderr, then continues.

def emit_exit(start_time: float, result_status: str,
              error_class: str | None = None,
              result_version: int | None = None,
              read_version: int | None = None) -> None
    # Emits exit event. latency_ms = (time.monotonic() - start_time) * 1000.
    # Non-throwing: OSError → sys.stderr, then continues.
```

**Environment variable:** `LOG_PATH` — JSONL file path. Default: `engine/logs/events.jsonl`.
Directory created at runtime if absent.

**Tests written before Step 2 commits** (`engine/tests/test_observability.py::TestLoggerWriter`):

| Test | What it verifies |
|---|---|
| `test_writer_non_throwing_on_os_error` | `emit_entry()`/`emit_exit()` do not raise when `open()` raises `OSError`; warning appears on stderr |
| `test_session_id_is_valid_uuid4` | `get_session_id()` returns a valid UUID4 string; same value on repeated calls |
| `test_processor_chain_output_fields` | After `configure()`, a test emit produces JSON with all required fields present |

---

## Step 3 — `mcp_server.py` instrumentation wrapper

**Change:** `call_tool()` wraps `_dispatch()`. No change to `_dispatch()` or `tool_handler.py`.

**Wrapper contract:**

```
call_tool(name, arguments):
  if name in {"get_journey", "get_session"}:
    return await _dispatch(name, arguments)       ← exclusion at entry, before any binding

  slug  = _extract_slug(name, arguments)          ← arguments["slug"] or parsed from artifact_path
  stage = _extract_stage(name, arguments)         ← arguments["stage"] or parsed from artifact_path

  bind_tool_context(name, slug, stage)
  start_time = emit_entry()
  try:
    result = await _dispatch(name, arguments)
    version_info = _extract_version_info(name, result)
    emit_exit(start_time, "ok", **version_info)
    return result
  except Exception as e:
    emit_exit(start_time, "error",
              error_class=f"{type(e).__name__}: {str(e)[:120]}")
    raise                                         ← bare re-raise, no wrapping
  finally:
    clear_tool_context()                          ← unconditional
```

`_extract_version_info` inspects the rendered result for `write_artifact` and
`read_artifact` to populate `result_version` / `read_version` respectively.

**Hard contracts (any deviation breaks frozen surface):**
- Exception from `_dispatch` propagates unchanged — no catching, no wrapping.
- `clear_tool_context()` runs in `finally` — executes even on exception.
- `emit_entry()` and `emit_exit()` are non-throwing — I/O failure must not fail the tool call.
- `get_journey` and `get_session` are excluded before any context binding.

**Manual gate verification (after Step 3 commits):** Run a full agent session. Inspect
`engine/logs/events.jsonl`. Verify: every tool call has a matched entry+exit pair;
`latency_ms` populated; `session_id` consistent across all events; no get_journey/get_session events.

**Tests written before Step 3 commits** (`TestWrapperBehavior`):

| Test | What it verifies |
|---|---|
| `test_wrapper_propagates_exception` | Mock `_dispatch` to raise `ValueError("test")`; assert same `ValueError` propagates from `call_tool` unchanged |
| `test_no_context_bleed` | Call two tools with different slugs; each JSONL exit event carries correct slug; no field from call N on events for call N+1 |

---

## Step 4 — `get_journey` and `get_session` query tools

**Registration:** New entries in `list_tools()` and new branches in `_dispatch()`.

**Tool schemas:**

```
get_journey:
  required: [slug]
  slug: string
  Returns: array of all events for that slug, ordered by timestamp ascending

get_session:
  required: [session_id]
  session_id: string (UUID4)
  Returns: array of all events for that session_id, ordered by timestamp ascending
```

These tools read the full JSONL file and filter in memory. At current scale (single
developer, tens of sessions) this is acceptable. File growth is a future evolution trigger.

**Tests written before Step 4 commits** (`TestQueryTools`):

| Test | What it verifies |
|---|---|
| `test_no_recursive_emission` | Call `get_journey` after populating JSONL with two tool calls; no entry/exit events with `tool_name == "get_journey"` appear |
| `test_get_journey_returns_ordered_events` | Known JSONL fixture with 3 events for slug "x"; assert all 3 returned, timestamp-ascending |
| `test_get_session_scopes_correctly` | Fixture with events for two session_ids; `get_session(id_A)` returns only id_A events |

---

## Step 5 — `observe.py`

**File:** `observe.py` (project root — standalone, no MCP surface)

**Invocation:**
```
python observe.py [--log-path PATH]
```
`--log-path` defaults to `LOG_PATH` env var, then `engine/logs/events.jsonl`.

**Output (stdout):**

```
Per-session summary
  session_id | total calls | write calls | read calls | errors | max revision

Revision loops  (write_artifact result_version ≥ 2)
  slug | stage | session_id | version reached

Redundant reads  (same slug+stage+read_version twice in one session)
  slug | stage | version | session_id | count

Error distribution
  error_class | count | % of errors

Misbehavior signals
  Premature approvals (approve_artifact errors): N
  Revision loops (write result_version ≥ 3): N
```

**Edge cases:**
- Empty or absent JSONL → prints `"No events recorded yet."`, exits 0, no traceback.
- Standard library only — no pandas, no numpy.

**Out of scope:** "stale read" detection (read_version < latest available) requires
querying the artifact store, not just the log — deferred to future evolution.

**Tests written before Step 5 commits** (`TestObserveCLI`):

| Test | What it verifies |
|---|---|
| `test_golden_path_output` | Fixture with 3 completed sessions; all output sections present without error |
| `test_empty_jsonl` | Empty JSONL → "No events recorded yet.", exit 0 |
| `test_absent_jsonl` | Non-existent path → same as empty |
| `test_revision_count_correctness` | 2 write_artifact calls (v1, v2) same slug+stage + 1 other; mean revision = 1.5 |
| `test_failure_rate_correctness` | 3 exit events, 1 error → failure rate 33.3% |

---

## Test impact analysis

**New test file:** `engine/tests/test_observability.py`
**New pytest mark:** `observability` — add to `pytest.ini` / `pyproject.toml`

```
TestLoggerWriter     — Step 2 gate (3 tests)
TestWrapperBehavior  — Step 3 gate (2 tests)
TestQueryTools       — Step 4 gate (3 tests)
TestObserveCLI       — Step 5 gate (5 tests)
```

**No new invariant tests** — no new orchestrator-owned artifact fields.
**No new lifecycle tests** — no new artifact types.
**No new contract tests** — `get_journey` / `get_session` are query tools, not DAG nodes.
**No new renderer tests** — no new artifact types.

---

## Confirmed technology decisions

| Decision | Value |
|---|---|
| Logging library | structlog (MDC via contextvars, JSONL processor chain) |
| Test framework | pytest (monkeypatch, capsys) |
| Session identity | UUID4, module-level, stable per process |
| Event log format | JSONL (one JSON object per line) |
| observe.py dependencies | Python standard library only |
| Query tool exclusion mechanism | Tool name check at wrapper entry |
| Context clear | `finally` block — unconditional |
| Rollback mechanism | git revert + server restart — no toggle flag |

---

## Misbehavior signals the schema supports

| Signal | How to detect |
|---|---|
| Revision loop | `write_artifact` exits with `result_version >= 2`, same `slug+stage+session_id` |
| Redundant read | Two `read_artifact` exits with same `slug+stage+read_version` in one session |
| Premature approval | `approve_artifact` exit with `result_status="error"` |
| Hallucinated slug | `error_class` starting with `"ValueError: no approved"` |
| Upstream-not-ready write | `error_class` matching `"ValueError: no approved <stage>"` |
| Agent looping | High total exit-event count per session |
