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
    get_available_artifacts, find_latest, read_artifact,
    _resolve_topology, _get_upstream_stage,
)
from conftest import make_prd_input, make_domain_input, make_brief_input, make_design_input, make_tech_stack_input

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
    Verifies that read_artifact(slug, stage, version) returns the full artifact
    content and raises clear errors for missing or invalid inputs.

    This is the MCP-scoped replacement for direct file reads in agent prompts.
    Agents must use this tool instead of Claude Code's Read/Glob for artifact access.
    """

    def test_returns_full_artifact_for_brief(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        artifact = read_artifact("my-app", "brief")
        assert artifact["slug"] == "my-app"
        assert artifact["version"] == 1
        assert "content" in artifact

    def test_returns_latest_version_when_version_omitted(self, artifacts_dir):
        v1 = handle_write_brief(make_brief_input(slug="my-app"))
        handle_write_brief(make_brief_input(slug="my-app"), existing_brief=v1)
        artifact = read_artifact("my-app", "brief")
        assert artifact["version"] == 2

    def test_returns_specific_version_when_given(self, artifacts_dir):
        v1 = handle_write_brief(make_brief_input(slug="my-app"))
        handle_write_brief(make_brief_input(slug="my-app"), existing_brief=v1)
        artifact = read_artifact("my-app", "brief", version=1)
        assert artifact["version"] == 1

    def test_returns_full_artifact_for_prd(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        artifact = read_artifact("my-app", "prd")
        assert artifact["slug"] == "my-app"
        assert "content" in artifact
        assert "title" in artifact["content"]

    def test_returns_full_artifact_for_domain(self, domain_artifacts_dir):
        handle_write_domain_model(make_domain_input(slug="my-app"))
        artifact = read_artifact("my-app", "domain")
        assert artifact["slug"] == "my-app"
        assert "bounded_contexts" in artifact["content"]

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

    def test_design_references_field_points_to_approved_domain(self, design_artifacts_dir):
        design = handle_write_design(make_design_input(slug="my-app"))
        assert len(design["references"]) == 1
        assert design["references"][0].endswith("my-app/domain/v1.json")

    def test_design_slug_matches_domain_slug(self, design_artifacts_dir):
        design = handle_write_design(make_design_input(slug="my-app"))
        assert design["slug"] == "my-app"

    def test_design_id_is_independent_from_domain_id(self, design_artifacts_dir):
        domain = read_artifact("my-app", "domain")
        design = handle_write_design(make_design_input(slug="my-app"))
        assert design["id"] != domain["id"]
        assert design["id"].startswith("design-")

    def test_design_written_to_separate_subfolder_from_domain(self, design_artifacts_dir):
        handle_write_design(make_design_input(slug="my-app"))
        assert (design_artifacts_dir / "my-app" / "domain" / "v1.json").exists()
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
        design = read_artifact("my-app", "design")
        ts = handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        assert ts["id"] != design["id"]
        assert ts["id"].startswith("tech-stack-")

    def test_tech_stack_written_to_separate_subfolder_from_design(self, tech_stack_artifacts_dir):
        handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        assert (tech_stack_artifacts_dir / "my-app" / "design" / "v1.json").exists()
        assert (tech_stack_artifacts_dir / "my-app" / "tech_stack" / "v1.json").exists()

    def test_approved_design_makes_slug_ready_to_start_for_tech_stack(self, tech_stack_artifacts_dir):
        result = get_available_artifacts("tech_stack")
        ready_slugs = [e["slug"] for e in result["ready_to_start"]]
        # my-app has an approved design but no tech_stack yet in this fixture
        assert "my-app" in ready_slugs


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
    Verifies that the engine enforces the Domain Model → Design handoff contract:
    the design cannot be created when no approved Domain Model exists for the slug.
    """

    def test_design_requires_approved_domain_model(self, prd_artifacts_dir):
        """Draft domain model (unapproved) is not sufficient to start design."""
        handle_write_prd(make_prd_input(slug="deploy-rollback"))
        handle_approve_prd(str(prd_artifacts_dir / "deploy-rollback" / "prd" / "v1.json"))
        handle_write_domain_model(make_domain_input(slug="deploy-rollback"))
        # domain is draft, not approved — must fail
        with pytest.raises(ValueError, match="no approved Domain Model"):
            handle_write_design(make_design_input(slug="deploy-rollback"))

    def test_design_requires_existing_domain_model(self, prd_artifacts_dir):
        """No domain model at all raises ValueError."""
        with pytest.raises(ValueError, match="no approved Domain Model"):
            handle_write_design(make_design_input(slug="no-domain-here"))


