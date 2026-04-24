"""
MCP server exposing pipeline tools to Claude Code.
Run via: python engine/mcp_server.py
Registered in .mcp.json at project root.
"""
import json
import os
import re
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tool_handler import (
    handle_write_artifact, handle_approve_artifact,
    handle_add_schema_field, handle_update_schema_field, handle_delete_schema_field,
    get_available_artifacts, read_artifact, handle_get_work_context,
)
from renderer import render_artifact
import logger

app = Server("agentic-team")

_EXCLUDED_FROM_INSTRUMENTATION = {"get_journey", "get_session"}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="read_artifact",
            description=(
                "Read the full content of a specific artifact version. "
                "Use this to load an existing artifact before entering refinement mode. "
                "If version is omitted, returns the latest version."
            ),
            inputSchema={
                "type": "object",
                "required": ["slug", "stage"],
                "properties": {
                    "slug": {"type": "string", "description": "Project slug, e.g. 'deploy-rollback'."},
                    "stage": {"type": "string", "description": "DAG stage, e.g. 'brief', 'prd', 'model_domain', 'design', 'tech_stack'."},
                    "version": {"type": "integer", "description": "Version number to read. Omit for latest."},
                },
            },
        ),
        Tool(
            name="get_available_artifacts",
            description=(
                "Return in-progress, approved, and ready-to-start artifacts for a DAG stage. "
                "Call at the start of a no-argument session to populate the opening menu."
            ),
            inputSchema={
                "type": "object",
                "required": ["stage"],
                "properties": {
                    "stage": {"type": "string", "description": "DAG stage to query: brief, prd, model_domain, model_data_flow, model_system, model_workflow, model_evolution, design, tech_stack."},
                },
            },
        ),
        Tool(
            name="get_work_context",
            description=(
                "Return the approved upstream artifact and current draft for a DAG stage. "
                "Call at the start of any agent session to get: "
                "upstream — the approved artifact from the previous stage; "
                "current_draft — the in-progress draft at this stage (null if none exists yet)."
            ),
            inputSchema={
                "type": "object",
                "required": ["slug", "stage"],
                "properties": {
                    "slug": {"type": "string", "description": "Project slug (e.g. 'deploy-rollback')."},
                    "stage": {"type": "string", "description": "DAG stage to get context for (e.g. 'prd', 'model_domain', 'design', 'tech_stack')."},
                },
            },
        ),
        Tool(
            name="write_artifact",
            description=(
                "Write or update any artifact stage. "
                "The engine verifies the upstream is approved, enforces locked fields, "
                "and initialises the instance schema on first write. "
                "body is stored verbatim as the artifact content."
            ),
            inputSchema={
                "type": "object",
                "required": ["slug", "stage", "body"],
                "properties": {
                    "slug": {"type": "string", "description": "Project slug (e.g. 'deploy-rollback')."},
                    "stage": {
                        "type": "string",
                        "description": "DAG stage to write: brief, prd, model_domain, model_data_flow, model_system, model_workflow, model_evolution, design, tech_stack.",
                    },
                    "body": {
                        "type": "object",
                        "description": "Artifact content. All fields are passed through; mandatory fields are validated at approval time.",
                    },
                    "decision_log_entry": {
                        "type": "object",
                        "description": "Optional log entry recorded with this write.",
                        "properties": {
                            "trigger": {"type": "string"},
                            "summary": {"type": "string"},
                            "changed_fields": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        ),
        Tool(
            name="approve_artifact",
            description=(
                "Approve any artifact after validating all mandatory schema fields are present. "
                "Advances the DAG to the next stage."
            ),
            inputSchema={
                "type": "object",
                "required": ["artifact_path"],
                "properties": {
                    "artifact_path": {
                        "type": "string",
                        "description": "Relative path to the artifact JSON file. Example: artifacts/deploy-rollback/prd/v2.json",
                    },
                },
            },
        ),
        Tool(
            name="add_schema_field",
            description=(
                "Add a new field to the instance schema for a slug/stage. "
                "Use when you discover a concept the base schema has no field for — "
                "call this before the next write so the field is included in the artifact. "
                "kind 'mandatory' means approval will fail if the field is absent; "
                "'optional' means it may be omitted. "
                "Rejects if the field already exists."
            ),
            inputSchema={
                "type": "object",
                "required": ["slug", "stage", "field_name", "kind", "description"],
                "properties": {
                    "slug": {"type": "string"},
                    "stage": {"type": "string"},
                    "field_name": {"type": "string"},
                    "kind": {"type": "string", "enum": ["mandatory", "optional"]},
                    "description": {"type": "string", "description": "What this field captures and why it matters."},
                },
            },
        ),
        Tool(
            name="update_schema_field",
            description=(
                "Change an existing field's kind, description, or name. "
                "Provide at least one of: kind, description, new_field_name. "
                "If new_field_name is provided, the field is renamed in the schema "
                "and the old key is cleared from the current draft artifact."
            ),
            inputSchema={
                "type": "object",
                "required": ["slug", "stage", "field_name"],
                "properties": {
                    "slug": {"type": "string"},
                    "stage": {"type": "string"},
                    "field_name": {"type": "string", "description": "Current name of the field to update."},
                    "kind": {"type": "string", "enum": ["mandatory", "optional"]},
                    "description": {"type": "string"},
                    "new_field_name": {"type": "string", "description": "Rename the field. Clears old key from the current draft."},
                },
            },
        ),
        Tool(
            name="delete_schema_field",
            description=(
                "Remove a field from the instance schema. "
                "The field is deleted from the schema and its value is cleared from the current draft. "
                "Requires a non-empty justification — recorded in the schema decision log."
            ),
            inputSchema={
                "type": "object",
                "required": ["slug", "stage", "field_name", "justification"],
                "properties": {
                    "slug": {"type": "string"},
                    "stage": {"type": "string"},
                    "field_name": {"type": "string"},
                    "justification": {"type": "string", "description": "Why this field is being removed."},
                },
            },
        ),
        Tool(
            name="get_journey",
            description="Return all events for a slug, ordered by timestamp ascending.",
            inputSchema={
                "type": "object",
                "required": ["slug"],
                "properties": {
                    "slug": {"type": "string", "description": "Project slug to query."},
                },
            },
        ),
        Tool(
            name="get_session",
            description="Return all events for a session_id, ordered by timestamp ascending.",
            inputSchema={
                "type": "object",
                "required": ["session_id"],
                "properties": {
                    "session_id": {"type": "string", "description": "UUID4 session identifier."},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name in _EXCLUDED_FROM_INSTRUMENTATION:
        return await _dispatch(name, arguments)

    slug = _extract_slug(name, arguments)
    stage = _extract_stage(name, arguments)

    logger.bind_tool_context(name, slug, stage)
    start_time = logger.emit_entry()
    try:
        result = await _dispatch(name, arguments)
        version_info = _extract_version_info(name, result)
        logger.emit_exit(start_time, "ok", **version_info)
        return result
    except Exception as e:
        logger.emit_exit(
            start_time, "error",
            error_class=f"{type(e).__name__}: {str(e)[:120]}",
        )
        raise
    finally:
        logger.clear_tool_context()


def _extract_slug(name: str, arguments: dict) -> str | None:
    if name == "approve_artifact":
        parts = arguments.get("artifact_path", "").split("/")
        return parts[1] if len(parts) > 2 else None
    return arguments.get("slug")


def _extract_stage(name: str, arguments: dict) -> str | None:
    if name == "approve_artifact":
        parts = arguments.get("artifact_path", "").split("/")
        return parts[2] if len(parts) > 3 else None
    return arguments.get("stage")


def _extract_version_info(name: str, result: list) -> dict:
    if not result:
        return {}
    text = result[0].text
    if name == "write_artifact":
        m = re.search(r"/v(\d+)\.json", text)
        if m:
            return {"result_version": int(m.group(1))}
    elif name == "read_artifact":
        try:
            data = json.loads(text)
            return {"read_version": data["artifact"]["version"]}
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


def _query_events(slug: str | None = None, session_id: str | None = None) -> list:
    log_path = logger.get_log_path()
    if log_path is None or not log_path.exists():
        return []
    events = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if slug is not None and event.get("slug") != slug:
                continue
            if session_id is not None and event.get("session_id") != session_id:
                continue
            events.append(event)
    events.sort(key=lambda e: e.get("timestamp", ""))
    return events


async def _dispatch(name: str, arguments: dict) -> list[TextContent]:
    if name == "read_artifact":
        result = read_artifact(arguments["slug"], arguments["stage"], arguments.get("version"))
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "get_available_artifacts":
        result = get_available_artifacts(arguments["stage"])
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "get_work_context":
        result = handle_get_work_context(arguments["slug"], arguments["stage"])
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "write_artifact":
        stage = arguments["stage"]
        artifact = handle_write_artifact(
            slug=arguments["slug"],
            stage=stage,
            body=dict(arguments["body"]),
            decision_log_entry=arguments.get("decision_log_entry"),
        )
        return [TextContent(type="text", text=render_artifact(artifact, stage))]

    if name == "approve_artifact":
        artifact = handle_approve_artifact(arguments["artifact_path"])
        return [TextContent(type="text", text=f"Approved: {arguments['artifact_path']}\nStatus: {artifact['status']}")]

    if name == "add_schema_field":
        schema = handle_add_schema_field(
            arguments["slug"], arguments["stage"], arguments["field_name"],
            arguments["kind"], arguments["description"],
        )
        return [TextContent(type="text", text=json.dumps(schema, indent=2))]

    if name == "update_schema_field":
        schema = handle_update_schema_field(
            arguments["slug"], arguments["stage"], arguments["field_name"],
            kind=arguments.get("kind"),
            description=arguments.get("description"),
            new_field_name=arguments.get("new_field_name"),
        )
        return [TextContent(type="text", text=json.dumps(schema, indent=2))]

    if name == "delete_schema_field":
        schema = handle_delete_schema_field(
            arguments["slug"], arguments["stage"], arguments["field_name"],
            arguments["justification"],
        )
        return [TextContent(type="text", text=json.dumps(schema, indent=2))]

    if name == "get_journey":
        events = _query_events(slug=arguments["slug"])
        return [TextContent(type="text", text=json.dumps(events, indent=2))]

    if name == "get_session":
        events = _query_events(session_id=arguments["session_id"])
        return [TextContent(type="text", text=json.dumps(events, indent=2))]

    return [TextContent(type="text", text=f"ERROR: unknown tool '{name}'")]


async def main():
    log_path = Path(os.getenv("LOG_PATH", "engine/logs/events.jsonl"))
    logger.configure(log_path)
    async with stdio_server() as (read_stream, write_write):
        await app.run(read_stream, write_write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
