# Observability Event Schema — v1

Structured event log for every MCP tool call. Written to `engine/logs/events.jsonl`
(one JSON object per line, UTF-8, newline-delimited). Path overridden via `LOG_PATH` env var.

## Purpose

Detect agent misbehavior and token waste: revision loops, redundant reads, premature
approvals, and error patterns across sessions.

---

## Entry event

Emitted immediately before dispatching the tool handler.

```json
{
  "event_type":  "entry",
  "tool_name":   "<string>",
  "session_id":  "<UUID4>",
  "slug":        "<string | null>",
  "stage":       "<string | null>",
  "timestamp":   "<ISO8601 UTC>"
}
```

| Field | Source | Null when |
|---|---|---|
| `tool_name` | `name` argument to `call_tool` | never |
| `session_id` | module-level UUID4, stable for process lifetime | never |
| `slug` | `arguments["slug"]` if present; parsed from `artifact_path` for `approve_artifact` | tool takes neither |
| `stage` | `arguments["stage"]` if present; parsed from `artifact_path` for `approve_artifact` | tool takes neither |

### artifact_path parsing (approve_artifact)

Path format: `artifacts/<slug>/<stage>/v<n>.json`

```
parts = artifact_path.split("/")
slug  = parts[1]
stage = parts[2]
```

---

## Exit event

Emitted after the handler returns or raises. Always paired with an entry event.
Matched on `(tool_name, session_id)` — not on position.

```json
{
  "event_type":     "exit",
  "tool_name":      "<string>",
  "session_id":     "<UUID4>",
  "slug":           "<string | null>",
  "stage":          "<string | null>",
  "timestamp":      "<ISO8601 UTC>",
  "latency_ms":     "<float>",
  "result_status":  "ok | error",
  "error_class":    "<string | null>",
  "result_version": "<int | null>",
  "read_version":   "<int | null>"
}
```

| Field | Source | Null when |
|---|---|---|
| `latency_ms` | `(time.monotonic() - start) * 1000` | never |
| `result_status` | `"ok"` on normal return; `"error"` on any exception | never |
| `error_class` | `f"{type(e).__name__}: {str(e)[:120]}"` | result_status is "ok" |
| `result_version` | version field of artifact returned by `write_artifact` | tool is not `write_artifact`, or call errored |
| `read_version` | version field of artifact returned by `read_artifact` | tool is not `read_artifact`, or call errored |

---

## Excluded tools

`get_journey` and `get_session` are excluded from instrumentation. They must never
appear as events in the JSONL file. Exclusion is enforced at wrapper entry by tool name
check — before any context binding or emit.

---

## Writer contract

The JSONL writer is **non-throwing**. Any `OSError` (disk full, permission denied) is
written to `sys.stderr` and suppressed. The tool call result is never affected by a
logging failure.

---

## Session identity

`session_id` is a UUID4 string initialized once on first call to `get_session_id()` and
stable for the lifetime of the process. A server restart starts a new session.

---

## Misbehavior signals derivable from this schema

| Signal | Query |
|---|---|
| Revision loop | Exit events for `write_artifact` with `result_version >= 2`, same `slug+stage+session_id` |
| Redundant read | Two exit events for `read_artifact` with same `slug+stage+read_version` in one session |
| Premature approval | Exit event for `approve_artifact` with `result_status="error"` |
| Hallucinated slug | `error_class` starting with `"ValueError: no approved"` |
| Agent looping | High total exit-event count per session (observe.py per-session summary) |
