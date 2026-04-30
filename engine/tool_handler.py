import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


_SCHEMAS_DIR = Path(__file__).parent / "schemas"

# ---------------------------------------------------------------------------
# Archetype, topology, and stage configuration
# ---------------------------------------------------------------------------

# archetype_confidence intentionally omitted: agents may revise confidence on refinements
_ARCHETYPE_LOCKED_KEYS = ("primary_archetype", "secondary_archetype", "archetype_reasoning")

_VALID_COMBINATIONS: frozenset[tuple] = frozenset({
    ("domain_system",),
    ("data_pipeline",),
    ("system_integration",),
    ("process_system",),
    ("system_evolution",),
    ("system_integration", "process_system"),
})

_DAG_TOPOLOGIES: dict[tuple, list[str]] = {
    ("domain_system",):                       ["brief", "prd", "model_domain",     "design", "tech_stack"],
    ("data_pipeline",):                       ["brief", "prd", "model_data_flow",  "design", "tech_stack"],
    ("system_integration",):                  ["brief", "prd", "model_system",     "design", "tech_stack"],
    ("process_system",):                      ["brief", "prd", "model_workflow",   "design", "tech_stack"],
    ("system_evolution",):                    ["brief", "prd", "model_evolution",  "design", "tech_stack"],
    ("system_integration", "process_system"): ["brief", "prd", "model_workflow", "model_system", "design", "tech_stack"],
}

_BASE_SCHEMAS_BY_STAGE: dict[str, str] = {
    "model_domain":              "model-domain.json",
    "model_data_flow":           "model-data-flow.json",
    "model_system":              "model-system.json",
    "model_workflow":            "model-workflow.json",
    "model_evolution":           "model-evolution.json",
    "brief":                     "brief.base.json",
    "prd":                       "prd.base.json",
    "tech_stack":                "tech_stack.base.json",
    # design base schema key is "design-{primary_archetype}" — resolved at write time
    "design-domain_system":      "design-domain_system.json",
    "design-data_pipeline":      "design-data_pipeline.json",
    "design-system_integration": "design-system_integration.json",
    "design-process_system":     "design-process_system.json",
    "design-system_evolution":   "design-system_evolution.json",
}

# Per-stage engine configuration: upstream resolution, locked content fields,
# artifact id prefix, and author tag written to decision_log entries.
# upstream="topology" means the preceding stage is resolved from the DAG at write time.
_STAGE_CONFIG: dict[str, dict] = {
    "brief": {
        "upstream":      None,
        "locked_fields": frozenset({"idea"}),
        "id_prefix":     "brief",
        "author":        "agent:brainstorm-agent",
    },
    "prd": {
        "upstream":      "brief",
        "locked_fields": frozenset(_ARCHETYPE_LOCKED_KEYS),
        "id_prefix":     "prd",
        "author":        "agent:product-agent",
    },
    "model_domain": {
        "upstream":      "topology",
        "locked_fields": frozenset(),
        "id_prefix":     "model-domain",
        "author":        "agent:model-agent-domain",
    },
    "model_data_flow": {
        "upstream":      "topology",
        "locked_fields": frozenset(),
        "id_prefix":     "model-data-flow",
        "author":        "agent:model-agent-data_flow",
    },
    "model_system": {
        "upstream":      "topology",
        "locked_fields": frozenset(),
        "id_prefix":     "model-system",
        "author":        "agent:model-agent-system",
    },
    "model_workflow": {
        "upstream":      "topology",
        "locked_fields": frozenset(),
        "id_prefix":     "model-workflow",
        "author":        "agent:model-agent-workflow",
    },
    "model_evolution": {
        "upstream":      "topology",
        "locked_fields": frozenset(),
        "id_prefix":     "model-evolution",
        "author":        "agent:model-agent-evolution",
    },
    "design": {
        "upstream":      "topology",
        "locked_fields": frozenset(),
        "id_prefix":     "design",
        "author":        "agent:architecture-agent",
    },
    "tech_stack": {
        "upstream":      "design",
        "locked_fields": frozenset(),
        "id_prefix":     "tech-stack",
        "author":        "agent:tech-stack-agent",
    },
}

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")

# ---------------------------------------------------------------------------
# Artifact directory resolution — CWD-relative for portability
#
# In production the artifacts directory is always resolved from the process
# working directory at call time, so artifacts land in whatever project the
# user has open in Claude Code.
#
# _ARTIFACTS_DIR_OVERRIDE is a test hook: conftest.py monkeypatches it to a
# tmp_path so tests never touch the real artifacts/ directory.
# ---------------------------------------------------------------------------