# ---------------------------------------------------------------------------
# Step 2 — DAG topology resolution
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

    def test_returns_none_without_approved_prd(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        # PRD exists but is draft — not approved
        assert _resolve_topology("my-app") is None

    def test_returns_none_for_unknown_slug(self, artifacts_dir):
        assert _resolve_topology("nonexistent") is None


class TestUpstreamStageResolution:
    """
    Verifies that _get_upstream_stage(slug, stage) returns the correct upstream
    using topology for topology-aware stages and _UPSTREAM_STAGE fallback for legacy stages.
    """

    def test_model_domain_upstream_is_prd(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        assert _get_upstream_stage("my-app", "model_domain") == "prd"

    def test_model_workflow_upstream_is_model_system_in_layered_case(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(
            slug="my-app",
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        assert _get_upstream_stage("my-app", "model_workflow") == "model_system"

    def test_design_upstream_is_model_domain_in_domain_system_topology(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        assert _get_upstream_stage("my-app", "design") == "model_domain"

    def test_returns_none_when_no_approved_prd(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-app"))
        # draft PRD — topology undetermined → None, not a legacy fallback
        assert _get_upstream_stage("my-app", "design") is None


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


class TestUpstreamChangedSignal:
    """
    Verifies that get_available_artifacts surfaces upstream_changed: true on an
    approved artifact when the latest approved upstream was updated after it.
    """

    def test_upstream_changed_true_when_upstream_re_approved_later(self, artifacts_dir):
        """Approved PRD shows upstream_changed when its Brief was updated later.

        Uses prd stage (upstream=brief) — universally resolvable without slug-specific
        topology. The signal logic is identical regardless of stage.
        """
        handle_write_brief(make_brief_input(slug="my-app"))
        handle_approve_brief(str(artifacts_dir / "my-app" / "brief" / "v1.json"))
        handle_write_prd(make_prd_input(slug="my-app"))
        handle_approve_prd(str(artifacts_dir / "my-app" / "prd" / "v1.json"))

        # Patch brief updated_at to be clearly after prd updated_at
        brief_path = artifacts_dir / "my-app" / "brief" / "v1.json"
        brief_artifact = json.loads(brief_path.read_text())
        brief_artifact["updated_at"] = "2099-01-01T00:00:00+00:00"
        brief_path.write_text(json.dumps(brief_artifact, indent=2))

        result = get_available_artifacts("prd")
        approved = {e["slug"]: e for e in result["approved"]}
        assert "my-app" in approved
        assert approved["my-app"].get("upstream_changed") is True
        assert "brief" in approved["my-app"]["upstream_changed_note"]

    def test_upstream_changed_absent_when_upstream_not_newer(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-app"))
        handle_approve_brief(str(artifacts_dir / "my-app" / "brief" / "v1.json"))
        handle_write_prd(make_prd_input(slug="my-app"))
        handle_approve_prd(str(artifacts_dir / "my-app" / "prd" / "v1.json"))

        result = get_available_artifacts("prd")
        approved = {e["slug"]: e for e in result["approved"]}
        assert "my-app" in approved
        assert "upstream_changed" not in approved["my-app"]
