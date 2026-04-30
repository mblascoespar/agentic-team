"""
Contract tests — DAG node boundary handoffs.

Verifies that the output of stage N is correctly consumable by stage N+1.
A contract test failure means a DAG edge is broken.

Edges under test:
  brief        → prd
  prd          → model_*  (all five archetypes)
  model_domain → design
  design       → tech_stack
  get_available_artifacts — topology-aware, forward-looking
  get_work_context        — upstream + draft resolution

Run this suite alone:  pytest -m contract
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_handler import (
    handle_write_artifact,
    handle_approve_artifact,
    get_available_artifacts,
    find_latest,
    read_artifact,
    handle_get_work_context,
    _resolve_topology,
    _next_stage,
)
from conftest import (
    make_brief_body, make_prd_body, make_model_body,
    make_design_body, make_tech_stack_body,
    _create_approved_brief, _create_approved_prd, _create_approved_model, _create_approved_design,
    _write_and_approve,
)

pytestmark = pytest.mark.contract

SLUG = "test-project"


# ===========================================================================
# Brief → PRD edge
# ===========================================================================

class TestContractBriefToPrd:
    def test_prd_references_approved_brief(self, brief_artifacts_dir):
        a = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert len(a["references"]) == 1
        assert a["references"][0].endswith("test-project/brief/v1.json")

    def test_prd_slug_matches_brief_slug(self, brief_artifacts_dir):
        a = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert a["slug"] == SLUG

    def test_prd_id_independent_from_brief_id(self, brief_artifacts_dir):
        brief_path = find_latest(SLUG, "brief", status="approved")
        brief = json.loads(brief_path.read_text())
        prd = handle_write_artifact(SLUG, "prd", make_prd_body())
        assert prd["id"] != brief["id"]
        assert prd["id"].startswith("prd-")

    def test_prd_blocked_on_draft_brief(self, artifacts_dir):
        handle_write_artifact(SLUG, "brief", make_brief_body())  # draft
        with pytest.raises(ValueError, match="no approved brief"):
            handle_write_artifact(SLUG, "prd", make_prd_body())

    def test_prd_blocked_on_no_brief(self, artifacts_dir):
        with pytest.raises(ValueError, match="no approved brief"):
            handle_write_artifact(SLUG, "prd", make_prd_body())


# ===========================================================================
# PRD → Model edges (all five archetypes)
# ===========================================================================

class TestContractPrdToModel:
    @pytest.mark.parametrize("primary_archetype,model_type,stage", [
        ("domain_system",    "domain",    "model_domain"),
        ("data_pipeline",    "data_flow", "model_data_flow"),
        ("system_integration", "system", "model_system"),
        ("process_system",   "workflow",  "model_workflow"),
        ("system_evolution", "evolution", "model_evolution"),
    ])
    def test_model_references_approved_prd(self, primary_archetype, model_type, stage, artifacts_dir):
        _create_approved_brief(SLUG, artifacts_dir)
        _create_approved_prd(SLUG, artifacts_dir, primary_archetype=primary_archetype)
        a = handle_write_artifact(SLUG, stage, make_model_body(model_type))
        assert len(a["references"]) == 1
        assert "prd/v1.json" in a["references"][0]

    @pytest.mark.parametrize("primary_archetype,model_type,stage", [
        ("domain_system",    "domain",    "model_domain"),
        ("data_pipeline",    "data_flow", "model_data_flow"),
    ])
    def test_model_blocked_on_draft_prd(self, primary_archetype, model_type, stage, artifacts_dir):
        _create_approved_brief(SLUG, artifacts_dir)
        handle_write_artifact(SLUG, "prd", make_prd_body(primary_archetype=primary_archetype))
        # PRD is draft — topology cannot be resolved
        with pytest.raises(ValueError, match="cannot determine topology"):
            handle_write_artifact(SLUG, stage, make_model_body(model_type))


# ===========================================================================
# Model → Design edge
# ===========================================================================

class TestContractModelToDesign:
    def test_design_references_approved_model_domain(self, model_artifacts_dir):
        a = handle_write_artifact(SLUG, "design", make_design_body())
        assert len(a["references"]) == 1
        assert "model_domain/v1.json" in a["references"][0]

    def test_design_slug_matches_model_slug(self, model_artifacts_dir):
        a = handle_write_artifact(SLUG, "design", make_design_body())
        assert a["slug"] == SLUG

    def test_design_id_independent_from_model_id(self, model_artifacts_dir):
        model_path = find_latest(SLUG, "model_domain", status="approved")
        model = json.loads(model_path.read_text())
        design = handle_write_artifact(SLUG, "design", make_design_body())
        assert design["id"] != model["id"]
        assert design["id"].startswith("design-")

    def test_design_blocked_on_draft_model(self, prd_artifacts_dir):
        handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))  # draft
        with pytest.raises(ValueError, match="no approved model_domain"):
            handle_write_artifact(SLUG, "design", make_design_body())

    def test_design_blocked_without_model(self, prd_artifacts_dir):
        with pytest.raises(ValueError, match="no approved model_domain"):
            handle_write_artifact(SLUG, "design", make_design_body())

    @pytest.mark.parametrize("primary_archetype,model_type,model_stage", [
        ("data_pipeline",      "data_flow", "model_data_flow"),
        ("system_integration", "system",    "model_system"),
        ("system_evolution",   "evolution", "model_evolution"),
    ])
    def test_design_references_correct_model_per_archetype(
        self, primary_archetype, model_type, model_stage, artifacts_dir
    ):
        _create_approved_brief(SLUG, artifacts_dir)
        _create_approved_prd(SLUG, artifacts_dir, primary_archetype=primary_archetype)
        _write_and_approve(SLUG, model_stage, make_model_body(model_type), artifacts_dir)
        design = handle_write_artifact(SLUG, "design", make_design_body())
        assert any(model_stage in r for r in design["references"])


# ===========================================================================
# Design → Tech Stack edge
# ===========================================================================

class TestContractDesignToTechStack:
    def test_tech_stack_references_approved_design(self, design_artifacts_dir):
        a = handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())
        assert len(a["references"]) == 1
        assert "design/v1.json" in a["references"][0]

    def test_tech_stack_blocked_on_draft_design(self, model_artifacts_dir):
        handle_write_artifact(SLUG, "design", make_design_body())  # draft
        with pytest.raises(ValueError, match="no approved design"):
            handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())

    def test_tech_stack_blocked_without_design(self, model_artifacts_dir):
        with pytest.raises(ValueError, match="no approved design"):
            handle_write_artifact(SLUG, "tech_stack", make_tech_stack_body())


# ===========================================================================
# Topology resolution
# ===========================================================================

class TestTopologyResolution:
    @pytest.mark.parametrize("primary_archetype,expected_model_stage", [
        ("domain_system",    "model_domain"),
        ("data_pipeline",    "model_data_flow"),
        ("system_integration", "model_system"),
        ("process_system",   "model_workflow"),
        ("system_evolution", "model_evolution"),
    ])
    def test_topology_per_archetype(self, primary_archetype, expected_model_stage, artifacts_dir):
        _create_approved_brief(SLUG, artifacts_dir)
        _create_approved_prd(SLUG, artifacts_dir, primary_archetype=primary_archetype)
        topology = _resolve_topology(SLUG)
        assert expected_model_stage in topology

    def test_topology_none_without_approved_prd(self, brief_artifacts_dir):
        assert _resolve_topology(SLUG) is None

    def test_topology_layered_includes_both_models(self, artifacts_dir):
        _create_approved_brief(SLUG, artifacts_dir)
        handle_write_artifact(SLUG, "prd", make_prd_body(
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_artifact(str(artifacts_dir / SLUG / "prd" / "v1.json"))
        topology = _resolve_topology(SLUG)
        assert "model_system" in topology
        assert "model_workflow" in topology
        assert topology.index("model_workflow") < topology.index("model_system")


# ===========================================================================
# _next_stage
# ===========================================================================

class TestNextStage:
    def test_returns_prd_after_approved_brief(self, artifacts_dir):
        _create_approved_brief(SLUG, artifacts_dir)
        assert _next_stage(SLUG) == "prd"

    def test_returns_none_without_approved_brief(self, artifacts_dir):
        assert _next_stage(SLUG) is None

    def test_returns_none_with_in_progress_prd(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())  # draft
        assert _next_stage(SLUG) is None

    def test_returns_model_stage_after_approved_prd(self, prd_artifacts_dir):
        assert _next_stage(SLUG) == "model_domain"

    def test_returns_design_after_approved_model(self, model_artifacts_dir):
        assert _next_stage(SLUG) == "design"

    def test_returns_tech_stack_after_approved_design(self, design_artifacts_dir):
        assert _next_stage(SLUG) == "tech_stack"

    def test_returns_none_after_full_pipeline(self, tech_stack_artifacts_dir):
        # tech_stack_artifacts_dir already has approved tech_stack — all stages approved
        assert _next_stage(SLUG) is None


# ===========================================================================
# get_available_artifacts
# ===========================================================================

class TestGetAvailableArtifacts:
    def test_in_progress_bucket(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        result = get_available_artifacts("prd")
        slugs = [item["slug"] for item in result["in_progress"]]
        assert SLUG in slugs

    def test_ready_to_start_bucket(self, prd_artifacts_dir):
        result = get_available_artifacts("model_domain")
        slugs = [item["slug"] for item in result["ready_to_start"]]
        assert SLUG in slugs

    def test_approved_bucket(self, model_artifacts_dir):
        result = get_available_artifacts("model_domain")
        slugs = [item["slug"] for item in result["approved"]]
        assert SLUG in slugs

    def test_ready_to_start_absent_for_mismatched_archetype(self, artifacts_dir):
        # data_pipeline PRD → model_domain should not appear as ready_to_start
        _create_approved_brief(SLUG, artifacts_dir)
        _create_approved_prd(SLUG, artifacts_dir, primary_archetype="data_pipeline")
        result = get_available_artifacts("model_domain")
        ready_slugs = [item["slug"] for item in result["ready_to_start"]]
        assert SLUG not in ready_slugs


# ===========================================================================
# get_work_context
# ===========================================================================

class TestGetWorkContext:
    def test_returns_upstream_and_null_draft_for_ready_slug(self, prd_artifacts_dir):
        result = handle_get_work_context(SLUG, "model_domain")
        assert result["upstream"]["artifact"]["slug"] == SLUG
        assert result["upstream"]["artifact"]["status"] == "approved"
        assert result["current_draft"] is None

    def test_returns_upstream_and_draft_for_in_progress_slug(self, prd_artifacts_dir):
        handle_write_artifact(SLUG, "model_domain", make_model_body("domain"))
        result = handle_get_work_context(SLUG, "model_domain")
        assert result["current_draft"] is not None
        assert result["current_draft"]["artifact"]["status"] == "draft"

    def test_upstream_not_approved_raises(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())  # draft PRD
        with pytest.raises(ValueError, match="cannot determine topology"):
            handle_get_work_context(SLUG, "model_domain")

    def test_stage_not_in_topology_raises(self, prd_artifacts_dir):
        # model_data_flow not in domain_system topology
        with pytest.raises(ValueError, match="not in the topology"):
            handle_get_work_context(SLUG, "model_data_flow")

    def test_no_approved_prd_raises(self, brief_artifacts_dir):
        with pytest.raises(ValueError, match="cannot determine topology"):
            handle_get_work_context(SLUG, "model_domain")

    def test_read_artifact_includes_schema(self, brief_artifacts_dir):
        handle_write_artifact(SLUG, "prd", make_prd_body())
        result = read_artifact(SLUG, "prd")
        assert "artifact" in result
        assert "schema" in result
