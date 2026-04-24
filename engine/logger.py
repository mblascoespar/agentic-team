import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog.contextvars

_SESSION_ID: str | None = None
_LOG_PATH: Path | None = None


def configure(log_path: Path) -> None:
    global _LOG_PATH
    if _LOG_PATH is not None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _LOG_PATH = log_path


def get_session_id() -> str:
    global _SESSION_ID
    if _SESSION_ID is None:
        _SESSION_ID = str(uuid.uuid4())
    return _SESSION_ID


def get_log_path() -> Path | None:
    return _LOG_PATH


def bind_tool_context(tool_name: str, slug: str | None, stage: str | None) -> None:
    structlog.contextvars.bind_contextvars(tool_name=tool_name, slug=slug, stage=stage)


def clear_tool_context() -> None:
    structlog.contextvars.clear_contextvars()


def _open_log(path: Path):
    return path.open("a", encoding="utf-8")


def _write_event(event: dict) -> None:
    if _LOG_PATH is None:
        return
    try:
        with _open_log(_LOG_PATH) as f:
            f.write(json.dumps(event) + "\n")
    except OSError as e:
        print(f"WARNING: observability write failed: {e}", file=sys.stderr)


def emit_entry() -> float:
    start_time = time.monotonic()
    ctx = structlog.contextvars.get_contextvars()
    event = {
        "event_type": "entry",
        "tool_name": ctx.get("tool_name"),
        "session_id": get_session_id(),
        "slug": ctx.get("slug"),
        "stage": ctx.get("stage"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _write_event(event)
    return start_time


def emit_exit(
    start_time: float,
    result_status: str,
    error_class: str | None = None,
    result_version: int | None = None,
    read_version: int | None = None,
) -> None:
    ctx = structlog.contextvars.get_contextvars()
    event = {
        "event_type": "exit",
        "tool_name": ctx.get("tool_name"),
        "session_id": get_session_id(),
        "slug": ctx.get("slug"),
        "stage": ctx.get("stage"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": (time.monotonic() - start_time) * 1000,
        "result_status": result_status,
        "error_class": error_class,
        "result_version": result_version,
        "read_version": read_version,
    }
    _write_event(event)