_ARTIFACTS_DIR_OVERRIDE: Path | None = None


def _get_artifacts_dir() -> Path:
    if _ARTIFACTS_DIR_OVERRIDE is not None:
        return _ARTIFACTS_DIR_OVERRIDE
    return Path(os.getcwd()) / "artifacts"


# ---------------------------------------------------------------------------
# Artifact lookup helpers
# ---------------------------------------------------------------------------

def find_latest(slug: str, stage: str, status: str | None = None) -> Path | None:
    """Return path to highest-versioned artifact at artifacts/<slug>/<stage>/.

    If status is given, filters to only artifacts matching that status
    (iterates from highest version down). Returns None if not found.
    """
    stage_dir = _get_artifacts_dir() / slug / stage
    if not stage_dir.exists():
        return None
    versions = sorted(stage_dir.glob("v*.json"), key=lambda p: int(p.stem[1:]))
    if not versions:
        return None
    if status is None:
        return versions[-1]
    for path in reversed(versions):
        artifact = json.loads(path.read_text())
        if artifact.get("status") == status:
            return path
    return None


def read_artifact(slug: str, stage: str, version: int | None = None) -> dict:
    """Return the full content of a specific artifact version.

    If version is omitted, returns the latest version for that slug/stage.
    Raises ValueError if the artifact does not exist.
    """
    _validate_slug_format(slug, "read_artifact")
    artifacts_dir = _get_artifacts_dir()
    stage_dir = artifacts_dir / slug / stage
    if not stage_dir.exists():
        raise ValueError(
            f"ERROR [read_artifact]: no artifacts found for slug '{slug}', stage '{stage}'."
        )
    versions = sorted(stage_dir.glob("v*.json"), key=lambda p: int(p.stem[1:]))
    if not versions:
        raise ValueError(
            f"ERROR [read_artifact]: no artifacts found for slug '{slug}', stage '{stage}'."
        )
    if version is None:
        path = versions[-1]
    else:
        path = stage_dir / f"v{version}.json"
        if not path.exists():
            raise ValueError(
                f"ERROR [read_artifact]: version {version} not found for slug '{slug}', stage '{stage}'."
            )
    artifact = json.loads(path.read_text())
    schema_path = _get_artifacts_dir() / slug / stage / "schema.json"
    schema = json.loads(schema_path.read_text()) if schema_path.exists() else {}
    return {"artifact": artifact, "schema": schema}


# ---------------------------------------------------------------------------
# Instance schema helpers
# ---------------------------------------------------------------------------

def _init_schema(slug: str, stage: str, base_schema_key: str | None = None) -> None:
    """Create schema.json for slug/stage if it does not exist yet.

    Copies the base schema from engine/schemas/ when one is defined for the
    stage. Falls back to an empty schema for stages without a base schema.
    base_schema_key overrides the lookup key (used for design: "design-{archetype}").
    Called on the first write for a slug/stage — idempotent on subsequent calls.
    """
    schema_path = _get_artifacts_dir() / slug / stage / "schema.json"
    if schema_path.exists():
        return
    lookup_key = base_schema_key if base_schema_key is not None else stage
    base_filename = _BASE_SCHEMAS_BY_STAGE.get(lookup_key)
    if base_filename is not None:
        base_schema = json.loads((_SCHEMAS_DIR / base_filename).read_text())
    else:
        base_schema = {"fields": {}}
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(json.dumps(base_schema, indent=2))


def _validate_mandatory_fields(artifact_path: Path, content: dict, caller: str) -> None:
    """Raise ValueError if any mandatory schema fields are absent from content.

    Reads schema.json from artifact_path.parent. No-ops when schema.json does
    not exist (stages without a schema have no mandatory fields to enforce).
    """
    schema_path = artifact_path.parent / "schema.json"
    if not schema_path.exists():
        return
    schema = json.loads(schema_path.read_text())
    mandatory = [
        name for name, field in schema.get("fields", {}).items()
        if field.get("kind") == "mandatory"
    ]
    missing = [f for f in mandatory if f not in content]
    if missing:
        raise ValueError(
            f"ERROR [{caller}]: cannot approve — missing mandatory fields: "
            f"{', '.join(missing)}. Add these fields before approving."
        )


