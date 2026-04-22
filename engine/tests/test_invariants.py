"""
Invariant tests — engine-owned field enforcement and input validation.

Categories:
1. Field ownership: engine controls id, slug, created_at, source_idea (prd),
   references, status, model_type, primary_archetype.
2. Locked fields: archetype fields (prd v2+), idea (brief v2+).
3. Input validation: invalid slugs, unknown stages, upstream gate enforcement.

Run this suite alone:  pytest -m invariant
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_handler import (
    handle_write_artifact,
    handle_approve_artifact,
    handle_add_schema_field,
    handle_update_schema_field,
    handle_delete_schema_field,
    _init_schema,
    _validate_mandatory_fields,
)
from conftest import (
    make_brief_body, make_prd_body, make_model_body,
    make_design_body, make_tech_stack_body,
    _create_approved_brief, _create_approved_prd, _create_approved_model, _create_approved_design,
)

pytestmark = pytest.mark.invariant

SLUG = "test-project"


# ---------------------------------------------------------------------------
# Slug immutability
# ---------------------------------------------------------------------------

def test_slug_stable_across_prd_versions(brief_artifacts_dir):
    v1 = handle_write_artifact("original-slug", "prd", make_prd_body())
    v2 = handle_write_artifact("original-slug", "prd", make_prd_body())
    assert v1["slug"] == v2["slug"] == "original-slug"


def test_v2_written_to_correct_folder(brief_artifacts_dir):
    handle_write_artifact("original-slug", "prd", make_prd_body())
    handle_write_artifact("original-slug", "prd", make_prd_body())
    assert (brief_artifacts_dir / "original-slug" / "prd" / "v2.json").exists()


# ---------------------------------------------------------------------------
# id immutability
# ---------------------------------------------------------------------------

def test_id_stable_across_prd_versions(brief_artifacts_dir):
    v1 = handle_write_artifact(SLUG, "prd", make_prd_body())
    v2 = handle_write_artifact(SLUG, "prd", make_prd_body())
    assert v1["id"] == v2["id"]


def test_id_stable_across_brief_versions(artifacts_dir):
    v1 = handle_write_artifact(SLUG, "brief", make_brief_body())
    v2 = handle_write_artifact(SLUG, "brief", make_brief_body())
    assert v1["id"] == v2["id"]


def test_id_stable_across_model_versions(prd_artifacts_dir):
    v1 = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
    v2 = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
    assert v1["id"] == v2["id"]


# ---------------------------------------------------------------------------
# created_at immutability
# ---------------------------------------------------------------------------

def test_prd_created_at_immutable(brief_artifacts_dir):
    v1 = handle_write_artifact(SLUG, "prd", make_prd_body())
    v2 = handle_write_artifact(SLUG, "prd", make_prd_body())
    assert v1["created_at"] == v2["created_at"]


def test_brief_created_at_immutable(artifacts_dir):
    v1 = handle_write_artifact(SLUG, "brief", make_brief_body())
    v2 = handle_write_artifact(SLUG, "brief", make_brief_body())
    assert v1["created_at"] == v2["created_at"]


# ---------------------------------------------------------------------------
# source_idea carried forward (PRD)
# ---------------------------------------------------------------------------

def test_source_idea_stable_across_prd_versions(brief_artifacts_dir):
    v1 = handle_write_artifact(SLUG, "prd", make_prd_body())
    v2 = handle_write_artifact(SLUG, "prd", make_prd_body())
    assert v1["source_idea"] == v2["source_idea"]
    assert v1["source_idea"] == make_brief_body()["idea"]


# ---------------------------------------------------------------------------
# references immutability
# ---------------------------------------------------------------------------

def test_prd_references_unchanged_on_v2(brief_artifacts_dir):
    v1 = handle_write_artifact(SLUG, "prd", make_prd_body())
    v2 = handle_write_artifact(SLUG, "prd", make_prd_body())
    assert v1["references"] == v2["references"]


def test_model_references_unchanged_on_v2(prd_artifacts_dir):
    v1 = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
    v2 = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
    assert v1["references"] == v2["references"]


# ---------------------------------------------------------------------------
# status always starts as draft
# ---------------------------------------------------------------------------

def test_brief_status_is_draft(artifacts_dir):
    assert handle_write_artifact(SLUG, "brief", make_brief_body())["status"] == "draft"


def test_prd_status_is_draft(brief_artifacts_dir):
    assert handle_write_artifact(SLUG, "prd", make_prd_body())["status"] == "draft"


def test_model_status_is_draft(prd_artifacts_dir):
    assert handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))["status"] == "draft"


# ---------------------------------------------------------------------------
# model_type derived from stage (engine-owned, not agent-supplied)
# ---------------------------------------------------------------------------

def test_model_type_derived_for_domain(prd_artifacts_dir):
    a = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
    assert a["model_type"] == "domain"


def test_model_type_derived_for_data_flow(artifacts_dir):
    _create_approved_brief(SLUG, artifacts_dir)
    handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype="data_pipeline"))
    handle_approve_artifact(str(artifacts_dir / SLUG / "prd" / "v1.json"))
    a = handle_write_artifact(SLUG, "model_data_flow", make_model_body("data_flow"))
    assert a["model_type"] == "data_flow"


def test_model_type_derived_for_evolution(artifacts_dir):
    _create_approved_brief(SLUG, artifacts_dir)
    handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype="system_evolution"))
    handle_approve_artifact(str(artifacts_dir / SLUG / "prd" / "v1.json"))
    a = handle_write_artifact(SLUG, "model_evolution", make_model_body("evolution"))
    assert a["model_type"] == "evolution"


# ---------------------------------------------------------------------------
# primary_archetype stamped on non-brief artifacts
# ---------------------------------------------------------------------------

def test_primary_archetype_on_model_domain(prd_artifacts_dir):
    a = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
    assert a["primary_archetype"] == "domain_system"


def test_primary_archetype_on_design(model_artifacts_dir):
    a = handle_write_artifact(SLUG, "design", make_design_body())
    assert a["primary_archetype"] == "domain_system"


def test_primary_archetype_on_tech_stack(design_artifacts_dir):
    a = handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())
    assert a["primary_archetype"] == "domain_system"


def test_no_primary_archetype_on_brief(artifacts_dir):
    a = handle_write_artifact(SLUG, "brief", make_brief_body())
    assert "primary_archetype" not in a


# ---------------------------------------------------------------------------
# Locked fields — PRD archetype fields locked on v2+
# ---------------------------------------------------------------------------

def test_prd_primary_archetype_locked(brief_artifacts_dir):
    handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype="domain_system"))
    v2 = handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype="data_pipeline"))
    assert v2["content"]["primary_archetype"] == "domain_system"


def test_prd_secondary_archetype_locked(brief_artifacts_dir):
    handle_write_artifact(SLUG, "prd", make_prd_body(
        primary_archetype="system_integration",
        secondary_archetype="process_system",
    ))
    v2 = handle_write_artifact(SLUG, "prd", make_prd_body(
        primary_archetype="system_integration",
        secondary_archetype=None,
    ))
    assert v2["content"].get("secondary_archetype") == "process_system"


def test_prd_archetype_reasoning_locked(brief_artifacts_dir):
    handle_write_artifact(SLUG, "prd", make_prd_body(archetype_reasoning="original reasoning"))
    v2 = handle_write_artifact(SLUG, "prd", make_prd_body(archetype_reasoning="changed reasoning"))
    assert v2["content"]["archetype_reasoning"] == "original reasoning"


# ---------------------------------------------------------------------------
# Locked fields — Brief idea locked on v2+
# ---------------------------------------------------------------------------

def test_brief_idea_locked_on_v2(artifacts_dir):
    handle_write_artifact(SLUG, "brief", make_brief_body(idea="original idea"))
    v2 = handle_write_artifact(SLUG, "brief", make_brief_body(idea="new idea"))
    assert v2["content"]["idea"] == "original idea"


# ---------------------------------------------------------------------------
# Slug format validation
# ---------------------------------------------------------------------------

def test_invalid_slug_raises(artifacts_dir):
    with pytest.raises(ValueError, match="invalid"):
        handle_write_artifact("UPPER_CASE", "brief", make_brief_body())


def test_slug_with_spaces_raises(artifacts_dir):
    with pytest.raises(ValueError, match="invalid"):
        handle_write_artifact("my project", "brief", make_brief_body())


def test_slug_starting_with_hyphen_raises(artifacts_dir):
    with pytest.raises(ValueError, match="invalid"):
        handle_write_artifact("-bad-slug", "brief", make_brief_body())


# ---------------------------------------------------------------------------
# Unknown stage
# ---------------------------------------------------------------------------

def test_unknown_stage_raises(artifacts_dir):
    with pytest.raises(ValueError, match="unknown stage"):
        handle_write_artifact(SLUG, "nonexistent", {})


# ---------------------------------------------------------------------------
# Approve path validation
# ---------------------------------------------------------------------------

def test_approve_nonexistent_path_raises(artifacts_dir):
    with pytest.raises(ValueError, match="artifact not found"):
        handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v99.json"))


def test_approve_outside_artifacts_dir_raises(artifacts_dir):
    with pytest.raises(ValueError, match="outside the artifacts directory"):
        handle_approve_artifact("/etc/passwd")


def test_approve_already_approved_raises(artifacts_dir):
    handle_write_artifact(SLUG, "brief", make_brief_body())
    handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v1.json"))
    with pytest.raises(ValueError, match="already approved"):
        handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v1.json"))


# ---------------------------------------------------------------------------
# Upstream gate enforcement
# ---------------------------------------------------------------------------

def test_prd_blocked_without_approved_brief(artifacts_dir):
    with pytest.raises(ValueError, match="no approved brief"):
        handle_write_artifact(SLUG, "prd", make_prd_body())


def test_model_blocked_without_approved_prd(brief_artifacts_dir):
    handle_write_artifact(SLUG, "prd", make_prd_body())  # draft — topology unresolvable
    with pytest.raises(ValueError, match="cannot determine topology"):
        handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))


def test_design_blocked_without_approved_model(prd_artifacts_dir):
    with pytest.raises(ValueError, match="no approved model_domain"):
        handle_write_artifact(SLUG, "design", make_design_body())


def test_tech_stack_blocked_without_approved_design(model_artifacts_dir):
    with pytest.raises(ValueError, match="no approved design"):
        handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())


# ---------------------------------------------------------------------------
# Schema invariants — add/update/delete
# ---------------------------------------------------------------------------

def test_add_field_requires_stage_written(artifacts_dir):
    with pytest.raises(ValueError, match="no schema found"):
        handle_add_schema_field(SLUG, "brief", "new_field", "optional", "A field")


def test_add_field_rejects_empty_field_name(brief_artifacts_dir):
    handle_write_artifact(SLUG, "prd", make_prd_body())
    with pytest.raises(ValueError, match="field_name must not be empty"):
        handle_add_schema_field(SLUG, "prd", "", "optional", "desc")


def test_update_nonexistent_field_raises(brief_artifacts_dir):
    handle_write_artifact(SLUG, "prd", make_prd_body())
    with pytest.raises(ValueError, match="does not exist"):
        handle_update_schema_field(SLUG, "prd", "ghost_field", kind="mandatory")


def test_delete_nonexistent_field_raises(brief_artifacts_dir):
    handle_write_artifact(SLUG, "prd", make_prd_body())
    with pytest.raises(ValueError, match="does not exist"):
        handle_delete_schema_field(SLUG, "prd", "ghost_field", "cleanup")


def test_delete_requires_justification(brief_artifacts_dir):
    handle_write_artifact(SLUG, "prd", make_prd_body())
    handle_add_schema_field(SLUG, "prd", "temp_field", "optional", "Temp")
    with pytest.raises(ValueError, match="justification must not be empty"):
        handle_delete_schema_field(SLUG, "prd", "temp_field", "")


# ---------------------------------------------------------------------------
# Mandatory field validation at approval
# ---------------------------------------------------------------------------

class TestMandatoryFieldValidation:
    def test_missing_mandatory_field_blocks_approval(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        handle_add_schema_field(SLUG, "brief", "required_field", "mandatory", "Must have")
        with pytest.raises(ValueError, match="missing mandatory fields"):
            handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v1.json"))

    def test_present_mandatory_field_allows_approval(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        handle_add_schema_field(SLUG, "brief", "required_field", "mandatory", "Must have")
        handle_write_artifact(SLUG, "brief", make_brief_body(required_field="present"))
        artifact = handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v2.json"))
        assert artifact["status"] == "approved"

    def test_optional_field_absence_allows_approval(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        handle_add_schema_field(SLUG, "brief", "optional_field", "optional", "Nice to have")
        # no optional_field in body — should still approve
        artifact = handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v1.json"))
        assert artifact["status"] == "approved"
