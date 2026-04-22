"""
Lifecycle tests — correct versioning behavior through the v1 / v2 / approve chain.

Tests verify that handle_write_artifact and handle_approve_artifact produce the
correct structure at each stage of an artifact's life: initial creation, iterative
refinement, and approval. Also covers instance schema creation and schema CRUD.

Run this suite alone:  pytest -m lifecycle
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
    _create_approved_brief, _create_approved_prd, _create_approved_model,
)

pytestmark = pytest.mark.lifecycle

SLUG = "test-project"


# ===========================================================================
# Brief — v1
# ===========================================================================

class TestBriefV1:
    def test_id_has_brief_prefix(self, artifacts_dir):
        a = handle_write_artifact(SLUG, "brief", make_brief_body())
        assert a["id"].startswith("brief-")

    def test_version_is_1(self, artifacts_dir):
        assert handle_write_artifact(SLUG, "brief", make_brief_body())["version"] == 1

    def test_parent_version_is_none(self, artifacts_dir):
        assert handle_write_artifact(SLUG, "brief", make_brief_body())["parent_version"] is None

    def test_timestamps_set(self, artifacts_dir):
        a = handle_write_artifact(SLUG, "brief", make_brief_body())
        assert a["created_at"] and a["updated_at"]

    def test_status_is_draft(self, artifacts_dir):
        assert handle_write_artifact(SLUG, "brief", make_brief_body())["status"] == "draft"

    def test_references_empty(self, artifacts_dir):
        assert handle_write_artifact(SLUG, "brief", make_brief_body())["references"] == []

    def test_decision_log_empty_without_entry(self, artifacts_dir):
        assert handle_write_artifact(SLUG, "brief", make_brief_body())["decision_log"] == []

    def test_decision_log_entry_appended(self, artifacts_dir):
        a = handle_write_artifact(SLUG, "brief", make_brief_body(), decision_log_entry={
            "trigger": "initial_draft", "summary": "First brief", "changed_fields": ["idea"],
        })
        assert len(a["decision_log"]) == 1
        entry = a["decision_log"][0]
        assert entry["version"] == 1
        assert entry["author"] == "agent:brainstorm-agent"
        assert entry["trigger"] == "initial_draft"

    def test_content_stored(self, artifacts_dir):
        body = make_brief_body()
        a = handle_write_artifact(SLUG, "brief", body)
        assert a["content"]["idea"] == body["idea"]

    def test_schema_created_on_v1(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        assert (artifacts_dir / SLUG / "brief" / "schema.json").exists()

    def test_written_to_disk(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        assert (artifacts_dir / SLUG / "brief" / "v1.json").exists()

    def test_no_primary_archetype_on_brief(self, artifacts_dir):
        a = handle_write_artifact(SLUG, "brief", make_brief_body())
        assert "primary_archetype" not in a


# ===========================================================================
# Brief — v2
# ===========================================================================

class TestBriefV2:
    def test_version_increments(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        v2 = handle_write_artifact(SLUG, "brief", make_brief_body())
        assert v2["version"] == 2

    def test_parent_version_set(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        v2 = handle_write_artifact(SLUG, "brief", make_brief_body())
        assert v2["parent_version"] == 1

    def test_id_stable_across_versions(self, artifacts_dir):
        v1 = handle_write_artifact(SLUG, "brief", make_brief_body())
        v2 = handle_write_artifact(SLUG, "brief", make_brief_body())
        assert v1["id"] == v2["id"]

    def test_created_at_immutable(self, artifacts_dir):
        v1 = handle_write_artifact(SLUG, "brief", make_brief_body())
        v2 = handle_write_artifact(SLUG, "brief", make_brief_body())
        assert v1["created_at"] == v2["created_at"]

    def test_idea_locked_on_v2(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body(idea="original idea"))
        v2 = handle_write_artifact(SLUG, "brief", make_brief_body(idea="attacker idea"))
        assert v2["content"]["idea"] == "original idea"

    def test_decision_log_accumulates(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body(), decision_log_entry={"trigger": "t1", "summary": "s1", "changed_fields": []})
        v2 = handle_write_artifact(SLUG, "brief", make_brief_body(), decision_log_entry={"trigger": "t2", "summary": "s2", "changed_fields": []})
        assert len(v2["decision_log"]) == 2

    def test_v2_written_to_disk(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        handle_write_artifact(SLUG, "brief", make_brief_body())
        assert (artifacts_dir / SLUG / "brief" / "v2.json").exists()


# ===========================================================================
# Brief — approve
# ===========================================================================

class TestApproveBrief:
    def test_status_becomes_approved(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        artifact = handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v1.json"))
        assert artifact["status"] == "approved"

    def test_approval_log_entry_appended(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        artifact = handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v1.json"))
        entry = artifact["decision_log"][-1]
        assert entry["trigger"] == "approval"
        assert entry["author"] == "human"

    def test_double_approve_raises(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())
        handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v1.json"))
        with pytest.raises(ValueError, match="already approved"):
            handle_approve_artifact(str(artifacts_dir / SLUG / "brief" / "v1.json"))


# ===========================================================================
# PRD — v1
# ===========================================================================

class TestPrdV1:
    def test_id_has_prd_prefix(self, brief_artifacts_dir):
        assert handle_write_artifact(SLUG, "prd", make_prd_body())["id"].startswith("prd-")

    def test_version_is_1(self, brief_artifacts_dir):
        assert handle_write_artifact(SLUG, "prd", make_prd_body())["version"] == 1

    def test_references_upstream_brief(self, brief_artifacts_dir):
        a = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert len(a["references"]) == 1
        assert "brief/v1.json" in a["references"][0]

    def test_source_idea_derived_from_brief(self, brief_artifacts_dir):
        a = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert a["source_idea"] == make_brief_body()["idea"]

    def test_primary_archetype_on_envelope(self, brief_artifacts_dir):
        # PRD is v1 before archetype is in approved PRD — archetype read from own content
        # after approval; at write time there's no approved PRD yet so field is absent
        a = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert "primary_archetype" not in a  # no approved PRD yet at write time

    def test_schema_created_on_v1(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        assert (brief_artifacts_dir / SLUG / "prd" / "schema.json").exists()

    def test_content_stored(self, brief_artifacts_dir):
        body = make_prd_body()
        a = handle_write_artifact(SLUG, "prd", body)
        assert a["content"]["title"] == body["title"]
        assert a["content"]["primary_archetype"] == "domain_system"

    def test_written_to_disk(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        assert (brief_artifacts_dir / SLUG / "prd" / "v1.json").exists()

    def test_no_upstream_brief_raises(self, artifacts_dir):
        with pytest.raises(ValueError, match="no approved brief"):
            handle_write_artifact(SLUG, "prd", make_prd_body())


# ===========================================================================
# PRD — v2 (archetype locking)
# ===========================================================================

class TestPrdV2:
    def test_version_increments(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        v2 = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert v2["version"] == 2

    def test_archetype_locked_on_v2(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype="domain_system"))
        # Attempt to change archetype on v2 — engine must ignore it
        v2 = handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype="data_pipeline"))
        assert v2["content"]["primary_archetype"] == "domain_system"

    def test_archetype_reasoning_locked_on_v2(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body(archetype_reasoning="original reasoning"))
        v2 = handle_write_artifact(SLUG, "prd", make_prd_body(archetype_reasoning="attacker reasoning"))
        assert v2["content"]["archetype_reasoning"] == "original reasoning"

    def test_id_stable(self, brief_artifacts_dir):
        v1 = handle_write_artifact(SLUG, "prd", make_prd_body())
        v2 = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert v1["id"] == v2["id"]

    def test_source_idea_carried_forward(self, brief_artifacts_dir):
        v1 = handle_write_artifact(SLUG, "prd", make_prd_body())
        v2 = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert v1["source_idea"] == v2["source_idea"]

    def test_decision_log_accumulates(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body(), decision_log_entry={"trigger": "t1", "summary": "s1", "changed_fields": []})
        v2 = handle_write_artifact(SLUG, "prd", make_prd_body(), decision_log_entry={"trigger": "t2", "summary": "s2", "changed_fields": []})
        assert len(v2["decision_log"]) == 2


# ===========================================================================
# PRD — approve
# ===========================================================================

class TestApprovePrd:
    def test_status_becomes_approved(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        artifact = handle_approve_artifact(str(brief_artifacts_dir / SLUG / "prd" / "v1.json"))
        assert artifact["status"] == "approved"

    def test_approval_log_entry(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        artifact = handle_approve_artifact(str(brief_artifacts_dir / SLUG / "prd" / "v1.json"))
        assert artifact["decision_log"][-1]["trigger"] == "approval"

    def test_double_approve_raises(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        handle_approve_artifact(str(brief_artifacts_dir / SLUG / "prd" / "v1.json"))
        with pytest.raises(ValueError, match="already approved"):
            handle_approve_artifact(str(brief_artifacts_dir / SLUG / "prd" / "v1.json"))


# ===========================================================================
# Model stages — v1 / v2 / approve (domain as representative)
# ===========================================================================

class TestModelDomainV1:
    def test_id_has_model_domain_prefix(self, prd_artifacts_dir):
        a = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        assert a["id"].startswith("model-domain-")

    def test_model_type_on_envelope(self, prd_artifacts_dir):
        a = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        assert a["model_type"] == "domain"

    def test_primary_archetype_on_envelope(self, prd_artifacts_dir):
        a = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        assert a["primary_archetype"] == "domain_system"

    def test_references_approved_prd(self, prd_artifacts_dir):
        a = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        assert any("prd/v1.json" in r for r in a["references"])

    def test_schema_created(self, prd_artifacts_dir):
        handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        assert (prd_artifacts_dir / SLUG / "model_domain" / "schema.json").exists()

    def test_no_approved_prd_raises(self, brief_artifacts_dir):
        # brief exists but PRD is draft — topology unresolvable
        handle_write_artifact(SLUG, "prd", make_prd_body())
        with pytest.raises(ValueError, match="cannot determine topology"):
            handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))

    def test_wrong_archetype_raises(self, artifacts_dir):
        # data_pipeline PRD → model_domain not in topology
        _create_approved_brief(SLUG, artifacts_dir)
        handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype="data_pipeline"))
        handle_approve_artifact(str(artifacts_dir / SLUG / "prd" / "v1.json"))
        with pytest.raises(ValueError, match="not in the topology"):
            handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))


class TestModelDomainV2:
    def test_version_increments(self, prd_artifacts_dir):
        handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        v2 = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        assert v2["version"] == 2

    def test_id_stable(self, prd_artifacts_dir):
        v1 = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        v2 = handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        assert v1["id"] == v2["id"]


class TestApproveModel:
    def test_status_becomes_approved(self, prd_artifacts_dir):
        handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        artifact = handle_approve_artifact(str(prd_artifacts_dir / SLUG / "model_domain" / "v1.json"))
        assert artifact["status"] == "approved"

    def test_missing_mandatory_field_rejects(self, prd_artifacts_dir):
        handle_write_artifact(SLUG, "model_domain", {})  # no content
        # schema has mandatory fields — approve should fail
        schema_path = prd_artifacts_dir / SLUG / "model_domain" / "schema.json"
        schema = json.loads(schema_path.read_text())
        if not any(f["kind"] == "mandatory" for f in schema.get("fields", {}).values()):
            pytest.skip("no mandatory fields in base schema")
        with pytest.raises(ValueError, match="missing mandatory fields"):
            handle_approve_artifact(str(prd_artifacts_dir / SLUG / "model_domain" / "v1.json"))


# ===========================================================================
# Model — all five types have correct model_type and topology routing
# ===========================================================================

@pytest.mark.parametrize("primary_archetype,model_type,stage", [
    ("domain_system",    "domain",    "model_domain"),
    ("data_pipeline",    "data_flow", "model_data_flow"),
    ("system_integration", "system", "model_system"),
    ("process_system",   "workflow",  "model_workflow"),
    ("system_evolution", "evolution", "model_evolution"),
])
def test_model_type_routing(primary_archetype, model_type, stage, artifacts_dir):
    _create_approved_brief(SLUG, artifacts_dir)
    handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype=primary_archetype))
    handle_approve_artifact(str(artifacts_dir / SLUG / "prd" / "v1.json"))
    a = handle_write_artifact(SLUG, stage, make_model_body(model_type))
    assert a["model_type"] == model_type
    assert a["primary_archetype"] == primary_archetype
    assert a["id"].startswith(stage.replace("_", "-"))


# ===========================================================================
# Layered topology: system_integration + process_system
# ===========================================================================

class TestLayeredModelChain:
    def test_model_workflow_references_model_system(self, artifacts_dir):
        _create_approved_brief(SLUG, artifacts_dir)
        handle_write_artifact(SLUG, "prd", make_prd_body(
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_artifact(str(artifacts_dir / SLUG / "prd" / "v1.json"))

        handle_write_artifact(SLUG, "model_system", make_model_body("system"))
        handle_approve_artifact(str(artifacts_dir / SLUG / "model_system" / "v1.json"))

        wf = handle_write_artifact(SLUG, "model_workflow", make_model_body("workflow"))
        assert any("model_system" in r for r in wf["references"])

    def test_model_workflow_blocked_until_model_system_approved(self, artifacts_dir):
        _create_approved_brief(SLUG, artifacts_dir)
        handle_write_artifact(SLUG, "prd", make_prd_body(
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_artifact(str(artifacts_dir / SLUG / "prd" / "v1.json"))
        handle_write_artifact(SLUG, "model_system", make_model_body("system"))
        # model_system is draft (not approved) — model_workflow should fail
        with pytest.raises(ValueError, match="no approved model_system"):
            handle_write_artifact(SLUG, "model_workflow", make_model_body("workflow"))


# ===========================================================================
# Design — v1 / v2 / approve
# ===========================================================================

class TestDesignV1:
    def test_id_has_design_prefix(self, model_artifacts_dir):
        a = handle_write_artifact(SLUG, "design", make_design_body())
        assert a["id"].startswith("design-")

    def test_primary_archetype_on_envelope(self, model_artifacts_dir):
        a = handle_write_artifact(SLUG, "design", make_design_body())
        assert a["primary_archetype"] == "domain_system"

    def test_references_approved_model(self, model_artifacts_dir):
        a = handle_write_artifact(SLUG, "design", make_design_body())
        assert any("model_domain" in r for r in a["references"])

    def test_schema_initialised_with_archetype_base(self, model_artifacts_dir):
        handle_write_artifact(SLUG, "design", make_design_body())
        schema = json.loads((model_artifacts_dir / SLUG / "design" / "schema.json").read_text())
        # domain_system schema has layering_strategy as mandatory
        assert "layering_strategy" in schema.get("fields", {})

    def test_no_approved_model_raises(self, prd_artifacts_dir):
        with pytest.raises(ValueError, match="no approved model_domain"):
            handle_write_artifact(SLUG, "design", make_design_body())


class TestDesignV2:
    def test_version_increments(self, model_artifacts_dir):
        handle_write_artifact(SLUG, "design", make_design_body())
        v2 = handle_write_artifact(SLUG, "design", make_design_body())
        assert v2["version"] == 2

    def test_id_stable(self, model_artifacts_dir):
        v1 = handle_write_artifact(SLUG, "design", make_design_body())
        v2 = handle_write_artifact(SLUG, "design", make_design_body())
        assert v1["id"] == v2["id"]


class TestApproveDesign:
    def test_status_becomes_approved(self, model_artifacts_dir):
        handle_write_artifact(SLUG, "design", make_design_body())
        artifact = handle_approve_artifact(str(model_artifacts_dir / SLUG / "design" / "v1.json"))
        assert artifact["status"] == "approved"


# ===========================================================================
# Tech Stack — v1 / approve
# ===========================================================================

class TestTechStackV1:
    def test_id_has_tech_stack_prefix(self, design_artifacts_dir):
        a = handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())
        assert a["id"].startswith("tech-stack-")

    def test_primary_archetype_on_envelope(self, design_artifacts_dir):
        a = handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())
        assert a["primary_archetype"] == "domain_system"

    def test_references_approved_design(self, design_artifacts_dir):
        a = handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())
        assert any("design/v1.json" in r for r in a["references"])

    def test_no_approved_design_raises(self, model_artifacts_dir):
        with pytest.raises(ValueError, match="no approved design"):
            handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())


class TestApproveTechStack:
    def test_status_becomes_approved(self, design_artifacts_dir):
        handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())
        artifact = handle_approve_artifact(str(design_artifacts_dir / SLUG / "tech_stack" / "v1.json"))
        assert artifact["status"] == "approved"


# ===========================================================================
# Instance schema — creation and CRUD across stages
# ===========================================================================

class TestInstanceSchemaCreation:
    @pytest.mark.parametrize("stage,fixture", [
        ("brief", "artifacts_dir"),
    ])
    def test_schema_created_on_first_write(self, stage, fixture, request):
        dir_ = request.getfixturevalue(fixture)
        handle_write_artifact(SLUG, stage, make_brief_body())
        assert (dir_ / SLUG / stage / "schema.json").exists()

    def test_prd_schema_created(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        assert (brief_artifacts_dir / SLUG / "prd" / "schema.json").exists()

    def test_design_schema_has_archetype_fields(self, model_artifacts_dir):
        handle_write_artifact(SLUG, "design", make_design_body())
        schema = json.loads((model_artifacts_dir / SLUG / "design" / "schema.json").read_text())
        assert "layering_strategy" in schema["fields"]

    def test_schema_not_overwritten_on_v2(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        handle_add_schema_field(SLUG, "prd", "custom_field", "optional", "A custom field")
        handle_write_artifact(SLUG, "prd", make_prd_body())
        schema = json.loads((brief_artifacts_dir / SLUG / "prd" / "schema.json").read_text())
        assert "custom_field" in schema["fields"]


class TestSchemaCRUD:
    def test_add_field(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        schema = handle_add_schema_field(SLUG, "prd", "risks", "mandatory", "Risk list")
        assert "risks" in schema["fields"]
        assert schema["fields"]["risks"]["kind"] == "mandatory"

    def test_add_duplicate_field_raises(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        handle_add_schema_field(SLUG, "prd", "risks", "optional", "Risk list")
        with pytest.raises(ValueError, match="already exists"):
            handle_add_schema_field(SLUG, "prd", "risks", "optional", "Risk list")

    def test_update_field_kind(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        handle_add_schema_field(SLUG, "prd", "risks", "optional", "Risk list")
        schema = handle_update_schema_field(SLUG, "prd", "risks", kind="mandatory")
        assert schema["fields"]["risks"]["kind"] == "mandatory"

    def test_rename_clears_old_key_from_draft(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body(old_key="value"))
        handle_add_schema_field(SLUG, "prd", "old_key", "optional", "Old field")
        handle_update_schema_field(SLUG, "prd", "old_key", new_field_name="new_key")
        draft_path = brief_artifacts_dir / SLUG / "prd" / "v1.json"
        content = json.loads(draft_path.read_text())["content"]
        assert "old_key" not in content

    def test_delete_field(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        handle_add_schema_field(SLUG, "prd", "temp_field", "optional", "Temp")
        schema = handle_delete_schema_field(SLUG, "prd", "temp_field", "No longer needed")
        assert "temp_field" not in schema["fields"]

    def test_schema_decision_log_records_add(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        schema = handle_add_schema_field(SLUG, "prd", "risks", "optional", "Risk list")
        assert any(e["trigger"] == "schema_field_added" for e in schema.get("decision_log", []))

    def test_schema_decision_log_records_delete(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        handle_add_schema_field(SLUG, "prd", "temp_field", "optional", "Temp")
        schema = handle_delete_schema_field(SLUG, "prd", "temp_field", "cleanup")
        assert any(e["trigger"] == "schema_field_deleted" for e in schema.get("decision_log", []))


# ===========================================================================
# Unknown stage rejection
# ===========================================================================

def test_unknown_stage_raises(artifacts_dir):
    with pytest.raises(ValueError, match="unknown stage"):
        handle_write_artifact(SLUG, "nonexistent_stage", {})