def _clear_draft_content_key(slug: str, stage: str, key: str) -> None:
    """Remove a key from the content of the latest draft artifact, if present."""
    draft_path = find_latest(slug, stage, status="draft")
    if draft_path is None:
        return
    artifact = json.loads(draft_path.read_text())
    content = artifact.get("content", {})
    if key in content:
        del content[key]
        artifact["content"] = content
        draft_path.write_text(json.dumps(artifact, indent=2))


def handle_add_schema_field(slug: str, stage: str, field_name: str, kind: str, description: str) -> dict:
    _validate_slug_format(slug, "add_schema_field")
    if kind not in {"mandatory", "optional"}:
        raise ValueError(
            f"ERROR [add_schema_field]: kind must be 'mandatory' or 'optional', got '{kind}'."
        )
    if not field_name or not field_name.strip():
        raise ValueError("ERROR [add_schema_field]: field_name must not be empty.")
    if not description or not description.strip():
        raise ValueError("ERROR [add_schema_field]: description must not be empty.")

    schema_path = _get_artifacts_dir() / slug / stage / "schema.json"
    if not schema_path.exists():
        raise ValueError(
            f"ERROR [add_schema_field]: no schema found for slug '{slug}', stage '{stage}'. "
            f"The stage must be written at least once before the schema can be updated."
        )

    schema = json.loads(schema_path.read_text())
    fields = schema.setdefault("fields", {})

    if field_name in fields:
        raise ValueError(
            f"ERROR [add_schema_field]: field '{field_name}' already exists in the schema for "
            f"slug '{slug}', stage '{stage}'. Choose a different name."
        )

    fields[field_name] = {"kind": kind, "description": description.strip()}
    schema.setdefault("decision_log", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": "schema_field_added",
        "field_name": field_name,
        "kind": kind,
        "description": description.strip(),
    })

    schema_path.write_text(json.dumps(schema, indent=2))
    return schema


def handle_update_schema_field(
    slug: str,
    stage: str,
    field_name: str,
    kind: str | None = None,
    description: str | None = None,
    new_field_name: str | None = None,
) -> dict:
    _validate_slug_format(slug, "update_schema_field")
    if not any([kind, description, new_field_name]):
        raise ValueError(
            "ERROR [update_schema_field]: at least one of kind, description, or new_field_name must be provided."
        )
    if kind is not None and kind not in {"mandatory", "optional"}:
        raise ValueError(
            f"ERROR [update_schema_field]: kind must be 'mandatory' or 'optional', got '{kind}'."
        )

    schema_path = _get_artifacts_dir() / slug / stage / "schema.json"
    if not schema_path.exists():
        raise ValueError(
            f"ERROR [update_schema_field]: no schema found for slug '{slug}', stage '{stage}'."
        )

    schema = json.loads(schema_path.read_text())
    fields = schema.setdefault("fields", {})

    if field_name not in fields:
        raise ValueError(
            f"ERROR [update_schema_field]: field '{field_name}' does not exist in the schema for "
            f"slug '{slug}', stage '{stage}'."
        )

    if new_field_name is not None and new_field_name != field_name and new_field_name in fields:
        raise ValueError(
            f"ERROR [update_schema_field]: field '{new_field_name}' already exists in the schema."
        )

    field = fields[field_name]
    if kind is not None:
        field["kind"] = kind
    if description is not None:
        field["description"] = description.strip()

    log_entry: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": "schema_field_updated",
        "field_name": field_name,
    }
    if new_field_name is not None:
        fields[new_field_name] = fields.pop(field_name)
        _clear_draft_content_key(slug, stage, field_name)
        log_entry["new_field_name"] = new_field_name
    if kind is not None:
        log_entry["kind"] = kind
    if description is not None:
        log_entry["description"] = description.strip()

    schema.setdefault("decision_log", []).append(log_entry)
    schema_path.write_text(json.dumps(schema, indent=2))
    return schema


def handle_delete_schema_field(slug: str, stage: str, field_name: str, justification: str) -> dict:
    _validate_slug_format(slug, "delete_schema_field")
    if not justification or not justification.strip():
        raise ValueError("ERROR [delete_schema_field]: justification must not be empty.")

    schema_path = _get_artifacts_dir() / slug / stage / "schema.json"
    if not schema_path.exists():
        raise ValueError(
            f"ERROR [delete_schema_field]: no schema found for slug '{slug}', stage '{stage}'."
        )

    schema = json.loads(schema_path.read_text())
    fields = schema.setdefault("fields", {})

    if field_name not in fields:
        raise ValueError(
            f"ERROR [delete_schema_field]: field '{field_name}' does not exist in the schema for "
            f"slug '{slug}', stage '{stage}'."
        )

    del fields[field_name]
    _clear_draft_content_key(slug, stage, field_name)

    schema.setdefault("decision_log", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": "schema_field_deleted",
        "field_name": field_name,
        "justification": justification.strip(),
    })

    schema_path.write_text(json.dumps(schema, indent=2))
    return schema


