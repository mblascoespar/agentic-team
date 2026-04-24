"""
Observability tests.

TestLoggerWriter     — Step 2 gate (3 tests)
TestWrapperBehavior  — Step 3 gate (2 tests)
TestQueryTools       — Step 4 gate (3 tests)
TestObserveCLI       — Step 5 gate (5 tests)

Run: pytest -m observability
"""
import asyncio
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import logger as logger_mod

pytestmark = pytest.mark.observability

PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(autouse=True)
def reset_logger():
    orig_session_id = logger_mod._SESSION_ID
    orig_log_path = logger_mod._LOG_PATH
    logger_mod._SESSION_ID = None
    logger_mod._LOG_PATH = None
    logger_mod.clear_tool_context()
    yield
    logger_mod._SESSION_ID = orig_session_id
    logger_mod._LOG_PATH = orig_log_path
    logger_mod.clear_tool_context()


# ===========================================================================
# Step 2 gate — TestLoggerWriter
# ===========================================================================

class TestLoggerWriter:
    def test_session_id_is_valid_uuid4(self):
        sid = logger_mod.get_session_id()
        assert logger_mod.get_session_id() == sid
        assert uuid.UUID(sid).version == 4

    def test_writer_non_throwing_on_os_error(self, tmp_path, capsys):
        logger_mod.configure(tmp_path / "events.jsonl")
        logger_mod.bind_tool_context("read_artifact", "my-slug", "prd")
        with patch.object(logger_mod, "_open_log", side_effect=OSError("disk full")):
            start = logger_mod.emit_entry()
            logger_mod.emit_exit(start, "ok")
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_processor_chain_output_fields(self, tmp_path):
        log_path = tmp_path / "events.jsonl"
        logger_mod.configure(log_path)
        logger_mod.bind_tool_context("write_artifact", "proj", "prd")
        start = logger_mod.emit_entry()
        logger_mod.emit_exit(start, "ok", result_version=1)
        lines = [ln for ln in log_path.read_text().splitlines() if ln]
        assert len(lines) == 2
        entry = json.loads(lines[0])
        assert entry["event_type"] == "entry"
        assert entry["tool_name"] == "write_artifact"
        assert entry["slug"] == "proj"
        assert entry["stage"] == "prd"
        assert "session_id" in entry
        assert "timestamp" in entry
        exit_ev = json.loads(lines[1])
        assert exit_ev["event_type"] == "exit"
        assert "latency_ms" in exit_ev
        assert exit_ev["result_status"] == "ok"
        assert exit_ev["result_version"] == 1
        assert exit_ev["error_class"] is None
        assert exit_ev["read_version"] is None


# ===========================================================================
# Step 3 gate — TestWrapperBehavior
# ===========================================================================

class TestWrapperBehavior:
    def test_wrapper_propagates_exception(self, tmp_path):
        import mcp_server
        logger_mod.configure(tmp_path / "events.jsonl")

        async def run():
            with patch.object(mcp_server, "_dispatch", new=AsyncMock(side_effect=ValueError("test"))):
                with pytest.raises(ValueError, match="test"):
                    await mcp_server.call_tool("read_artifact", {"slug": "x", "stage": "prd"})

        asyncio.run(run())

    def test_no_context_bleed(self, tmp_path):
        import mcp_server
        from mcp.types import TextContent

        log_path = tmp_path / "events.jsonl"
        logger_mod.configure(log_path)

        r1 = [TextContent(type="text", text='{"artifact": {"version": 1}, "schema": {}}')]
        r2 = [TextContent(type="text", text='{"artifact": {"version": 1}, "schema": {}}')]

        async def run():
            with patch.object(mcp_server, "_dispatch", new=AsyncMock(side_effect=[r1, r2])):
                await mcp_server.call_tool("read_artifact", {"slug": "slug-a", "stage": "prd"})
                await mcp_server.call_tool("read_artifact", {"slug": "slug-b", "stage": "brief"})

        asyncio.run(run())

        events = [json.loads(ln) for ln in log_path.read_text().splitlines() if ln]
        exits = [e for e in events if e["event_type"] == "exit"]
        assert len(exits) == 2
        assert exits[0]["slug"] == "slug-a"
        assert exits[1]["slug"] == "slug-b"


# ===========================================================================
# Step 4 gate — TestQueryTools
# ===========================================================================

