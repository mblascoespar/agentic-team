import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import validate as _jsonschema_validate, ValidationError


_SCHEMAS_DIR = Path(__file__).parent / "schemas"

# ---------------------------------------------------------------------------
# Input schema loading — single source of truth is engine/schemas/
# ---------------------------------------------------------------------------

_BRIEF_INPUT_SCHEMA        = json.loads((_SCHEMAS_DIR / "brief.input.json").read_text())
_PRD_INPUT_SCHEMA          = json.loads((_SCHEMAS_DIR / "prd.input.json").read_text())
_DOMAIN_MODEL_INPUT_SCHEMA = json.loads((_SCHEMAS_DIR / "domain.input.json").read_text())
_DESIGN_INPUT_SCHEMA       = json.loads((_SCHEMAS_DIR / "design.input.json").read_text())
_TECH_STACK_INPUT_SCHEMA   = json.loads((_SCHEMAS_DIR / "tech_stack.input.json").read_text())

_PRD_CONTENT_KEYS = (
    "title", "problem", "target_users", "goals", "success_metrics",
    "scope_in", "scope_out", "features", "assumptions", "open_questions",
    "primary_archetype", "secondary_archetype", "archetype_confidence", "archetype_reasoning",
)

# archetype_confidence intentionally omitted: agents may revise confidence on refinements
_ARCHETYPE_LOCKED_KEYS = ("primary_archetype", "secondary_archetype", "archetype_reasoning")

_VALID_COMBINATIONS: frozenset[tuple] = frozenset({
    ("domain_system",),
    ("data_pipeline",),
    ("system_integration",),
    ("process_system",),
    ("system_integration", "process_system"),
})

# TODO(step-2): consumed by DAG router in get_available_artifacts topology resolution
_DAG_TOPOLOGIES: dict[tuple, list[str]] = {
    ("domain_system",):                       ["brief", "prd", "model_domain",    "design", "tech_stack"],
    ("data_pipeline",):                       ["brief", "prd", "model_data_flow", "design", "tech_stack"],
    ("system_integration",):                  ["brief", "prd", "model_system",    "design", "tech_stack"],
    ("process_system",):                      ["brief", "prd", "model_workflow",  "design", "tech_stack"],
    ("system_integration", "process_system"): ["brief", "prd", "model_system", "model_workflow", "design", "tech_stack"],
}

_BRIEF_CONTENT_KEYS = (
    "idea", "alternatives", "chosen_direction",
    "competitive_scan", "complexity_assessment", "open_questions",
)

_DESIGN_CONTENT_KEYS = (
    "layering_strategy", "aggregate_consistency", "integration_patterns",
    "storage", "cross_cutting", "testing_strategy", "nfrs", "open_questions",
)

_TECH_STACK_CONTENT_KEYS = ("adrs", "open_questions")

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")

# ---------------------------------------------------------------------------
# DAG topology — single source of truth for stage ordering
# Agents never see this; the engine uses it for upstream resolution and
# get_available_artifacts queries.
# ---------------------------------------------------------------------------

_UPSTREAM_STAGE: dict[str, str] = {
    "prd":        "brief",
    "domain":     "prd",
    "design":     "domain",
    "tech_stack": "design",
}

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
    return json.loads(path.read_text())