def _resolve_topology(slug: str) -> list[str] | None:
    """Return the ordered DAG stage list for slug, or None if undetermined.

    Reads the approved PRD to extract the archetype combination, then looks
    up _DAG_TOPOLOGIES. Returns None when no approved PRD exists or when the
    PRD predates archetype classification (migration period).
    """
    prd_path = find_latest(slug, "prd", status="approved")
    if prd_path is None:
        return None
    content = json.loads(prd_path.read_text()).get("content", {})
    primary = content.get("primary_archetype")
    if primary is None:
        return None
    secondary = content.get("secondary_archetype")
    combo = (primary, secondary) if secondary else (primary,)
    topology = _DAG_TOPOLOGIES.get(combo)
    return list(topology) if topology is not None else None


def _next_stage(slug: str) -> str | None:
    """Return the next unstarted stage for slug by walking topology forward.

    Scans the slug's artifact state from the brief forward. Returns the first
    stage that has no artifact yet. Returns None when:
    - No approved brief exists (entry gate not met)
    - A stage is in-progress (not yet approved — one stage active at a time)
    - The topology cannot be determined (no approved PRD, or pre-archetype PRD)
    - All topology stages are already approved

    Brief is the DAG entry node and is never returned: briefs are created by the
    Brainstormer, not queued up as ready-to-start.
    """
    if find_latest(slug, "brief", status="approved") is None:
        return None

    prd_path = find_latest(slug, "prd")
    if prd_path is None:
        return "prd"

    if json.loads(prd_path.read_text()).get("status") != "approved":
        return None  # PRD in-progress — wait for approval

    topology = _resolve_topology(slug)
    if topology is None:
        return None  # PRD approved but predates archetype classification

    prd_idx = topology.index("prd")
    for stage in topology[prd_idx + 1:]:
        path = find_latest(slug, stage)
        if path is None:
            return stage  # First stage with no artifact yet
        if json.loads(path.read_text()).get("status") != "approved":
            return None  # Stage in-progress — wait
    return None  # All stages complete