class TestQueryTools:
    def test_no_recursive_emission(self, tmp_path):
        import mcp_server

        log_path = tmp_path / "events.jsonl"
        logger_mod.configure(log_path)

        logger_mod.bind_tool_context("read_artifact", "my-slug", "prd")
        s = logger_mod.emit_entry()
        logger_mod.emit_exit(s, "ok", read_version=1)
        logger_mod.clear_tool_context()

        async def run():
            await mcp_server.call_tool("get_journey", {"slug": "my-slug"})

        asyncio.run(run())

        events = [json.loads(ln) for ln in log_path.read_text().splitlines() if ln]
        assert not any(e.get("tool_name") == "get_journey" for e in events)

    def test_get_journey_returns_ordered_events(self, tmp_path):
        import mcp_server

        log_path = tmp_path / "events.jsonl"
        logger_mod.configure(log_path)

        fixture = [
            {"event_type": "entry", "tool_name": "read_artifact", "session_id": "s1", "slug": "x", "stage": "prd", "timestamp": "2026-04-24T10:00:02Z"},
            {"event_type": "exit",  "tool_name": "read_artifact", "session_id": "s1", "slug": "x", "stage": "prd", "timestamp": "2026-04-24T10:00:01Z"},
            {"event_type": "entry", "tool_name": "write_artifact", "session_id": "s1", "slug": "x", "stage": "prd", "timestamp": "2026-04-24T10:00:03Z"},
        ]
        with log_path.open("w") as f:
            for ev in fixture:
                f.write(json.dumps(ev) + "\n")

        async def run():
            return await mcp_server.call_tool("get_journey", {"slug": "x"})

        result = asyncio.run(run())
        events = json.loads(result[0].text)
        assert len(events) == 3
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_get_session_scopes_correctly(self, tmp_path):
        import mcp_server

        log_path = tmp_path / "events.jsonl"
        logger_mod.configure(log_path)

        id_a = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
        id_b = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
        fixture = [
            {"event_type": "entry", "tool_name": "read_artifact", "session_id": id_a, "slug": "x", "stage": "prd",   "timestamp": "2026-04-24T10:00:01Z"},
            {"event_type": "entry", "tool_name": "read_artifact", "session_id": id_b, "slug": "y", "stage": "brief", "timestamp": "2026-04-24T10:00:02Z"},
            {"event_type": "exit",  "tool_name": "read_artifact", "session_id": id_a, "slug": "x", "stage": "prd",   "timestamp": "2026-04-24T10:00:03Z"},
        ]
        with log_path.open("w") as f:
            for ev in fixture:
                f.write(json.dumps(ev) + "\n")

        async def run():
            return await mcp_server.call_tool("get_session", {"session_id": id_a})

        result = asyncio.run(run())
        events = json.loads(result[0].text)
        assert len(events) == 2
        assert all(e["session_id"] == id_a for e in events)


# ===========================================================================
# Step 5 gate — TestObserveCLI
# ===========================================================================

def _load_observe():
    spec = importlib.util.spec_from_file_location("observe", PROJECT_ROOT / "observe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_exit_event(tool_name, slug, stage, session_id, timestamp, **kwargs):
    ev = {
        "event_type": "exit",
        "tool_name": tool_name,
        "session_id": session_id,
        "slug": slug,
        "stage": stage,
        "timestamp": timestamp,
        "latency_ms": 10.0,
        "result_status": "ok",
        "error_class": None,
        "result_version": None,
        "read_version": None,
    }
    ev.update(kwargs)
    return ev


class TestObserveCLI:
    def _write_jsonl(self, path: Path, events: list) -> None:
        with path.open("w") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")

    def test_empty_jsonl(self, tmp_path, capsys):
        log_path = tmp_path / "events.jsonl"
        log_path.write_text("")
        observe = _load_observe()
        observe.main(["--log-path", str(log_path)])
        out = capsys.readouterr().out
        assert "No events recorded yet." in out

    def test_absent_jsonl(self, tmp_path, capsys):
        log_path = tmp_path / "nonexistent.jsonl"
        observe = _load_observe()
        observe.main(["--log-path", str(log_path)])
        out = capsys.readouterr().out
        assert "No events recorded yet." in out

    def test_golden_path_output(self, tmp_path, capsys):
        log_path = tmp_path / "events.jsonl"
        s1, s2, s3 = "sid-1111", "sid-2222", "sid-3333"
        events = [
            _make_exit_event("write_artifact", "proj-a", "prd",    s1, "2026-04-24T10:00:01Z", result_version=1),
            _make_exit_event("read_artifact",  "proj-a", "prd",    s1, "2026-04-24T10:00:02Z", read_version=1),
            _make_exit_event("write_artifact", "proj-b", "design", s2, "2026-04-24T10:00:03Z", result_version=1),
            _make_exit_event("approve_artifact","proj-b","design",  s2, "2026-04-24T10:00:04Z", result_status="error", error_class="ValueError: no approved design"),
            _make_exit_event("read_artifact",  "proj-c", "brief",   s3, "2026-04-24T10:00:05Z", read_version=1),
        ]
        self._write_jsonl(log_path, events)
        observe = _load_observe()
        observe.main(["--log-path", str(log_path)])
        out = capsys.readouterr().out
        assert "Per-session summary" in out
        assert "Revision loops" in out
        assert "Redundant reads" in out
        assert "Error distribution" in out
        assert "Misbehavior signals" in out

    def test_revision_count_correctness(self, tmp_path, capsys):
        log_path = tmp_path / "events.jsonl"
        s1 = "sid-aaaa"
        events = [
            _make_exit_event("write_artifact", "slug-a", "prd", s1, "2026-04-24T10:00:01Z", result_version=1),
            _make_exit_event("write_artifact", "slug-a", "prd", s1, "2026-04-24T10:00:02Z", result_version=2),
            _make_exit_event("write_artifact", "slug-b", "prd", s1, "2026-04-24T10:00:03Z", result_version=1),
        ]
        self._write_jsonl(log_path, events)
        observe = _load_observe()
        observe.main(["--log-path", str(log_path)])
        out = capsys.readouterr().out
        assert "slug-a" in out
        assert "slug-b" not in out.split("Revision loops")[1].split("Redundant reads")[0]

    def test_failure_rate_correctness(self, tmp_path, capsys):
        log_path = tmp_path / "events.jsonl"
        s1 = "sid-bbbb"
        ec = "ValueError: bad input"
        events = [
            _make_exit_event("write_artifact", "x", "prd", s1, "2026-04-24T10:00:01Z", result_version=1),
            _make_exit_event("read_artifact",  "x", "prd", s1, "2026-04-24T10:00:02Z", read_version=1),
            _make_exit_event("read_artifact",  "x", "prd", s1, "2026-04-24T10:00:03Z", result_status="error", error_class=ec),
        ]
        self._write_jsonl(log_path, events)
        observe = _load_observe()
        observe.main(["--log-path", str(log_path)])
        out = capsys.readouterr().out
        assert ec in out
        assert "33.3" in out
