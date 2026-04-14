"""
Contract tests — DAG node boundary handoffs.

These tests verify that the output of node N is correctly consumable by
node N+1. A contract test failure means a DAG edge is broken: the producing
node writes something the consuming node cannot correctly interpret.

Also tests that the engine enforces the handoff contract: the domain agent
cannot start from an unapproved PRD or a slug with no PRD.

Current edges under test:
  Brief   → PRD          (Brainstormer → Product Agent)
  PRD     → Domain Model (Product Agent → Domain Agent)

As new nodes are implemented, add one test class per new edge:
  Domain Model → Architecture  (Domain Agent → Architecture Agent)
  Architecture → Execution      (Architecture Agent → Execution Agent)

Run this suite alone:  pytest -m contract
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_handler import (
    handle_write_prd, handle_approve_prd,
    handle_write_domain_model, handle_approve_domain_model,
    handle_write_brief, handle_approve_brief,
    handle_write_design, handle_approve_design,
    handle_write_tech_stack,
    handle_write_model, handle_approve_model,
    get_available_artifacts, find_latest, read_artifact,
    _resolve_topology, _next_stage,
)
from conftest import make_prd_input, make_domain_input, make_brief_input, make_design_input, make_tech_stack_input, make_model_input

pytestmark = pytest.mark.contract


class TestContractPrdToDomainModel:
    """
    Verifies that an approved PRD produced by handle_write_prd / handle_approve_prd
    is correctly consumed by handle_write_domain_model as the upstream reference.

    Uses prd_artifacts_dir: approved Briefs are pre-created (required for write_prd),
    and tests create + approve PRDs themselves.
    """

    def test_domain_references_field_points_to_approved_prd(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        domain = handle_write_domain_model(make_domain_input(slug="my-app"))
        assert len(domain["references"]) == 1
        assert domain["references"][0].endswith("my-app/prd/v1.json")

    def test_domain_slug_matches_prd_slug(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        domain = handle_write_domain_model(make_domain_input(slug="my-app"))
        assert domain["slug"] == "my-app"

    def test_domain_id_is_independent_from_prd_id(self, prd_artifacts_dir):
        prd = handle_write_prd(make_prd_input(slug="my-app"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        domain = handle_write_domain_model(make_domain_input(slug="my-app"))
        assert domain["id"] != prd["id"]
        assert domain["id"].startswith("domain-")

    def test_domain_written_to_separate_subfolder_from_prd(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        handle_write_domain_model(make_domain_input(slug="my-app"))
        assert (prd_artifacts_dir / "my-app" / "prd" / "v1.json").exists()
        assert (prd_artifacts_dir / "my-app" / "domain" / "v1.json").exists()


class TestContractPrdToDomainModelHandoffGuards:
    """
    Verifies that the engine enforces the PRD → Domain Model handoff contract:
    the domain model cannot be created when no approved PRD exists for the slug.
    """

    def test_domain_rejects_unapproved_prd(self, prd_artifacts_dir):
        """PRD exists but status is 'draft' — domain write must be rejected."""
        handle_write_prd(make_prd_input(slug="my-app"))
        # deliberately NOT approving the PRD
        with pytest.raises(ValueError, match="no approved PRD"):
            handle_write_domain_model(make_domain_input(slug="my-app"))

    def test_domain_rejects_slug_with_no_prd(self, prd_artifacts_dir):
        """Slug has an approved Brief but no PRD yet — domain write must be rejected."""
        # prd_artifacts_dir has an approved Brief for "my-app" but no PRD
        with pytest.raises(ValueError, match="no approved PRD"):
            handle_write_domain_model(make_domain_input(slug="my-app"))

    def test_domain_references_correct_slug_prd(self, prd_artifacts_dir):
        """Engine resolves PRD from the slug — references always match the slug."""
        handle_write_prd(make_prd_input(slug="my-app"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        domain = handle_write_domain_model(make_domain_input(slug="my-app"))
        # References must contain the PRD path for the same slug
        assert len(domain["references"]) == 1
        assert "my-app" in domain["references"][0]
        assert "prd" in domain["references"][0]


class TestContractBriefToPrd:
    """
    Verifies that an approved Brief produced by handle_write_brief / handle_approve_brief
    is the correct upstream artifact for the Product Owner (PRD) node.

    Tests that only touch Brief artifacts use the bare artifacts_dir fixture.
    Tests that also write PRDs use prd_artifacts_dir (approved Brief pre-created).
    """

    def test_approved_brief_has_required_content_fields(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        path = str(artifacts_dir / "my-app" / "brief" / "v1.json")
        approved = handle_approve_brief(path)
        for field in ("idea", "alternatives", "chosen_direction",
                      "competitive_scan", "complexity_assessment", "open_questions"):
            assert field in approved["content"]

    def test_approved_brief_status_is_approved(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        path = str(artifacts_dir / "my-app" / "brief" / "v1.json")
        approved = handle_approve_brief(path)
        assert approved["status"] == "approved"

    def test_unapproved_brief_cannot_be_approved_twice(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        path = str(artifacts_dir / "my-app" / "brief" / "v1.json")
        handle_approve_brief(path)
        with pytest.raises(ValueError, match="already approved"):
            handle_approve_brief(path)

    def test_brief_written_to_separate_subfolder_from_prd(self, prd_artifacts_dir):
        # Approved Brief already exists; write PRD and verify both subfolders exist
        handle_write_prd(make_prd_input(slug="my-app"))
        assert (prd_artifacts_dir / "my-app" / "brief" / "v1.json").exists()
        assert (prd_artifacts_dir / "my-app" / "prd" / "v1.json").exists()

    def test_brief_slug_matches_prd_slug(self, prd_artifacts_dir):
        brief = json.loads((prd_artifacts_dir / "my-app" / "brief" / "v1.json").read_text())
        prd = handle_write_prd(make_prd_input(slug="my-app"))
        assert brief["slug"] == prd["slug"]

    def test_brief_id_is_independent_from_prd_id(self, prd_artifacts_dir):
        brief = json.loads((prd_artifacts_dir / "my-app" / "brief" / "v1.json").read_text())
        prd = handle_write_prd(make_prd_input(slug="my-app"))
        assert brief["id"] != prd["id"]
        assert brief["id"].startswith("brief-")
        assert prd["id"].startswith("prd-")

    def test_prd_references_upstream_brief(self, prd_artifacts_dir):
        """Engine auto-populates references with the approved Brief path on v1."""
        prd = handle_write_prd(make_prd_input(slug="my-app"))
        assert len(prd["references"]) == 1
        assert "my-app" in prd["references"][0]
        assert "brief" in prd["references"][0]

    def test_prd_v1_fails_without_approved_brief(self, artifacts_dir):
        """No Brief exists for slug — PRD write must be rejected."""
        with pytest.raises(ValueError, match="no approved Brief"):
            handle_write_prd(make_prd_input(slug="my-app"))


class TestGetAvailableArtifacts:
    """
    Verifies the get_available_artifacts(stage) engine function returns correct
    buckets: in_progress (draft), approved, ready_to_start (upstream approved,
    this stage absent).

    This is the foundation of DAG state visibility across all agent entry points.
    """

    def test_empty_artifacts_dir_returns_all_empty_buckets(self, artifacts_dir):
        result = get_available_artifacts("brief")
        assert result == {"in_progress": [], "approved": [], "ready_to_start": []}

    def test_draft_brief_appears_in_in_progress(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        result = get_available_artifacts("brief")
        assert len(result["in_progress"]) == 1
        assert result["in_progress"][0]["slug"] == "my-app"
        assert result["in_progress"][0]["status"] == "draft"

    def test_approved_brief_appears_in_approved(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        handle_approve_brief(str(artifacts_dir / "my-app" / "brief" / "v1.json"))
        result = get_available_artifacts("brief")
        assert len(result["approved"]) == 1
        assert result["approved"][0]["slug"] == "my-app"
        assert result["approved"][0]["status"] == "approved"

    def test_brief_stage_has_no_ready_to_start(self, artifacts_dir):
        """Brief is the DAG entry node — it has no upstream, so ready_to_start is always empty."""
        handle_write_brief(make_brief_input(slug="my-app"))
        handle_approve_brief(str(artifacts_dir / "my-app" / "brief" / "v1.json"))
        result = get_available_artifacts("brief")
        assert result["ready_to_start"] == []

    def test_approved_brief_makes_slug_ready_to_start_for_prd(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        handle_approve_brief(str(artifacts_dir / "my-app" / "brief" / "v1.json"))
        result = get_available_artifacts("prd")
        assert len(result["ready_to_start"]) == 1
        assert result["ready_to_start"][0]["slug"] == "my-app"

    def test_draft_brief_does_not_make_slug_ready_for_prd(self, artifacts_dir):
        """Draft Brief should NOT populate ready_to_start for prd stage."""
        handle_write_brief(make_brief_input(slug="my-app"))
        result = get_available_artifacts("prd")
        assert result["ready_to_start"] == []

    def test_draft_prd_appears_in_in_progress_not_ready_to_start(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        result = get_available_artifacts("prd")
        in_progress_slugs = [e["slug"] for e in result["in_progress"]]
        ready_slugs = [e["slug"] for e in result["ready_to_start"]]
        assert "my-app" in in_progress_slugs
        assert "my-app" not in ready_slugs

    def test_approved_prd_makes_slug_ready_to_start_for_model_domain(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        result = get_available_artifacts("model_domain")
        assert any(e["slug"] == "my-app" for e in result["ready_to_start"])

    def test_entry_includes_open_questions_count(self, artifacts_dir):
        brief_input = make_brief_input(slug="my-app")
        handle_write_brief(brief_input)
        result = get_available_artifacts("brief")
        entry = result["in_progress"][0]
        assert "open_questions" in entry
        expected = len(make_brief_input()["open_questions"])
        assert entry["open_questions"] == expected

    def test_entry_includes_version_number(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        result = get_available_artifacts("brief")
        assert result["in_progress"][0]["version"] == 1

    def test_entry_includes_relative_path(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        result = get_available_artifacts("brief")
        assert result["in_progress"][0]["path"].endswith("my-app/brief/v1.json")

    def test_highest_version_wins(self, artifacts_dir):
        """get_available_artifacts always reflects the latest version for a slug."""
        handle_write_brief(make_brief_input(slug="my-app"))
        v1_path = str(artifacts_dir / "my-app" / "brief" / "v1.json")
        handle_approve_brief(v1_path)
        v1_artifact = json.loads((artifacts_dir / "my-app" / "brief" / "v1.json").read_text())
        # Write v2 (back to draft)
        handle_write_brief(make_brief_input(slug="my-app"), existing_brief=v1_artifact)
        result = get_available_artifacts("brief")
        # v2 is draft — appears in in_progress at version 2
        assert len(result["in_progress"]) == 1
        assert result["in_progress"][0]["version"] == 2
        assert result["approved"] == []

    def test_find_latest_returns_none_for_missing_slug(self, artifacts_dir):
        assert find_latest("nonexistent", "brief") is None

    def test_find_latest_status_filter_approved(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        v1_path = str(artifacts_dir / "my-app" / "brief" / "v1.json")
        handle_approve_brief(v1_path)
        assert find_latest("my-app", "brief", status="approved") is not None
        assert find_latest("my-app", "brief", status="draft") is None

    def test_find_latest_status_filter_draft(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        # v1 is draft, not yet approved
        assert find_latest("my-app", "brief", status="draft") is not None
        assert find_latest("my-app", "brief", status="approved") is None


class TestReadArtifact:
    """
    Verifies that read_artifact(slug, stage, version) returns {"artifact": ..., "schema": ...}
    and raises clear errors for missing or invalid inputs.
    """

    def test_returns_artifact_and_schema_keys(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        result = read_artifact("my-app", "brief")
        assert "artifact" in result
        assert "schema" in result

    def test_artifact_has_expected_fields(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        result = read_artifact("my-app", "brief")
        assert result["artifact"]["slug"] == "my-app"
        assert result["artifact"]["version"] == 1
        assert "content" in result["artifact"]

    def test_returns_latest_version_when_version_omitted(self, artifacts_dir):
        v1 = handle_write_brief(make_brief_input(slug="my-app"))
        handle_write_brief(make_brief_input(slug="my-app"), existing_brief=v1)
        result = read_artifact("my-app", "brief")
        assert result["artifact"]["version"] == 2

    def test_returns_specific_version_when_given(self, artifacts_dir):
        v1 = handle_write_brief(make_brief_input(slug="my-app"))
        handle_write_brief(make_brief_input(slug="my-app"), existing_brief=v1)
        result = read_artifact("my-app", "brief", version=1)
        assert result["artifact"]["version"] == 1

    def test_schema_empty_for_stages_without_base_schema(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        result = read_artifact("my-app", "brief")
        assert result["schema"] == {}

    def test_raises_for_unknown_slug(self, artifacts_dir):
        with pytest.raises(ValueError, match="ERROR \\[read_artifact\\]"):
            read_artifact("nonexistent", "brief")

    def test_raises_for_slug_with_no_artifacts_at_stage(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        with pytest.raises(ValueError, match="ERROR \\[read_artifact\\]"):
            read_artifact("my-app", "prd")

    def test_raises_for_unknown_version(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        with pytest.raises(ValueError, match="ERROR \\[read_artifact\\]"):
            read_artifact("my-app", "brief", version=99)

    def test_raises_for_invalid_slug(self, artifacts_dir):
        with pytest.raises(ValueError, match="slug.*invalid"):
            read_artifact("../../etc", "brief")


class TestContractDomainModelToDesign:
    """
    Verifies that an approved Domain Model produced by handle_write_domain_model /
    handle_approve_domain_model is correctly consumed by handle_write_design as
    the upstream reference.
    """

    def test_design_references_field_points_to_approved_model(self, design_artifacts_dir):
        design = handle_write_design(make_design_input(slug="my-app"))
        assert len(design["references"]) == 1
        assert design["references"][0].endswith("my-app/model_domain/v1.json")

    def test_design_slug_matches_model_slug(self, design_artifacts_dir):
        design = handle_write_design(make_design_input(slug="my-app"))
        assert design["slug"] == "my-app"

    def test_design_id_is_independent_from_model_id(self, design_artifacts_dir):
        model = read_artifact("my-app", "model_domain")["artifact"]
        design = handle_write_design(make_design_input(slug="my-app"))
        assert design["id"] != model["id"]
        assert design["id"].startswith("design-")

    def test_design_written_to_separate_subfolder_from_model(self, design_artifacts_dir):
        handle_write_design(make_design_input(slug="my-app"))
        assert (design_artifacts_dir / "my-app" / "model_domain" / "v1.json").exists()
        assert (design_artifacts_dir / "my-app" / "design" / "v1.json").exists()


class TestContractDesignToTechStack:
    """
    Verifies that an approved Design artifact produced by handle_write_design /
    handle_approve_design is correctly consumed by handle_write_tech_stack as
    the upstream reference.
    """

    def test_tech_stack_references_field_points_to_approved_design(self, tech_stack_artifacts_dir):
        ts = handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        assert len(ts["references"]) == 1
        assert ts["references"][0].endswith("my-app/design/v1.json")

    def test_tech_stack_slug_matches_design_slug(self, tech_stack_artifacts_dir):
        ts = handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        assert ts["slug"] == "my-app"

    def test_tech_stack_id_is_independent_from_design_id(self, tech_stack_artifacts_dir):
        design = read_artifact("my-app", "design")["artifact"]
        ts = handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        assert ts["id"] != design["id"]
        assert ts["id"].startswith("tech-stack-")

    def test_tech_stack_written_to_separate_subfolder_from_design(self, tech_stack_artifacts_dir):
        handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        assert (tech_stack_artifacts_dir / "my-app" / "design" / "v1.json").exists()
        assert (tech_stack_artifacts_dir / "my-app" / "tech_stack" / "v1.json").exists()

class TestContractDesignToTechStackHandoffGuards:
    """
    Verifies that the engine enforces the Design → Tech Stack handoff contract:
    the tech stack cannot be created when no approved Design artifact exists.
    """

    def test_tech_stack_requires_approved_design(self, design_artifacts_dir):
        """Draft design (unapproved) is not sufficient to start tech stack."""
        handle_write_design(make_design_input(slug="deploy-rollback"))
        # design is draft, not approved — must fail
        with pytest.raises(ValueError, match="no approved Design artifact"):
            handle_write_tech_stack(make_tech_stack_input(slug="deploy-rollback"))

    def test_tech_stack_requires_existing_design(self, domain_artifacts_dir):
        """No design artifact at all raises ValueError."""
        with pytest.raises(ValueError, match="no approved Design artifact"):
            handle_write_tech_stack(make_tech_stack_input(slug="no-design-here"))

    def test_tech_stack_references_correct_slug_design(self, tech_stack_artifacts_dir):
        """Engine resolves design from the slug — references always match the slug."""
        ts = handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        assert len(ts["references"]) == 1
        assert "my-app" in ts["references"][0]
        assert "design" in ts["references"][0]


class TestContractDomainModelToDesignHandoffGuards:
    """
    Verifies that the engine enforces the Model → Design handoff contract:
    the design cannot be created when no approved model artifact exists for the slug.
    """

    def test_design_requires_approved_model(self, prd_artifacts_dir):
        """Draft model (unapproved) is not sufficient to start design."""
        handle_write_prd(make_prd_input(slug="deploy-rollback", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "deploy-rollback" / "prd" / "v1.json"))
        handle_write_model(make_model_input(slug="deploy-rollback", model_type="domain"))
        # model_domain is draft, not approved — must fail
        with pytest.raises(ValueError, match="no approved model_domain"):
            handle_write_design(make_design_input(slug="deploy-rollback"))

    def test_design_requires_approved_prd_for_topology(self, prd_artifacts_dir):
        """No approved PRD means topology is undetermined — must fail."""
        with pytest.raises(ValueError, match="cannot determine topology"):
            handle_write_design(make_design_input(slug="no-prd-here"))


# ---------------------------------------------------------------------------
# Step 2 — DAG topology: _resolve_topology and _next_stage
# ---------------------------------------------------------------------------

class TestTopologyResolution:
    """
    Verifies that _resolve_topology(slug) returns the correct stage list
    per archetype combination, and returns None when no approved PRD exists
    or when the PRD predates archetype classification.
    """

    def test_domain_system_topology(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        topology = _resolve_topology("my-app")
        assert topology == ["brief", "prd", "model_domain", "design", "tech_stack"]

    def test_data_pipeline_topology(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="deploy-rollback", primary_archetype="data_pipeline"))
        handle_approve_prd(str(prd_artifacts_dir / "deploy-rollback" / "prd" / "v1.json"))
        topology = _resolve_topology("deploy-rollback")
        assert topology == ["brief", "prd", "model_data_flow", "design", "tech_stack"]

    def test_system_integration_topology(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="system_integration"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        topology = _resolve_topology("my-app")
        assert topology == ["brief", "prd", "model_system", "design", "tech_stack"]

    def test_layered_topology(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(
            slug="my-app",
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        topology = _resolve_topology("my-app")
        assert topology == ["brief", "prd", "model_system", "model_workflow", "design", "tech_stack"]

    def test_process_system_topology(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="process_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        topology = _resolve_topology("my-app")
        assert topology == ["brief", "prd", "model_workflow", "design", "tech_stack"]

    def test_system_evolution_topology(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="system_evolution"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        topology = _resolve_topology("my-app")
        assert topology == ["brief", "prd", "model_evolution", "design", "tech_stack"]

    def test_returns_none_without_approved_prd(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        # PRD exists but is draft — not approved
        assert _resolve_topology("my-app") is None

    def test_returns_none_for_unknown_slug(self, artifacts_dir):
        assert _resolve_topology("nonexistent") is None

    def test_all_valid_combinations_have_topology(self):
        """_VALID_COMBINATIONS and _DAG_TOPOLOGIES must stay in sync.

        Adding a combination without a topology causes silent None returns from
        _resolve_topology — no error, just missing ready_to_start entries.
        """
        from tool_handler import _VALID_COMBINATIONS, _DAG_TOPOLOGIES
        assert _VALID_COMBINATIONS == frozenset(_DAG_TOPOLOGIES.keys())


class TestNextStage:
    """
    Verifies _next_stage(slug) — the forward-looking function that returns the
    first unstarted stage for a slug by walking the topology from approved state.

    The function encodes the DAG gate rules:
    - No approved brief → None (entry gate not met)
    - Brief approved, no PRD started → "prd"
    - PRD in-progress (draft) → None (wait for approval)
    - PRD approved → first model stage for that archetype
    - Model stage in-progress → None
    - All stages complete → None
    """

    def test_returns_none_when_no_brief_exists(self, artifacts_dir):
        assert _next_stage("nonexistent") is None

    def test_returns_none_when_brief_is_draft_only(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        assert _next_stage("my-app") is None

    def test_returns_prd_when_brief_approved_no_prd(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        handle_approve_brief(str(artifacts_dir / "my-app" / "brief" / "v1.json"))
        assert _next_stage("my-app") == "prd"

    def test_returns_none_when_prd_is_draft(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        # PRD is draft — gate is not open
        assert _next_stage("my-app") is None

    def test_returns_model_domain_when_prd_approved_for_domain_system(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        assert _next_stage("my-app") == "model_domain"

    def test_returns_model_data_flow_when_prd_approved_for_data_pipeline(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="data_pipeline"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        assert _next_stage("my-app") == "model_data_flow"

    def test_returns_model_system_when_prd_approved_for_system_integration(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="system_integration"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        assert _next_stage("my-app") == "model_system"

    def test_returns_model_workflow_when_prd_approved_for_process_system(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="process_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        assert _next_stage("my-app") == "model_workflow"

    def test_returns_model_system_first_in_layered_topology(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(
            slug="my-app",
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        assert _next_stage("my-app") == "model_system"

    def test_returns_none_when_prd_predates_archetype_classification(self, prd_artifacts_dir):
        """PRD approved but has no archetype fields — topology undetermined."""
        # Write PRD without archetype fields by patching the file directly
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        prd_path = prd_artifacts_dir / "my-app" / "prd" / "v1.json"
        prd_artifact = json.loads(prd_path.read_text())
        prd_artifact["status"] = "approved"
        prd_artifact["content"].pop("primary_archetype", None)
        prd_artifact["content"].pop("secondary_archetype", None)
        prd_path.write_text(json.dumps(prd_artifact, indent=2))
        assert _next_stage("my-app") is None


class TestTopologyAwareGetAvailableArtifacts:
    """
    Verifies that get_available_artifacts is topology-aware for model stages:
    a slug whose archetype does not include a given model stage must not appear
    in ready_to_start for that stage.
    """

    def test_data_pipeline_slug_not_ready_for_model_domain(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="data_pipeline"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        result = get_available_artifacts("model_domain")
        ready_slugs = [e["slug"] for e in result["ready_to_start"]]
        assert "my-app" not in ready_slugs

    def test_domain_system_slug_is_ready_for_model_domain(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        result = get_available_artifacts("model_domain")
        ready_slugs = [e["slug"] for e in result["ready_to_start"]]
        assert "my-app" in ready_slugs

    def test_layered_slug_ready_for_model_system_not_model_domain(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(
            slug="my-app",
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        model_domain_ready = [e["slug"] for e in get_available_artifacts("model_domain")["ready_to_start"]]
        model_system_ready = [e["slug"] for e in get_available_artifacts("model_system")["ready_to_start"]]
        assert "my-app" not in model_domain_ready
        assert "my-app" in model_system_ready

    def test_process_system_slug_ready_for_model_workflow_not_others(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="process_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        for wrong_stage in ("model_domain", "model_data_flow", "model_system"):
            ready = [e["slug"] for e in get_available_artifacts(wrong_stage)["ready_to_start"]]
            assert "my-app" not in ready, f"should not be ready for {wrong_stage}"
        ready_workflow = [e["slug"] for e in get_available_artifacts("model_workflow")["ready_to_start"]]
        assert "my-app" in ready_workflow




# ---------------------------------------------------------------------------
# Step 4 — PRD → Model contracts
# ---------------------------------------------------------------------------

class TestContractPRDToModel:
    """
    Verifies that an approved PRD is correctly consumed by handle_write_model
    and that each archetype routes to the correct stage.
    """

    @pytest.mark.parametrize("model_type,archetype,expected_stage", [
        ("domain",    "domain_system",     "model_domain"),
        ("data_flow", "data_pipeline",     "model_data_flow"),
        ("system",    "system_integration","model_system"),
        ("workflow",  "process_system",    "model_workflow"),
    ])
    def test_model_references_approved_prd(self, prd_artifacts_dir, model_type, archetype, expected_stage):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype=archetype))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        artifact = handle_write_model(make_model_input(slug="my-app", model_type=model_type))
        assert artifact["references"][0].endswith("my-app/prd/v1.json")
        assert (prd_artifacts_dir / "my-app" / expected_stage / "v1.json").exists()

    @pytest.mark.parametrize("model_type,archetype", [
        ("domain",    "domain_system"),
        ("data_flow", "data_pipeline"),
        ("system",    "system_integration"),
        ("workflow",  "process_system"),
    ])
    def test_approved_prd_makes_slug_ready_for_correct_model_stage(self, prd_artifacts_dir, model_type, archetype):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype=archetype))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        expected_stage = f"model_{model_type}"
        result = get_available_artifacts(expected_stage)
        assert any(e["slug"] == "my-app" for e in result["ready_to_start"])

    def test_wrong_archetype_not_ready_for_other_model_stage(self, prd_artifacts_dir):
        """data_pipeline slug must not appear in ready_to_start for model_domain."""
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="data_pipeline"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        result = get_available_artifacts("model_domain")
        assert not any(e["slug"] == "my-app" for e in result["ready_to_start"])


class TestContractLayeredModel:
    """
    Verifies the layered topology (system_integration + process_system):
    model_system must be approved before model_workflow can start.
    """

    def test_layered_model_system_approval_unlocks_model_workflow(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(
            slug="my-app",
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        handle_write_model(make_model_input(slug="my-app", model_type="system"))
        handle_approve_model(str(prd_artifacts_dir / "my-app" / "model_system" / "v1.json"))
        result = get_available_artifacts("model_workflow")
        assert any(e["slug"] == "my-app" for e in result["ready_to_start"])

    def test_layered_model_system_not_approved_blocks_model_workflow(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(
            slug="my-app",
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        handle_write_model(make_model_input(slug="my-app", model_type="system"))
        # model_system is draft — model_workflow must not be ready
        result = get_available_artifacts("model_workflow")
        assert not any(e["slug"] == "my-app" for e in result["ready_to_start"])