def get_available_artifacts(stage: str) -> dict:
    """Return in-progress, approved, and ready-to-start artifacts for a stage.

    - in_progress: draft artifacts at this stage
    - approved: approved artifacts at this stage
    - ready_to_start: slugs where _next_stage(slug) == stage — the immediate
      upstream is approved and this stage has no artifact yet; topology-correct
      (slugs whose archetype does not include this stage never appear here)
    """
    artifacts_dir = _get_artifacts_dir()
    result: dict = {"in_progress": [], "approved": [], "ready_to_start": []}
    if not artifacts_dir.exists():
        return result

    for slug_dir in sorted(artifacts_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        path = find_latest(slug, stage)
        if path is not None:
            artifact = json.loads(path.read_text())
            entry = {
                "slug": slug,
                "status": artifact["status"],
                "version": artifact["version"],
                "open_questions": len(artifact.get("content", {}).get("open_questions", [])),
                "path": str(path.relative_to(artifacts_dir.parent)),
            }
            if artifact["status"] == "draft":
                result["in_progress"].append(entry)
            else:
                result["approved"].append(entry)
        else:
            if _next_stage(slug) == stage:
                result["ready_to_start"].append({"slug": slug})

    return result


def handle_get_work_context(slug: str, stage: str) -> dict:
    """Return the approved upstream artifact and current draft for a DAG stage.

    Provides everything an agent needs to start or continue work on a stage:
    the approved upstream output and any in-progress draft already written.
    """
    _validate_slug_format(slug, "get_work_context")

    if stage == "brief":
        raise ValueError(
            "ERROR [get_work_context]: stage 'brief' has no upstream. "
            "Use get_available_artifacts instead."
        )

    if stage == "prd":
        upstream_stage = "brief"
    else:
        topology = _resolve_topology(slug)
        if topology is None:
            raise ValueError(
                f"ERROR [get_work_context]: cannot determine topology for '{slug}'. "
                "Approve the PRD first."
            )

        if stage not in topology:
            raise ValueError(
                f"ERROR [get_work_context]: stage '{stage}' is not in the topology for '{slug}'."
            )

        idx = topology.index(stage)
        upstream_stage = topology[idx - 1]

    upstream_path = find_latest(slug, upstream_stage, status="approved")
    if upstream_path is None:
        agent_hint = upstream_stage.replace("_", "-")
        raise ValueError(
            f"ERROR [get_work_context]: '{upstream_stage}' for '{slug}' is not approved. "
            f"Approve it first with /{agent_hint}."
        )

    artifacts_dir = _get_artifacts_dir()
    upstream_artifact = json.loads(upstream_path.read_text())
    upstream_schema_path = artifacts_dir / slug / upstream_stage / "schema.json"
    upstream_schema = json.loads(upstream_schema_path.read_text()) if upstream_schema_path.exists() else {}

    draft_path = find_latest(slug, stage, status="draft")
    if draft_path is not None:
        draft_artifact = json.loads(draft_path.read_text())
        draft_schema_path = artifacts_dir / slug / stage / "schema.json"
        draft_schema = json.loads(draft_schema_path.read_text()) if draft_schema_path.exists() else {}
        current_draft = {"artifact": draft_artifact, "schema": draft_schema}
    else:
        current_draft = None

    return {
        "upstream": {"artifact": upstream_artifact, "schema": upstream_schema},
        "current_draft": current_draft,
    }


# ---------------------------------------------------------------------------
# Validation helpers — engine owns all validation
# ---------------------------------------------------------------------------

def _validate_schema(tool_input: dict, schema: dict, handler_name: str) -> None:
    """Validate tool_input against the full input schema (all nested fields)."""
    try:
        _jsonschema_validate(instance=tool_input, schema=schema)
    except ValidationError as e:
        path = " → ".join(str(p) for p in e.absolute_path) or "(root)"
        raise ValueError(
            f"ERROR [{handler_name}]: {path} — {e.message}\n"
            f"Correct the field and retry."
        )


def _validate_slug_format(slug: str, handler_name: str) -> None:
    """Slug must be lowercase alphanumeric + hyphens, no path traversal."""
    if not slug or not _SLUG_RE.match(slug):
        raise ValueError(
            f"ERROR [{handler_name}]: slug '{slug}' is invalid. "
            f"Use lowercase letters, digits, and hyphens only. "
            f"Must start and end with a letter or digit (e.g. 'deploy-rollback')."
        )


def _validate_approve_path(artifact_path: str, handler_name: str) -> Path:
    """Validate artifact_path: within artifacts dir, exists, not already approved."""
    artifacts_dir = _get_artifacts_dir()
    path = Path(artifact_path).resolve()
    if not path.is_relative_to(artifacts_dir.resolve()):
        raise ValueError(
            f"ERROR [{handler_name}]: path '{artifact_path}' is outside the "
            f"artifacts directory. Only paths within artifacts/ are allowed."
        )
    if not path.exists():
        raise ValueError(
            f"ERROR [{handler_name}]: artifact not found at '{artifact_path}'. "
            f"Check the path and retry."
        )
    artifact = json.loads(path.read_text())
    if artifact.get("status") == "approved":
        raise ValueError(
            f"ERROR [{handler_name}]: artifact at '{artifact_path}' is already approved."
        )
    return path


# ---------------------------------------------------------------------------
# Primary archetype helper
# ---------------------------------------------------------------------------

def _read_primary_archetype(slug: str) -> str | None:
    """Return primary_archetype from the approved PRD for slug, or None."""
    prd_path = find_latest(slug, "prd", status="approved")
    if prd_path is None:
        return None
    return json.loads(prd_path.read_text()).get("content", {}).get("primary_archetype")


# ---------------------------------------------------------------------------
# Generic artifact handlers
# ---------------------------------------------------------------------------

def handle_write_artifact(
    slug: str,
    stage: str,
    body: dict,
    decision_log_entry: dict | None = None,
) -> dict:
    """Write or update any artifact stage. Body is stored verbatim as content.

    On v1: verifies upstream is approved, builds references, derives source_idea
    (prd), model_type (model_* stages), and primary_archetype (all non-brief stages).
    On v2+: enforces locked_fields from the existing artifact content.
    """
    _validate_slug_format(slug, "write_artifact")
    if stage not in _STAGE_CONFIG:
        raise ValueError(
            f"ERROR [write_artifact]: unknown stage '{stage}'. "
            f"Valid stages: {', '.join(sorted(_STAGE_CONFIG))}."
        )

    config = _STAGE_CONFIG[stage]
    artifacts_dir = _get_artifacts_dir()
    now = datetime.now(timezone.utc).isoformat()

    existing_path = find_latest(slug, stage)
    existing = json.loads(existing_path.read_text()) if existing_path else None

    if existing is None:
        upstream_key = config["upstream"]
        if upstream_key == "topology":
            topology = _resolve_topology(slug)
            if topology is None:
                raise ValueError(
                    f"ERROR [write_artifact]: cannot determine topology for '{slug}'. "
                    f"Approve the PRD with archetype fields first."
                )
            if stage not in topology:
                raise ValueError(
                    f"ERROR [write_artifact]: stage '{stage}' is not in the topology for '{slug}'."
                )
            upstream_stage: str | None = topology[topology.index(stage) - 1]
        else:
            upstream_stage = upstream_key

        if upstream_stage is not None:
            upstream_path = find_latest(slug, upstream_stage, status="approved")
            if upstream_path is None:
                raise ValueError(
                    f"ERROR [write_artifact]: no approved {upstream_stage} found for slug '{slug}'. "
                    f"Approve the {upstream_stage} first."
                )
            references = [str(upstream_path.relative_to(artifacts_dir.parent))]
        else:
            references = []

        artifact_id = f"{config['id_prefix']}-{uuid.uuid4()}"
        version = 1
        parent_version = None
        created_at = now
        prior_log: list = []

        source_idea: str | None = None
        if stage == "prd":
            brief_data = json.loads(
                find_latest(slug, "brief", status="approved").read_text()
            )
            source_idea = brief_data.get("content", {}).get("idea")
    else:
        slug = existing["slug"]
        artifact_id = existing["id"]
        version = existing["version"] + 1
        parent_version = existing["version"]
        created_at = existing["created_at"]
        prior_log = existing.get("decision_log", [])
        references = existing.get("references", [])
        source_idea = existing.get("source_idea") if stage == "prd" else None

        existing_content = existing.get("content", {})
        for key in config["locked_fields"]:
            if key in existing_content:
                body[key] = existing_content[key]
            else:
                body.pop(key, None)

    folder = artifacts_dir / slug / stage
    folder.mkdir(parents=True, exist_ok=True)

    if stage == "design":
        primary_archetype = _read_primary_archetype(slug)
        _init_schema(
            slug, stage,
            base_schema_key=f"design-{primary_archetype}" if primary_archetype else None,
        )
    else:
        _init_schema(slug, stage)

    if decision_log_entry:
        decision_log = prior_log + [{
            "version": version,
            "timestamp": now,
            "author": config["author"],
            "trigger": decision_log_entry.get("trigger", "human_feedback"),
            "summary": decision_log_entry.get("summary", ""),
            "changed_fields": decision_log_entry.get("changed_fields", []),
        }]
    else:
        decision_log = prior_log

    artifact: dict = {
        "id": artifact_id,
        "slug": slug,
        "version": version,
        "parent_version": parent_version,
        "created_at": created_at,
        "updated_at": now,
        "status": "draft",
        "references": references,
        "decision_log": decision_log,
        "content": body,
    }

    if stage == "prd" and source_idea is not None:
        artifact["source_idea"] = source_idea
    if stage.startswith("model_"):
        artifact["model_type"] = stage.removeprefix("model_")
    if stage != "brief":
        archetype = _read_primary_archetype(slug)
        if archetype is not None:
            artifact["primary_archetype"] = archetype

    path = folder / f"v{version}.json"
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_approve_artifact(artifact_path: str) -> dict:
    """Approve any artifact after validating all mandatory schema fields are present."""
    path = _validate_approve_path(artifact_path, "approve_artifact")
    artifact = json.loads(path.read_text())
    _validate_mandatory_fields(path, artifact.get("content", {}), "approve_artifact")
    now = datetime.now(timezone.utc).isoformat()
    stage_label = path.parent.name.replace("_", " ")
    artifact["status"] = "approved"
    artifact["updated_at"] = now
    artifact.setdefault("decision_log", []).append({
        "version": artifact["version"],
        "timestamp": now,
        "author": "human",
        "trigger": "approval",
        "summary": f"{stage_label} approved.",
        "changed_fields": ["status"],
    })
    path.write_text(json.dumps(artifact, indent=2))
    slug = path.parts[path.parts.index("artifacts") + 1]
    return {**artifact, "next_stage": _next_stage(slug)}