def get_available_artifacts(stage: str) -> dict:
    """Return in-progress, approved, and ready-to-start artifacts for a stage.

    - in_progress: draft artifacts at this stage
    - approved: approved artifacts at this stage
    - ready_to_start: slugs whose upstream stage artifact is approved but
      this stage has no artifact yet (entry-node stages have no ready_to_start)
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
            upstream_stage = _UPSTREAM_STAGE.get(stage)
            if upstream_stage and find_latest(slug, upstream_stage, status="approved"):
                result["ready_to_start"].append({"slug": slug})

    return result


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
# Archetype helpers
# ---------------------------------------------------------------------------

def _fmt_combinations() -> str:
    parts = []
    for combo in sorted(_VALID_COMBINATIONS):
        if len(combo) == 1:
            parts.append(f"primary={combo[0]!r}")
        else:
            parts.append(f"primary={combo[0]!r} + secondary={combo[1]!r}")
    return ", ".join(parts)


def _validate_archetype_combination(primary: str, secondary: str | None) -> None:
    combo = (primary, secondary) if secondary else (primary,)
    if combo not in _VALID_COMBINATIONS:
        raise ValueError(
            f"ERROR [write_prd]: unsupported archetype combination "
            f"primary={primary!r} secondary={secondary!r}. "
            f"Valid combinations: {_fmt_combinations()}"
        )



# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_write_prd(tool_input: dict, existing_prd: dict | None = None) -> dict:
    _validate_schema(tool_input, _PRD_INPUT_SCHEMA, "write_prd")
    _validate_slug_format(tool_input.get("slug", ""), "write_prd")

    artifacts_dir = _get_artifacts_dir()
    now = datetime.now(timezone.utc).isoformat()
    log_entry_input = tool_input.pop("decision_log_entry", None)

    if existing_prd is None:
        slug = tool_input["slug"]
        # Validate archetype combination before the Brief gate: stateless and cheap,
        # so agents get the right error regardless of upstream artifact state.
        primary = tool_input["primary_archetype"]
        secondary = tool_input.get("secondary_archetype")
        _validate_archetype_combination(primary, secondary)

        upstream = find_latest(slug, "brief", status="approved")
        if upstream is None:
            raise ValueError(
                f"ERROR [write_prd]: no approved Brief found for slug '{slug}'. "
                f"Run /brainstorm {slug} and approve the Brief first."
            )

        references = [str(upstream.relative_to(artifacts_dir.parent))]
        prd_id = f"prd-{uuid.uuid4()}"
        version = 1
        parent_version = None
        created_at = now
        prior_log = []
        source_idea = tool_input.get("source_idea")
    else:
        slug = existing_prd["slug"]  # orchestrator-enforced: agent cannot change slug
        prd_id = existing_prd["id"]
        version = existing_prd["version"] + 1
        parent_version = existing_prd["version"]
        created_at = existing_prd["created_at"]
        prior_log = existing_prd.get("decision_log", [])
        source_idea = existing_prd["source_idea"]
        references = existing_prd.get("references", [])
        # Lock archetype fields on v2+: engine overwrites whatever the agent provided.
        # Keys absent from v1 are evicted — agents cannot add them on refinement turns.
        locked_content = existing_prd.get("content", {})
        for key in _ARCHETYPE_LOCKED_KEYS:
            if key in locked_content:
                tool_input[key] = locked_content[key]
            else:
                tool_input.pop(key, None)

    folder = artifacts_dir / slug / "prd"
    folder.mkdir(parents=True, exist_ok=True)

    if log_entry_input:
        decision_log = prior_log + [{
            "version": version,
            "timestamp": now,
            "author": "agent:product-agent",
            "trigger": log_entry_input.get("trigger", "human_feedback"),
            "summary": log_entry_input.get("summary", ""),
            "changed_fields": log_entry_input.get("changed_fields", []),
        }]
    else:
        decision_log = prior_log

    artifact = {
        "id": prd_id,
        "slug": slug,
        "version": version,
        "parent_version": parent_version,
        "created_at": created_at,
        "updated_at": now,
        "source_idea": source_idea,
        "status": "draft",
        "references": references,
        "decision_log": decision_log,
        "content": {k: tool_input[k] for k in _PRD_CONTENT_KEYS if k in tool_input},
    }

    path = folder / f"v{version}.json"
    path.write_text(json.dumps(artifact, indent=2))

    return artifact


def handle_write_domain_model(tool_input: dict, existing_domain: dict | None = None) -> dict:
    _validate_schema(tool_input, _DOMAIN_MODEL_INPUT_SCHEMA, "write_domain_model")
    _validate_slug_format(tool_input.get("slug", ""), "write_domain_model")

    artifacts_dir = _get_artifacts_dir()
    now = datetime.now(timezone.utc).isoformat()
    log_entry_input = tool_input.pop("decision_log_entry", None)

    if existing_domain is None:
        slug = tool_input["slug"]
        upstream = find_latest(slug, "prd", status="approved")
        if upstream is None:
            raise ValueError(
                f"ERROR [write_domain_model]: no approved PRD found for slug '{slug}'. "
                f"Approve the PRD first, then call write_domain_model again."
            )
        references = [str(upstream.relative_to(artifacts_dir.parent))]
        domain_id = f"domain-{uuid.uuid4()}"
        version = 1
        parent_version = None
        created_at = now
        prior_log = []
    else:
        slug = existing_domain["slug"]  # orchestrator-enforced: agent cannot change slug
        domain_id = existing_domain["id"]
        version = existing_domain["version"] + 1
        parent_version = existing_domain["version"]
        created_at = existing_domain["created_at"]
        prior_log = existing_domain.get("decision_log", [])
        references = existing_domain.get("references", [])

    folder = artifacts_dir / slug / "domain"
    folder.mkdir(parents=True, exist_ok=True)

    if log_entry_input:
        decision_log = prior_log + [{
            "version": version,
            "timestamp": now,
            "author": "agent:domain-agent",
            "trigger": log_entry_input.get("trigger", "human_feedback"),
            "summary": log_entry_input.get("summary", ""),
            "changed_fields": log_entry_input.get("changed_fields", []),
        }]
    else:
        decision_log = prior_log

    content_keys = ("bounded_contexts", "context_map", "assumptions", "open_questions")
    artifact = {
        "id": domain_id,
        "slug": slug,
        "version": version,
        "parent_version": parent_version,
        "created_at": created_at,
        "updated_at": now,
        "status": "draft",
        "references": references,
        "decision_log": decision_log,
        "content": {k: tool_input[k] for k in content_keys if k in tool_input},
    }

    path = folder / f"v{version}.json"
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_approve_domain_model(artifact_path: str) -> dict:
    path = _validate_approve_path(artifact_path, "approve_domain_model")
    artifact = json.loads(path.read_text())
    now = datetime.now(timezone.utc).isoformat()
    artifact["status"] = "approved"
    artifact["updated_at"] = now
    artifact.setdefault("decision_log", []).append({
        "version": artifact["version"],
        "timestamp": now,
        "author": "human",
        "trigger": "approval",
        "summary": "Domain model approved.",
        "changed_fields": ["status"],
    })
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_approve_prd(artifact_path: str) -> dict:
    path = _validate_approve_path(artifact_path, "approve_prd")
    artifact = json.loads(path.read_text())
    now = datetime.now(timezone.utc).isoformat()
    artifact["status"] = "approved"
    artifact["updated_at"] = now
    artifact.setdefault("decision_log", []).append({
        "version": artifact["version"],
        "timestamp": now,
        "author": "human",
        "trigger": "approval",
        "summary": "PRD approved.",
        "changed_fields": ["status"],
    })
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_write_brief(tool_input: dict, existing_brief: dict | None = None) -> dict:
    _validate_schema(tool_input, _BRIEF_INPUT_SCHEMA, "write_brief")
    _validate_slug_format(tool_input.get("slug", ""), "write_brief")

    artifacts_dir = _get_artifacts_dir()
    now = datetime.now(timezone.utc).isoformat()
    log_entry_input = tool_input.pop("decision_log_entry", None)

    if existing_brief is None:
        slug = tool_input["slug"]
        brief_id = f"brief-{uuid.uuid4()}"
        version = 1
        parent_version = None
        created_at = now
        prior_log = []
        idea = tool_input.get("idea")
    else:
        slug = existing_brief["slug"]  # orchestrator-enforced: agent cannot change slug
        brief_id = existing_brief["id"]
        version = existing_brief["version"] + 1
        parent_version = existing_brief["version"]
        created_at = existing_brief["created_at"]
        prior_log = existing_brief.get("decision_log", [])
        idea = existing_brief["content"]["idea"]  # locked from v1

    folder = artifacts_dir / slug / "brief"
    folder.mkdir(parents=True, exist_ok=True)

    if log_entry_input:
        decision_log = prior_log + [{
            "version": version,
            "timestamp": now,
            "author": "agent:brainstorm-agent",
            "trigger": log_entry_input.get("trigger", "human_feedback"),
            "summary": log_entry_input.get("summary", ""),
            "changed_fields": log_entry_input.get("changed_fields", []),
        }]
    else:
        decision_log = prior_log

    content = {k: tool_input[k] for k in _BRIEF_CONTENT_KEYS if k in tool_input}
    content["idea"] = idea  # always use the locked value

    artifact = {
        "id": brief_id,
        "slug": slug,
        "version": version,
        "parent_version": parent_version,
        "created_at": created_at,
        "updated_at": now,
        "status": "draft",
        "references": [],
        "decision_log": decision_log,
        "content": content,
    }

    path = folder / f"v{version}.json"
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_write_design(tool_input: dict, existing_design: dict | None = None) -> dict:
    _validate_schema(tool_input, _DESIGN_INPUT_SCHEMA, "write_design")
    _validate_slug_format(tool_input.get("slug", ""), "write_design")

    # Handler-level semantic guards (not enforceable by JSON schema alone)
    for entry in tool_input.get("integration_patterns", []):
        if entry.get("acl_needed") and not entry.get("translation_approach", "").strip():
            raise ValueError(
                "ERROR [write_design]: integration_pattern with acl_needed=true requires a "
                "non-empty translation_approach. Add the translation direction and mechanism."
            )
    for entry in tool_input.get("layering_strategy", []):
        if entry.get("cqrs_applied") and not entry.get("cqrs_read_models"):
            raise ValueError(
                f"ERROR [write_design]: layering_strategy entry for context '{entry.get('context')}' "
                "has cqrs_applied=true but cqrs_read_models is missing or empty. "
                "List the aggregates that need separate read models."
            )

    artifacts_dir = _get_artifacts_dir()
    now = datetime.now(timezone.utc).isoformat()
    log_entry_input = tool_input.pop("decision_log_entry", None)

    if existing_design is None:
        slug = tool_input["slug"]
        upstream = find_latest(slug, "domain", status="approved")
        if upstream is None:
            raise ValueError(
                f"ERROR [write_design]: no approved Domain Model found for slug '{slug}'. "
                f"Approve the Domain Model first, then call write_design again."
            )
        references = [str(upstream.relative_to(artifacts_dir.parent))]
        design_id = f"design-{uuid.uuid4()}"
        version = 1
        parent_version = None
        created_at = now
        prior_log = []
    else:
        slug = existing_design["slug"]  # orchestrator-enforced: agent cannot change slug
        design_id = existing_design["id"]
        version = existing_design["version"] + 1
        parent_version = existing_design["version"]
        created_at = existing_design["created_at"]
        prior_log = existing_design.get("decision_log", [])
        references = existing_design.get("references", [])

    folder = artifacts_dir / slug / "design"
    folder.mkdir(parents=True, exist_ok=True)

    if log_entry_input:
        decision_log = prior_log + [{
            "version": version,
            "timestamp": now,
            "author": "agent:architecture-agent",
            "trigger": log_entry_input.get("trigger", "human_feedback"),
            "summary": log_entry_input.get("summary", ""),
            "changed_fields": log_entry_input.get("changed_fields", []),
        }]
    else:
        decision_log = prior_log

    artifact = {
        "id": design_id,
        "slug": slug,
        "version": version,
        "parent_version": parent_version,
        "created_at": created_at,
        "updated_at": now,
        "status": "draft",
        "references": references,
        "decision_log": decision_log,
        "content": {k: tool_input[k] for k in _DESIGN_CONTENT_KEYS if k in tool_input},
    }

    path = folder / f"v{version}.json"
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_approve_design(artifact_path: str) -> dict:
    path = _validate_approve_path(artifact_path, "approve_design")
    artifact = json.loads(path.read_text())
    now = datetime.now(timezone.utc).isoformat()
    artifact["status"] = "approved"
    artifact["updated_at"] = now
    artifact.setdefault("decision_log", []).append({
        "version": artifact["version"],
        "timestamp": now,
        "author": "human",
        "trigger": "approval",
        "summary": "Design artifact approved.",
        "changed_fields": ["status"],
    })
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_write_tech_stack(tool_input: dict, existing_tech_stack: dict | None = None) -> dict:
    _validate_schema(tool_input, _TECH_STACK_INPUT_SCHEMA, "write_tech_stack")
    _validate_slug_format(tool_input.get("slug", ""), "write_tech_stack")

    # Handler-level semantic guard: every rejection entry must have a non-empty rejection_reason.
    # (minLength: 1 in the schema guards the field type; this guard provides a clear message.)
    for adr in tool_input.get("adrs", []):
        for rejection in adr.get("rejections", []):
            if not rejection.get("rejection_reason", "").strip():
                raise ValueError(
                    f"ERROR [write_tech_stack]: ADR record '{adr.get('decision_point', '')}' "
                    f"has a rejection entry for '{rejection.get('candidate', '')}' with an empty "
                    f"rejection_reason. Every non-chosen candidate must have a non-empty rejection_reason."
                )

    artifacts_dir = _get_artifacts_dir()
    now = datetime.now(timezone.utc).isoformat()
    log_entry_input = tool_input.pop("decision_log_entry", None)

    if existing_tech_stack is None:
        slug = tool_input["slug"]
        upstream = find_latest(slug, "design", status="approved")
        if upstream is None:
            raise ValueError(
                f"ERROR [write_tech_stack]: no approved Design artifact found for slug '{slug}'. "
                f"Approve the Design artifact first, then call write_tech_stack again."
            )
        references = [str(upstream.relative_to(artifacts_dir.parent))]
        tech_stack_id = f"tech-stack-{uuid.uuid4()}"
        version = 1
        parent_version = None
        created_at = now
        prior_log = []
    else:
        slug = existing_tech_stack["slug"]  # orchestrator-enforced: agent cannot change slug
        tech_stack_id = existing_tech_stack["id"]
        version = existing_tech_stack["version"] + 1
        parent_version = existing_tech_stack["version"]
        created_at = existing_tech_stack["created_at"]
        prior_log = existing_tech_stack.get("decision_log", [])
        references = existing_tech_stack.get("references", [])

    folder = artifacts_dir / slug / "tech_stack"
    folder.mkdir(parents=True, exist_ok=True)

    if log_entry_input:
        decision_log = prior_log + [{
            "version": version,
            "timestamp": now,
            "author": "agent:tech-stack-agent",
            "trigger": log_entry_input.get("trigger", "human_feedback"),
            "summary": log_entry_input.get("summary", ""),
            "changed_fields": log_entry_input.get("changed_fields", []),
        }]
    else:
        decision_log = prior_log

    artifact = {
        "id": tech_stack_id,
        "slug": slug,
        "version": version,
        "parent_version": parent_version,
        "created_at": created_at,
        "updated_at": now,
        "status": "draft",
        "references": references,
        "decision_log": decision_log,
        "content": {k: tool_input[k] for k in _TECH_STACK_CONTENT_KEYS if k in tool_input},
    }

    path = folder / f"v{version}.json"
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_approve_tech_stack(artifact_path: str) -> dict:
    path = _validate_approve_path(artifact_path, "approve_tech_stack")
    artifact = json.loads(path.read_text())
    now = datetime.now(timezone.utc).isoformat()
    artifact["status"] = "approved"
    artifact["updated_at"] = now
    artifact.setdefault("decision_log", []).append({
        "version": artifact["version"],
        "timestamp": now,
        "author": "human",
        "trigger": "approval",
        "summary": "Tech stack artifact approved.",
        "changed_fields": ["status"],
    })
    path.write_text(json.dumps(artifact, indent=2))
    return artifact


def handle_approve_brief(artifact_path: str) -> dict:
    path = _validate_approve_path(artifact_path, "approve_brief")
    artifact = json.loads(path.read_text())
    now = datetime.now(timezone.utc).isoformat()
    artifact["status"] = "approved"
    artifact["updated_at"] = now
    artifact.setdefault("decision_log", []).append({
        "version": artifact["version"],
        "timestamp": now,
        "author": "human",
        "trigger": "approval",
        "summary": "Brief approved.",
        "changed_fields": ["status"],
    })
    path.write_text(json.dumps(artifact, indent=2))
    return artifact
