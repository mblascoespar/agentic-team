"""
MCP server exposing pipeline tools to Claude Code.
Run via: python engine/mcp_server.py
Registered in .mcp.json at project root.
"""
import json
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tool_handler import (
    handle_write_prd, handle_approve_prd,
    handle_write_domain_model, handle_approve_domain_model,
    handle_write_brief, handle_approve_brief,
    handle_write_design, handle_approve_design,
    handle_write_tech_stack, handle_approve_tech_stack,
    handle_write_model, handle_approve_model,
    handle_update_schema,
    get_available_artifacts, read_artifact,
    _MODEL_TYPE_TO_STAGE,
)
from renderer import render_prd, render_domain_model, render_brief, render_design, render_tech_stack, render_model

app = Server("agentic-team")

_SCHEMAS_DIR = Path(__file__).parent / "schemas"

_WRITE_BRIEF_INPUT_SCHEMA        = json.loads((_SCHEMAS_DIR / "brief.mcp.json").read_text())
_WRITE_PRD_INPUT_SCHEMA          = json.loads((_SCHEMAS_DIR / "prd.mcp.json").read_text())
_WRITE_DOMAIN_MODEL_INPUT_SCHEMA = json.loads((_SCHEMAS_DIR / "domain.mcp.json").read_text())
_WRITE_DESIGN_INPUT_SCHEMA       = json.loads((_SCHEMAS_DIR / "design.mcp.json").read_text())
_WRITE_TECH_STACK_INPUT_SCHEMA   = json.loads((_SCHEMAS_DIR / "tech_stack.mcp.json").read_text())


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
                    "slug": {
                        "type": "string",
                        "description": "Project slug, e.g. 'deploy-rollback'.",
                    },
                    "stage": {
                        "type": "string",
                        "description": "DAG stage: brief, prd, domain, or design.",
                    },
                    "version": {
                        "type": "integer",
                        "description": "Version number to read (e.g. 1, 2). Omit for latest.",
                    },
                },
            },
        ),
        Tool(
            name="get_available_artifacts",
            description=(
                "Return in-progress, approved, and ready-to-start artifacts for a DAG stage. "
                "Call this at the start of a no-argument session to populate the opening menu. "
                "Returns three buckets: in_progress (draft), approved, and ready_to_start "
                "(approved upstream artifact exists but this stage has no artifact yet)."
            ),
            inputSchema={
                "type": "object",
                "required": ["stage"],
                "properties": {
                    "stage": {
                        "type": "string",
                        "description": "DAG stage to query. Current stages: brief, prd, domain, design, tech_stack.",
                    }
                },
            },
        ),
        Tool(
            name="write_prd",
            description="Write or update a structured PRD artifact to disk. Call this when the user signals readiness to draft or refine.",
            inputSchema=_WRITE_PRD_INPUT_SCHEMA,
        ),
        Tool(
            name="approve_prd",
            description="Mark a PRD artifact as approved. Advances the DAG to the Domain Agent.",
            inputSchema={
                "type": "object",
                "required": ["artifact_path"],
                "properties": {
                    "artifact_path": {
                        "type": "string",
                        "description": "Relative path to the PRD JSON file. Example: artifacts/deploy-rollback/prd/v2.json",
                    }
                },
            },
        ),
        Tool(
            name="write_model",
            description=(
                "Write or update a model artifact for any archetype. "
                "Routes to the correct stage directory based on model_type. "
                "The engine validates model_type against the PRD archetype and resolves the upstream reference from the topology."
            ),
            inputSchema={
                "type": "object",
                "required": ["slug", "model_type", "content"],
                "properties": {
                    "slug": {"type": "string"},
                    "model_type": {
                        "type": "string",
                        "enum": ["domain", "data_flow", "system", "workflow"],
                        "description": "Must match the PRD archetype for this slug.",
                    },
                    "content": {
                        "type": "object",
                        "description": "Model content. Fields are validated against the instance schema at approval time.",
                    },
                    "decision_log_entry": {
                        "type": "object",
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
            name="approve_model",
            description="Approve a model artifact after validating all mandatory schema fields are present.",
            inputSchema={
                "type": "object",
                "required": ["artifact_path"],
                "properties": {
                    "artifact_path": {
                        "type": "string",
                        "description": "Relative path to the model JSON file. Example: artifacts/my-app/model_domain/v1.json",
                    }
                },
            },
        ),
        Tool(
            name="write_design",
            description="Write or update a structured Design artifact to disk. Call this when the user signals readiness to draft or refine. Pass only slug — the engine resolves the upstream domain model path automatically.",
            inputSchema=_WRITE_DESIGN_INPUT_SCHEMA,
        ),
        Tool(
            name="approve_design",
            description="Mark a Design artifact as approved. Advances the DAG to the Execution Agent.",
            inputSchema={
                "type": "object",
                "required": ["artifact_path"],
                "properties": {
                    "artifact_path": {
                        "type": "string",
                        "description": "Relative path to the design JSON file. Example: artifacts/deploy-rollback/design/v1.json",
                    }
                },
            },
        ),
        Tool(
            name="write_brief",
            description="Write or update a structured Brief artifact to disk. Call this when the user signals readiness to draft or refine, and after direction has been confirmed.",
            inputSchema=_WRITE_BRIEF_INPUT_SCHEMA,
        ),
        Tool(
            name="approve_brief",
            description="Mark a Brief artifact as approved. Advances the DAG to the Product Owner.",
            inputSchema={
                "type": "object",
                "required": ["artifact_path"],
                "properties": {
                    "artifact_path": {
                        "type": "string",
                        "description": "Relative path to the brief JSON file. Example: artifacts/deploy-rollback/brief/v1.json",
                    }
                },
            },
        ),
        Tool(
            name="write_tech_stack",
            description=(
                "Write or update a Tech Stack artifact to disk. "
                "Call this when every decision on the confirmed agenda is resolved and the user signals readiness to draft. "
                "Pass only slug — the engine resolves the upstream design artifact path automatically."
            ),
            inputSchema=_WRITE_TECH_STACK_INPUT_SCHEMA,
        ),
        Tool(
            name="approve_tech_stack",
            description="Mark a Tech Stack artifact as approved. Advances the DAG to the Execution Agent.",
            inputSchema={
                "type": "object",
                "required": ["artifact_path"],
                "properties": {
                    "artifact_path": {
                        "type": "string",
                        "description": "Relative path to the tech stack JSON file. Example: artifacts/deploy-rollback/tech_stack/v1.json",
                    }
                },
            },
        ),
        Tool(
            name="update_schema",
            description=(
                "Add a field to the instance schema for a slug/stage. "
                "Use this when you discover a field that belongs in the artifact but is not in the base schema. "
                "The field will be validated at approval time if kind is 'mandatory'."
            ),
            inputSchema={
                "type": "object",
                "required": ["slug", "stage", "field_name", "kind", "description"],
                "properties": {
                    "slug": {"type": "string"},
                    "stage": {"type": "string"},
                    "field_name": {"type": "string", "description": "Name of the new field."},
                    "kind": {"type": "string", "enum": ["mandatory", "optional"]},
                    "description": {"type": "string", "description": "What this field captures and why it matters."},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        return await _dispatch(name, arguments)
    except ValueError as e:
        return [TextContent(type="text", text=str(e))]


async def _dispatch(name: str, arguments: dict) -> list[TextContent]:
    if name == "read_artifact":
        artifact = read_artifact(
            arguments["slug"],
            arguments["stage"],
            arguments.get("version"),
        )
        return [TextContent(type="text", text=json.dumps(artifact, indent=2))]

    if name == "get_available_artifacts":
        result = get_available_artifacts(arguments["stage"])
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "write_prd":
        slug = arguments.get("slug", "unknown")
        existing_path = Path("artifacts") / slug / "prd"
        existing_prd = None

        if existing_path.exists():
            versions = sorted(existing_path.glob("v*.json"), key=lambda p: int(p.stem[1:]))
            if versions:
                existing_prd = json.loads(versions[-1].read_text())

        artifact = handle_write_prd(arguments, existing_prd)
        rendered = render_prd(artifact)
        return [TextContent(type="text", text=rendered)]

    if name == "approve_prd":
        artifact = handle_approve_prd(arguments["artifact_path"])
        return [TextContent(type="text", text=f"PRD approved: {arguments['artifact_path']}\nStatus: {artifact['status']}")]

    if name == "write_model":
        slug = arguments.get("slug", "unknown")
        model_type = arguments.get("model_type", "")
        stage = _MODEL_TYPE_TO_STAGE.get(model_type)
        existing_model = None
        if stage:
            existing_path = Path("artifacts") / slug / stage
            if existing_path.exists():
                versions = sorted(existing_path.glob("v*.json"), key=lambda p: int(p.stem[1:]))
                if versions:
                    existing_model = json.loads(versions[-1].read_text())
        artifact = handle_write_model(dict(arguments), existing_model)
        return [TextContent(type="text", text=render_model(artifact))]

    if name == "approve_model":
        artifact = handle_approve_model(arguments["artifact_path"])
        return [TextContent(type="text", text=f"Model approved: {arguments['artifact_path']}\nStatus: {artifact['status']}")]

    if name == "write_design":
        slug = arguments.get("slug", "unknown")
        existing_path = Path("artifacts") / slug / "design"
        existing_design = None

        if existing_path.exists():
            versions = sorted(existing_path.glob("v*.json"), key=lambda p: int(p.stem[1:]))
            if versions:
                existing_design = json.loads(versions[-1].read_text())

        artifact = handle_write_design(arguments, existing_design)
        rendered = render_design(artifact)
        return [TextContent(type="text", text=rendered)]

    if name == "approve_design":
        artifact = handle_approve_design(arguments["artifact_path"])
        return [TextContent(type="text", text=f"Design approved: {arguments['artifact_path']}\nStatus: {artifact['status']}")]

    if name == "write_brief":
        slug = arguments.get("slug", "unknown")
        existing_path = Path("artifacts") / slug / "brief"
        existing_brief = None

        if existing_path.exists():
            versions = sorted(existing_path.glob("v*.json"), key=lambda p: int(p.stem[1:]))
            if versions:
                existing_brief = json.loads(versions[-1].read_text())

        artifact = handle_write_brief(arguments, existing_brief)
        rendered = render_brief(artifact)
        return [TextContent(type="text", text=rendered)]

    if name == "approve_brief":
        artifact = handle_approve_brief(arguments["artifact_path"])
        return [TextContent(type="text", text=f"Brief approved: {arguments['artifact_path']}\nStatus: {artifact['status']}")]

    if name == "write_tech_stack":
        slug = arguments.get("slug", "unknown")
        existing_path = Path("artifacts") / slug / "tech_stack"
        existing_tech_stack = None

        if existing_path.exists():
            versions = sorted(existing_path.glob("v*.json"), key=lambda p: int(p.stem[1:]))
            if versions:
                existing_tech_stack = json.loads(versions[-1].read_text())

        artifact = handle_write_tech_stack(arguments, existing_tech_stack)
        rendered = render_tech_stack(artifact)
        return [TextContent(type="text", text=rendered)]

    if name == "approve_tech_stack":
        artifact = handle_approve_tech_stack(arguments["artifact_path"])
        return [TextContent(type="text", text=f"Tech stack approved: {arguments['artifact_path']}\nStatus: {artifact['status']}")]

    if name == "update_schema":
        schema = handle_update_schema(
            arguments["slug"],
            arguments["stage"],
            arguments["field_name"],
            arguments["kind"],
            arguments["description"],
        )
        return [TextContent(type="text", text=json.dumps(schema, indent=2))]

    return [TextContent(type="text", text=f"ERROR: unknown tool '{name}'")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
