"""
Lifecycle tests — correct versioning behavior through the v1 / v2 / approve chain.

These tests verify that each handler produces the correct structure at each
stage of the artifact's life: initial creation, iterative refinement, and
approval. They also test that data is correctly persisted to and read from disk.

Run this suite alone:  pytest -m lifecycle
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_handler import (
    handle_write_prd,
    handle_approve_prd,
    handle_write_domain_model,
    handle_approve_domain_model,
    handle_write_brief,
    handle_approve_brief,
    handle_write_design,
    handle_approve_design,
    handle_write_tech_stack,
    handle_approve_tech_stack,
    handle_update_schema,
    _ensure_instance_schema,
)
from conftest import make_prd_input, make_domain_input, make_brief_input, make_design_input, make_tech_stack_input, make_model_input

pytestmark = pytest.mark.lifecycle


# ===========================================================================
# PRD — v1 creation
# ===========================================================================

class TestPrdV1:
    def test_id_has_prd_prefix(self, prd_artifacts_dir):
        assert handle_write_prd(make_prd_input())["id"].startswith("prd-")

    def test_version_is_1(self, prd_artifacts_dir):
        assert handle_write_prd(make_prd_input())["version"] == 1

    def test_parent_version_is_none(self, prd_artifacts_dir):
        assert handle_write_prd(make_prd_input())["parent_version"] is None

    def test_created_at_and_updated_at_set(self, prd_artifacts_dir):
        a = handle_write_prd(make_prd_input())
        assert a["created_at"]
        assert a["updated_at"]

    def test_source_idea_stored(self, prd_artifacts_dir):
        a = handle_write_prd(make_prd_input(source_idea="My original idea"))
        assert a["source_idea"] == "My original idea"

    def test_references_contains_upstream_brief(self, prd_artifacts_dir):
        a = handle_write_prd(make_prd_input())
        assert len(a["references"]) == 1
        assert a["references"][0].endswith("test-project/brief/v1.json")

    def test_decision_log_empty_when_no_entry(self, prd_artifacts_dir):
        assert handle_write_prd(make_prd_input())["decision_log"] == []

    def test_decision_log_entry_appended_with_metadata(self, prd_artifacts_dir):
        inp = make_prd_input()
        inp["decision_log_entry"] = {
            "trigger": "initial_draft", "summary": "First draft", "changed_fields": ["title"],
        }
        a = handle_write_prd(inp)
        assert len(a["decision_log"]) == 1
        entry = a["decision_log"][0]
        assert entry["version"] == 1
        assert entry["author"] == "agent:product-agent"
        assert entry["trigger"] == "initial_draft"
        assert entry["summary"] == "First draft"
        assert entry["timestamp"]

    def test_content_fields_present(self, prd_artifacts_dir):
        a = handle_write_prd(make_prd_input())
        for key in ("title", "problem", "target_users", "goals", "features"):
            assert key in a["content"]

    def test_file_written_to_correct_path(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-project"))
        assert (prd_artifacts_dir / "my-project" / "prd" / "v1.json").exists()

    def test_file_is_valid_json(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input(slug="my-project"))
        raw = (prd_artifacts_dir / "my-project" / "prd" / "v1.json").read_text()
        parsed = json.loads(raw)
        assert parsed["version"] == 1


# ===========================================================================
# PRD — v2 refinement
# ===========================================================================

class TestPrdV2:
    def _v1(self, prd_artifacts_dir):
        return handle_write_prd(make_prd_input())

    def test_version_increments_by_1(self, prd_artifacts_dir):
        v1 = self._v1(prd_artifacts_dir)
        v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
        assert v2["version"] == 2

    def test_parent_version_points_to_prior(self, prd_artifacts_dir):
        v1 = self._v1(prd_artifacts_dir)
        v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
        assert v2["parent_version"] == 1

    def test_updated_at_changes(self, prd_artifacts_dir):
        v1 = self._v1(prd_artifacts_dir)
        v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
        assert v2["updated_at"] >= v1["updated_at"]

    def test_references_carried_forward(self, prd_artifacts_dir):
        v1 = self._v1(prd_artifacts_dir)
        v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
        assert v2["references"] == v1["references"]

    def test_decision_log_grows_by_one(self, prd_artifacts_dir):
        v1_inp = make_prd_input()
        v1_inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "v1", "changed_fields": []}
        v1 = handle_write_prd(v1_inp)

        v2_inp = make_prd_input()
        v2_inp["decision_log_entry"] = {"trigger": "human_feedback", "summary": "v2", "changed_fields": ["title"]}
        v2 = handle_write_prd(v2_inp, existing_prd=v1)

        assert len(v2["decision_log"]) == 2
        assert v2["decision_log"][1]["version"] == 2

    def test_three_version_chain(self, prd_artifacts_dir):
        v1 = handle_write_prd(make_prd_input())
        v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
        v3 = handle_write_prd(make_prd_input(), existing_prd=v2)
        assert v3["version"] == 3
        assert v3["parent_version"] == 2

    def test_v2_file_written_to_disk(self, prd_artifacts_dir):
        v1 = self._v1(prd_artifacts_dir)
        handle_write_prd(make_prd_input(), existing_prd=v1)
        assert (prd_artifacts_dir / "test-project" / "prd" / "v2.json").exists()


# ===========================================================================
# PRD — approval
# ===========================================================================

class TestApprovePrd:
    def _write_and_approve(self, prd_artifacts_dir):
        handle_write_prd(make_prd_input())
        path = str(prd_artifacts_dir / "test-project" / "prd" / "v1.json")
        return handle_approve_prd(path), path

    def test_status_set_to_approved(self, prd_artifacts_dir):
        approved, _ = self._write_and_approve(prd_artifacts_dir)
        assert approved["status"] == "approved"

    def test_updated_at_refreshed(self, prd_artifacts_dir):
        v1 = handle_write_prd(make_prd_input())
        path = str(prd_artifacts_dir / "test-project" / "prd" / "v1.json")
        approved = handle_approve_prd(path)
        assert approved["updated_at"] >= v1["updated_at"]

    def test_approval_entry_author_is_human(self, prd_artifacts_dir):
        approved, _ = self._write_and_approve(prd_artifacts_dir)
        assert approved["decision_log"][-1]["author"] == "human"

    def test_approval_entry_trigger(self, prd_artifacts_dir):
        approved, _ = self._write_and_approve(prd_artifacts_dir)
        assert approved["decision_log"][-1]["trigger"] == "approval"

    def test_version_unchanged_on_approval(self, prd_artifacts_dir):
        approved, _ = self._write_and_approve(prd_artifacts_dir)
        assert approved["version"] == 1

    def test_approval_persisted_to_disk(self, prd_artifacts_dir):
        _, path = self._write_and_approve(prd_artifacts_dir)
        on_disk = json.loads(Path(path).read_text())
        assert on_disk["status"] == "approved"

    def test_approve_rejects_missing_file(self, prd_artifacts_dir):
        with pytest.raises(ValueError, match="artifact not found"):
            handle_approve_prd(str(prd_artifacts_dir / "ghost" / "prd" / "v1.json"))

    def test_approve_rejects_already_approved(self, prd_artifacts_dir):
        _, path = self._write_and_approve(prd_artifacts_dir)
        with pytest.raises(ValueError, match="already approved"):
            handle_approve_prd(path)

    def test_approve_rejects_path_outside_artifacts_dir(self, prd_artifacts_dir):
        with pytest.raises(ValueError, match="outside the artifacts directory"):
            handle_approve_prd("/etc/passwd")


# ===========================================================================
# Domain model — v1 creation
# ===========================================================================

class TestDomainV1:
    def test_id_has_domain_prefix(self, domain_artifacts_dir):
        assert handle_write_domain_model(make_domain_input())["id"].startswith("domain-")

    def test_version_is_1(self, domain_artifacts_dir):
        assert handle_write_domain_model(make_domain_input())["version"] == 1

    def test_parent_version_is_none(self, domain_artifacts_dir):
        assert handle_write_domain_model(make_domain_input())["parent_version"] is None

    def test_created_at_and_updated_at_set(self, domain_artifacts_dir):
        a = handle_write_domain_model(make_domain_input())
        assert a["created_at"]
        assert a["updated_at"]

    def test_references_contains_upstream_prd(self, domain_artifacts_dir):
        """Engine resolves and stores the upstream PRD path in references."""
        a = handle_write_domain_model(make_domain_input())
        assert len(a["references"]) == 1
        assert a["references"][0].endswith("test-project/prd/v1.json")

    def test_decision_log_empty_when_no_entry(self, domain_artifacts_dir):
        assert handle_write_domain_model(make_domain_input())["decision_log"] == []

    def test_decision_log_entry_appended_with_metadata(self, domain_artifacts_dir):
        inp = make_domain_input()
        inp["decision_log_entry"] = {
            "trigger": "initial_draft", "summary": "Initial model", "changed_fields": ["bounded_contexts"],
        }
        a = handle_write_domain_model(inp)
        assert len(a["decision_log"]) == 1
        entry = a["decision_log"][0]
        assert entry["version"] == 1
        assert entry["author"] == "agent:domain-agent"
        assert entry["timestamp"]

    def test_content_fields_present(self, domain_artifacts_dir):
        a = handle_write_domain_model(make_domain_input())
        for key in ("bounded_contexts", "context_map", "open_questions"):
            assert key in a["content"]

    def test_file_written_to_correct_path(self, domain_artifacts_dir):
        handle_write_domain_model(make_domain_input(slug="deploy-rollback"))
        assert (domain_artifacts_dir / "deploy-rollback" / "domain" / "v1.json").exists()

    def test_file_is_valid_json(self, domain_artifacts_dir):
        handle_write_domain_model(make_domain_input(slug="deploy-rollback"))
        raw = (domain_artifacts_dir / "deploy-rollback" / "domain" / "v1.json").read_text()
        parsed = json.loads(raw)
        assert parsed["version"] == 1


# ===========================================================================
# Domain model — v2 refinement
# ===========================================================================

class TestDomainV2:
    def _v1(self, domain_artifacts_dir):
        return handle_write_domain_model(make_domain_input())

    def test_version_increments_by_1(self, domain_artifacts_dir):
        v1 = self._v1(domain_artifacts_dir)
        v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
        assert v2["version"] == 2

    def test_parent_version_points_to_prior(self, domain_artifacts_dir):
        v1 = self._v1(domain_artifacts_dir)
        v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
        assert v2["parent_version"] == 1

    def test_updated_at_changes(self, domain_artifacts_dir):
        v1 = self._v1(domain_artifacts_dir)
        v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
        assert v2["updated_at"] >= v1["updated_at"]

    def test_references_carried_forward(self, domain_artifacts_dir):
        v1 = self._v1(domain_artifacts_dir)
        v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
        assert v2["references"] == v1["references"]

    def test_decision_log_grows_by_one(self, domain_artifacts_dir):
        v1_inp = make_domain_input()
        v1_inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "v1", "changed_fields": []}
        v1 = handle_write_domain_model(v1_inp)

        v2_inp = make_domain_input()
        v2_inp["decision_log_entry"] = {"trigger": "human_feedback", "summary": "v2", "changed_fields": ["bounded_contexts"]}
        v2 = handle_write_domain_model(v2_inp, existing_domain=v1)

        assert len(v2["decision_log"]) == 2
        assert v2["decision_log"][1]["version"] == 2

    def test_three_version_chain(self, domain_artifacts_dir):
        v1 = handle_write_domain_model(make_domain_input())
        v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
        v3 = handle_write_domain_model(make_domain_input(), existing_domain=v2)
        assert v3["version"] == 3
        assert v3["parent_version"] == 2

    def test_v2_file_written_to_disk(self, domain_artifacts_dir):
        v1 = self._v1(domain_artifacts_dir)
        handle_write_domain_model(make_domain_input(), existing_domain=v1)
        assert (domain_artifacts_dir / "test-project" / "domain" / "v2.json").exists()


# ===========================================================================
# Domain model — approval
# ===========================================================================

class TestApproveDomainModel:
    def _write_and_approve(self, domain_artifacts_dir):
        handle_write_domain_model(make_domain_input())
        path = str(domain_artifacts_dir / "test-project" / "domain" / "v1.json")
        return handle_approve_domain_model(path), path

    def test_status_set_to_approved(self, domain_artifacts_dir):
        approved, _ = self._write_and_approve(domain_artifacts_dir)
        assert approved["status"] == "approved"

    def test_updated_at_refreshed(self, domain_artifacts_dir):
        v1 = handle_write_domain_model(make_domain_input())
        path = str(domain_artifacts_dir / "test-project" / "domain" / "v1.json")
        approved = handle_approve_domain_model(path)
        assert approved["updated_at"] >= v1["updated_at"]

    def test_approval_entry_author_is_human(self, domain_artifacts_dir):
        approved, _ = self._write_and_approve(domain_artifacts_dir)
        assert approved["decision_log"][-1]["author"] == "human"

    def test_approval_entry_trigger(self, domain_artifacts_dir):
        approved, _ = self._write_and_approve(domain_artifacts_dir)
        assert approved["decision_log"][-1]["trigger"] == "approval"

    def test_version_unchanged_on_approval(self, domain_artifacts_dir):
        approved, _ = self._write_and_approve(domain_artifacts_dir)
        assert approved["version"] == 1

    def test_approval_persisted_to_disk(self, domain_artifacts_dir):
        _, path = self._write_and_approve(domain_artifacts_dir)
        on_disk = json.loads(Path(path).read_text())
        assert on_disk["status"] == "approved"

    def test_approve_rejects_missing_file(self, domain_artifacts_dir):
        with pytest.raises(ValueError, match="artifact not found"):
            handle_approve_domain_model(str(domain_artifacts_dir / "ghost" / "domain" / "v1.json"))

    def test_approve_rejects_already_approved(self, domain_artifacts_dir):
        _, path = self._write_and_approve(domain_artifacts_dir)
        with pytest.raises(ValueError, match="already approved"):
            handle_approve_domain_model(path)

    def test_approve_rejects_path_outside_artifacts_dir(self, domain_artifacts_dir):
        with pytest.raises(ValueError, match="outside the artifacts directory"):
            handle_approve_domain_model("/etc/passwd")


# ===========================================================================
# Brief — v1 creation
# ===========================================================================

class TestBriefV1:
    def test_id_has_brief_prefix(self, artifacts_dir):
        assert handle_write_brief(make_brief_input())["id"].startswith("brief-")

    def test_version_is_1(self, artifacts_dir):
        assert handle_write_brief(make_brief_input())["version"] == 1

    def test_parent_version_is_none(self, artifacts_dir):
        assert handle_write_brief(make_brief_input())["parent_version"] is None

    def test_created_at_and_updated_at_set(self, artifacts_dir):
        a = handle_write_brief(make_brief_input())
        assert a["created_at"]
        assert a["updated_at"]

    def test_idea_stored_in_content(self, artifacts_dir):
        a = handle_write_brief(make_brief_input(idea="My original idea"))
        assert a["content"]["idea"] == "My original idea"

    def test_references_empty(self, artifacts_dir):
        assert handle_write_brief(make_brief_input())["references"] == []

    def test_decision_log_empty_when_no_entry(self, artifacts_dir):
        assert handle_write_brief(make_brief_input())["decision_log"] == []

    def test_decision_log_entry_appended_with_metadata(self, artifacts_dir):
        inp = make_brief_input()
        inp["decision_log_entry"] = {
            "trigger": "initial_draft", "summary": "First brief", "changed_fields": ["alternatives"],
        }
        a = handle_write_brief(inp)
        assert len(a["decision_log"]) == 1
        entry = a["decision_log"][0]
        assert entry["version"] == 1
        assert entry["author"] == "agent:brainstorm-agent"
        assert entry["trigger"] == "initial_draft"
        assert entry["timestamp"]

    def test_content_fields_present(self, artifacts_dir):
        a = handle_write_brief(make_brief_input())
        for key in ("idea", "alternatives", "chosen_direction", "competitive_scan",
                    "complexity_assessment", "open_questions"):
            assert key in a["content"]

    def test_file_written_to_correct_path(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-project"))
        assert (artifacts_dir / "my-project" / "brief" / "v1.json").exists()

    def test_file_is_valid_json(self, artifacts_dir):
        handle_write_brief(make_brief_input(slug="my-project"))
        raw = (artifacts_dir / "my-project" / "brief" / "v1.json").read_text()
        parsed = json.loads(raw)
        assert parsed["version"] == 1


# ===========================================================================
# Brief — v2 refinement
# ===========================================================================

class TestBriefV2:
    def _v1(self, artifacts_dir):
        return handle_write_brief(make_brief_input())

    def test_version_increments_by_1(self, artifacts_dir):
        v1 = self._v1(artifacts_dir)
        v2 = handle_write_brief(make_brief_input(), existing_brief=v1)
        assert v2["version"] == 2

    def test_parent_version_points_to_prior(self, artifacts_dir):
        v1 = self._v1(artifacts_dir)
        v2 = handle_write_brief(make_brief_input(), existing_brief=v1)
        assert v2["parent_version"] == 1

    def test_updated_at_changes(self, artifacts_dir):
        v1 = self._v1(artifacts_dir)
        v2 = handle_write_brief(make_brief_input(), existing_brief=v1)
        assert v2["updated_at"] >= v1["updated_at"]

    def test_decision_log_grows_by_one(self, artifacts_dir):
        v1_inp = make_brief_input()
        v1_inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "v1", "changed_fields": []}
        v1 = handle_write_brief(v1_inp)

        v2_inp = make_brief_input()
        v2_inp["decision_log_entry"] = {"trigger": "human_feedback", "summary": "v2", "changed_fields": ["chosen_direction"]}
        v2 = handle_write_brief(v2_inp, existing_brief=v1)

        assert len(v2["decision_log"]) == 2
        assert v2["decision_log"][1]["version"] == 2

    def test_three_version_chain(self, artifacts_dir):
        v1 = handle_write_brief(make_brief_input())
        v2 = handle_write_brief(make_brief_input(), existing_brief=v1)
        v3 = handle_write_brief(make_brief_input(), existing_brief=v2)
        assert v3["version"] == 3
        assert v3["parent_version"] == 2

    def test_v2_file_written_to_disk(self, artifacts_dir):
        v1 = self._v1(artifacts_dir)
        handle_write_brief(make_brief_input(), existing_brief=v1)
        assert (artifacts_dir / "test-project" / "brief" / "v2.json").exists()


# ===========================================================================
# Brief — approval
# ===========================================================================

class TestApproveBrief:
    def _write_and_approve(self, artifacts_dir):
        handle_write_brief(make_brief_input())
        path = str(artifacts_dir / "test-project" / "brief" / "v1.json")
        return handle_approve_brief(path), path

    def test_status_set_to_approved(self, artifacts_dir):
        approved, _ = self._write_and_approve(artifacts_dir)
        assert approved["status"] == "approved"

    def test_updated_at_refreshed(self, artifacts_dir):
        v1 = handle_write_brief(make_brief_input())
        path = str(artifacts_dir / "test-project" / "brief" / "v1.json")
        approved = handle_approve_brief(path)
        assert approved["updated_at"] >= v1["updated_at"]

    def test_approval_entry_author_is_human(self, artifacts_dir):
        approved, _ = self._write_and_approve(artifacts_dir)
        assert approved["decision_log"][-1]["author"] == "human"

    def test_approval_entry_trigger(self, artifacts_dir):
        approved, _ = self._write_and_approve(artifacts_dir)
        assert approved["decision_log"][-1]["trigger"] == "approval"

    def test_version_unchanged_on_approval(self, artifacts_dir):
        approved, _ = self._write_and_approve(artifacts_dir)
        assert approved["version"] == 1

    def test_approval_persisted_to_disk(self, artifacts_dir):
        _, path = self._write_and_approve(artifacts_dir)
        on_disk = json.loads(Path(path).read_text())
        assert on_disk["status"] == "approved"

    def test_approve_rejects_missing_file(self, artifacts_dir):
        with pytest.raises(ValueError, match="artifact not found"):
            handle_approve_brief(str(artifacts_dir / "ghost" / "brief" / "v1.json"))

    def test_approve_rejects_already_approved(self, artifacts_dir):
        _, path = self._write_and_approve(artifacts_dir)
        with pytest.raises(ValueError, match="already approved"):
            handle_approve_brief(path)

    def test_approve_rejects_path_outside_artifacts_dir(self, artifacts_dir):
        with pytest.raises(ValueError, match="outside the artifacts directory"):
            handle_approve_brief("/etc/passwd")


# ===========================================================================
# Design — v1 creation
# ===========================================================================

class TestDesignV1:
    def test_id_has_design_prefix(self, design_artifacts_dir):
        assert handle_write_design(make_design_input())["id"].startswith("design-")

    def test_version_is_1(self, design_artifacts_dir):
        assert handle_write_design(make_design_input())["version"] == 1

    def test_parent_version_is_none(self, design_artifacts_dir):
        assert handle_write_design(make_design_input())["parent_version"] is None

    def test_created_at_and_updated_at_set(self, design_artifacts_dir):
        a = handle_write_design(make_design_input())
        assert a["created_at"]
        assert a["updated_at"]

    def test_references_contains_upstream_domain(self, design_artifacts_dir):
        a = handle_write_design(make_design_input())
        assert len(a["references"]) == 1
        assert a["references"][0].endswith("test-project/model_domain/v1.json")

    def test_decision_log_empty_when_no_entry(self, design_artifacts_dir):
        assert handle_write_design(make_design_input())["decision_log"] == []

    def test_decision_log_entry_appended_with_metadata(self, design_artifacts_dir):
        inp = make_design_input()
        inp["decision_log_entry"] = {
            "trigger": "initial_draft", "summary": "Initial design", "changed_fields": ["layering_strategy"],
        }
        a = handle_write_design(inp)
        assert len(a["decision_log"]) == 1
        entry = a["decision_log"][0]
        assert entry["version"] == 1
        assert entry["author"] == "agent:architecture-agent"
        assert entry["trigger"] == "initial_draft"
        assert entry["timestamp"]

    def test_content_fields_present(self, design_artifacts_dir):
        a = handle_write_design(make_design_input())
        for key in ("layering_strategy", "aggregate_consistency", "integration_patterns",
                    "storage", "cross_cutting", "testing_strategy", "nfrs", "open_questions"):
            assert key in a["content"]

    def test_file_written_to_correct_path(self, design_artifacts_dir):
        handle_write_design(make_design_input(slug="my-app"))
        assert (design_artifacts_dir / "my-app" / "design" / "v1.json").exists()

    def test_file_is_valid_json(self, design_artifacts_dir):
        handle_write_design(make_design_input(slug="my-app"))
        raw = (design_artifacts_dir / "my-app" / "design" / "v1.json").read_text()
        parsed = json.loads(raw)
        assert parsed["version"] == 1

    def test_status_is_draft(self, design_artifacts_dir):
        assert handle_write_design(make_design_input())["status"] == "draft"


# ===========================================================================
# Design — v2 refinement
# ===========================================================================

class TestDesignV2:
    def _v1(self, design_artifacts_dir):
        return handle_write_design(make_design_input())

    def test_version_increments_by_1(self, design_artifacts_dir):
        v1 = self._v1(design_artifacts_dir)
        v2 = handle_write_design(make_design_input(), existing_design=v1)
        assert v2["version"] == 2

    def test_parent_version_points_to_prior(self, design_artifacts_dir):
        v1 = self._v1(design_artifacts_dir)
        v2 = handle_write_design(make_design_input(), existing_design=v1)
        assert v2["parent_version"] == 1

    def test_id_stable(self, design_artifacts_dir):
        v1 = self._v1(design_artifacts_dir)
        v2 = handle_write_design(make_design_input(), existing_design=v1)
        assert v2["id"] == v1["id"]

    def test_created_at_unchanged(self, design_artifacts_dir):
        v1 = self._v1(design_artifacts_dir)
        v2 = handle_write_design(make_design_input(), existing_design=v1)
        assert v2["created_at"] == v1["created_at"]

    def test_updated_at_changes(self, design_artifacts_dir):
        v1 = self._v1(design_artifacts_dir)
        v2 = handle_write_design(make_design_input(), existing_design=v1)
        assert v2["updated_at"] >= v1["updated_at"]

    def test_decision_log_grows_by_one(self, design_artifacts_dir):
        v1_inp = make_design_input()
        v1_inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "v1", "changed_fields": []}
        v1 = handle_write_design(v1_inp)

        v2_inp = make_design_input()
        v2_inp["decision_log_entry"] = {"trigger": "human_feedback", "summary": "v2", "changed_fields": ["layering_strategy"]}
        v2 = handle_write_design(v2_inp, existing_design=v1)

        assert len(v2["decision_log"]) == 2
        assert v2["decision_log"][1]["version"] == 2

    def test_three_version_chain(self, design_artifacts_dir):
        v1 = handle_write_design(make_design_input())
        v2 = handle_write_design(make_design_input(), existing_design=v1)
        v3 = handle_write_design(make_design_input(), existing_design=v2)
        assert v3["version"] == 3
        assert v3["parent_version"] == 2

    def test_v2_file_written_to_disk(self, design_artifacts_dir):
        v1 = self._v1(design_artifacts_dir)
        handle_write_design(make_design_input(), existing_design=v1)
        assert (design_artifacts_dir / "test-project" / "design" / "v2.json").exists()


# ===========================================================================
# Design — approval
# ===========================================================================

class TestApproveDesign:
    def _write_and_approve(self, design_artifacts_dir):
        handle_write_design(make_design_input())
        path = str(design_artifacts_dir / "test-project" / "design" / "v1.json")
        return handle_approve_design(path), path

    def test_status_set_to_approved(self, design_artifacts_dir):
        approved, _ = self._write_and_approve(design_artifacts_dir)
        assert approved["status"] == "approved"

    def test_updated_at_refreshed(self, design_artifacts_dir):
        v1 = handle_write_design(make_design_input())
        path = str(design_artifacts_dir / "test-project" / "design" / "v1.json")
        approved = handle_approve_design(path)
        assert approved["updated_at"] >= v1["updated_at"]

    def test_approval_entry_author_is_human(self, design_artifacts_dir):
        approved, _ = self._write_and_approve(design_artifacts_dir)
        assert approved["decision_log"][-1]["author"] == "human"

    def test_approval_entry_trigger(self, design_artifacts_dir):
        approved, _ = self._write_and_approve(design_artifacts_dir)
        assert approved["decision_log"][-1]["trigger"] == "approval"

    def test_version_unchanged_on_approval(self, design_artifacts_dir):
        approved, _ = self._write_and_approve(design_artifacts_dir)
        assert approved["version"] == 1

    def test_approval_persisted_to_disk(self, design_artifacts_dir):
        _, path = self._write_and_approve(design_artifacts_dir)
        on_disk = json.loads(Path(path).read_text())
        assert on_disk["status"] == "approved"

    def test_approve_rejects_missing_file(self, design_artifacts_dir):
        with pytest.raises(ValueError, match="artifact not found"):
            handle_approve_design(str(design_artifacts_dir / "ghost" / "design" / "v1.json"))

    def test_approve_rejects_already_approved(self, design_artifacts_dir):
        _, path = self._write_and_approve(design_artifacts_dir)
        with pytest.raises(ValueError, match="already approved"):
            handle_approve_design(path)

    def test_approve_rejects_path_outside_artifacts_dir(self, design_artifacts_dir):
        with pytest.raises(ValueError, match="outside the artifacts directory"):
            handle_approve_design("/etc/passwd")


# ===========================================================================
# Tech Stack — v1 creation
# ===========================================================================

class TestTechStackV1:
    def test_id_has_tech_stack_prefix(self, tech_stack_artifacts_dir):
        assert handle_write_tech_stack(make_tech_stack_input())["id"].startswith("tech-stack-")

    def test_version_is_1(self, tech_stack_artifacts_dir):
        assert handle_write_tech_stack(make_tech_stack_input())["version"] == 1

    def test_parent_version_is_none(self, tech_stack_artifacts_dir):
        assert handle_write_tech_stack(make_tech_stack_input())["parent_version"] is None

    def test_created_at_and_updated_at_set(self, tech_stack_artifacts_dir):
        a = handle_write_tech_stack(make_tech_stack_input())
        assert a["created_at"]
        assert a["updated_at"]

    def test_references_contains_upstream_design(self, tech_stack_artifacts_dir):
        a = handle_write_tech_stack(make_tech_stack_input())
        assert len(a["references"]) == 1
        assert a["references"][0].endswith("test-project/design/v1.json")

    def test_status_is_draft(self, tech_stack_artifacts_dir):
        assert handle_write_tech_stack(make_tech_stack_input())["status"] == "draft"

    def test_decision_log_empty_when_no_entry(self, tech_stack_artifacts_dir):
        assert handle_write_tech_stack(make_tech_stack_input())["decision_log"] == []

    def test_decision_log_entry_appended_with_metadata(self, tech_stack_artifacts_dir):
        inp = make_tech_stack_input()
        inp["decision_log_entry"] = {
            "trigger": "initial_draft",
            "summary": "All ADRs resolved via deliberation",
            "changed_fields": ["adrs"],
        }
        a = handle_write_tech_stack(inp)
        assert len(a["decision_log"]) == 1
        entry = a["decision_log"][0]
        assert entry["version"] == 1
        assert entry["author"] == "agent:tech-stack-agent"
        assert entry["trigger"] == "initial_draft"
        assert entry["summary"] == "All ADRs resolved via deliberation"
        assert entry["timestamp"]

    def test_content_fields_present(self, tech_stack_artifacts_dir):
        a = handle_write_tech_stack(make_tech_stack_input())
        assert "adrs" in a["content"]
        assert "open_questions" in a["content"]

    def test_adr_fields_stored(self, tech_stack_artifacts_dir):
        a = handle_write_tech_stack(make_tech_stack_input())
        adr = a["content"]["adrs"][0]
        for field in ("decision_point", "architectural_signal", "candidates",
                      "constraints_surfaced", "chosen", "rationale", "rejections"):
            assert field in adr

    def test_file_written_to_correct_path(self, tech_stack_artifacts_dir):
        handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        assert (tech_stack_artifacts_dir / "my-app" / "tech_stack" / "v1.json").exists()

    def test_file_is_valid_json(self, tech_stack_artifacts_dir):
        handle_write_tech_stack(make_tech_stack_input(slug="my-app"))
        raw = (tech_stack_artifacts_dir / "my-app" / "tech_stack" / "v1.json").read_text()
        parsed = json.loads(raw)
        assert parsed["version"] == 1


# ===========================================================================
# Tech Stack — v2 refinement
# ===========================================================================

class TestTechStackV2:
    def _v1(self, tech_stack_artifacts_dir):
        return handle_write_tech_stack(make_tech_stack_input())

    def test_version_increments_by_1(self, tech_stack_artifacts_dir):
        v1 = self._v1(tech_stack_artifacts_dir)
        v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
        assert v2["version"] == 2

    def test_parent_version_points_to_prior(self, tech_stack_artifacts_dir):
        v1 = self._v1(tech_stack_artifacts_dir)
        v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
        assert v2["parent_version"] == 1

    def test_id_stable(self, tech_stack_artifacts_dir):
        v1 = self._v1(tech_stack_artifacts_dir)
        v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
        assert v2["id"] == v1["id"]

    def test_created_at_unchanged(self, tech_stack_artifacts_dir):
        v1 = self._v1(tech_stack_artifacts_dir)
        v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
        assert v2["created_at"] == v1["created_at"]

    def test_updated_at_changes(self, tech_stack_artifacts_dir):
        v1 = self._v1(tech_stack_artifacts_dir)
        v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
        assert v2["updated_at"] >= v1["updated_at"]

    def test_references_carried_forward(self, tech_stack_artifacts_dir):
        v1 = self._v1(tech_stack_artifacts_dir)
        v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
        assert v2["references"] == v1["references"]

    def test_decision_log_grows_by_one(self, tech_stack_artifacts_dir):
        v1_inp = make_tech_stack_input()
        v1_inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "v1", "changed_fields": ["adrs"]}
        v1 = handle_write_tech_stack(v1_inp)

        v2_inp = make_tech_stack_input()
        v2_inp["decision_log_entry"] = {"trigger": "scope_change", "summary": "re-opened API framework decision", "changed_fields": ["adrs"]}
        v2 = handle_write_tech_stack(v2_inp, existing_tech_stack=v1)

        assert len(v2["decision_log"]) == 2
        assert v2["decision_log"][1]["version"] == 2

    def test_three_version_chain(self, tech_stack_artifacts_dir):
        v1 = handle_write_tech_stack(make_tech_stack_input())
        v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
        v3 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v2)
        assert v3["version"] == 3
        assert v3["parent_version"] == 2

    def test_v2_file_written_to_disk(self, tech_stack_artifacts_dir):
        v1 = self._v1(tech_stack_artifacts_dir)
        handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
        assert (tech_stack_artifacts_dir / "test-project" / "tech_stack" / "v2.json").exists()


# ===========================================================================
# Tech Stack — approval
# ===========================================================================

class TestApproveTechStack:
    def _write_and_approve(self, tech_stack_artifacts_dir):
        handle_write_tech_stack(make_tech_stack_input())
        path = str(tech_stack_artifacts_dir / "test-project" / "tech_stack" / "v1.json")
        return handle_approve_tech_stack(path), path

    def test_status_set_to_approved(self, tech_stack_artifacts_dir):
        approved, _ = self._write_and_approve(tech_stack_artifacts_dir)
        assert approved["status"] == "approved"

    def test_updated_at_refreshed(self, tech_stack_artifacts_dir):
        v1 = handle_write_tech_stack(make_tech_stack_input())
        path = str(tech_stack_artifacts_dir / "test-project" / "tech_stack" / "v1.json")
        approved = handle_approve_tech_stack(path)
        assert approved["updated_at"] >= v1["updated_at"]

    def test_approval_entry_author_is_human(self, tech_stack_artifacts_dir):
        approved, _ = self._write_and_approve(tech_stack_artifacts_dir)
        assert approved["decision_log"][-1]["author"] == "human"

    def test_approval_entry_trigger(self, tech_stack_artifacts_dir):
        approved, _ = self._write_and_approve(tech_stack_artifacts_dir)
        assert approved["decision_log"][-1]["trigger"] == "approval"

    def test_version_unchanged_on_approval(self, tech_stack_artifacts_dir):
        approved, _ = self._write_and_approve(tech_stack_artifacts_dir)
        assert approved["version"] == 1

    def test_approval_persisted_to_disk(self, tech_stack_artifacts_dir):
        _, path = self._write_and_approve(tech_stack_artifacts_dir)
        on_disk = json.loads(Path(path).read_text())
        assert on_disk["status"] == "approved"

    def test_approve_rejects_missing_file(self, tech_stack_artifacts_dir):
        with pytest.raises(ValueError, match="artifact not found"):
            handle_approve_tech_stack(str(tech_stack_artifacts_dir / "ghost" / "tech_stack" / "v1.json"))

    def test_approve_rejects_already_approved(self, tech_stack_artifacts_dir):
        _, path = self._write_and_approve(tech_stack_artifacts_dir)
        with pytest.raises(ValueError, match="already approved"):
            handle_approve_tech_stack(path)

    def test_approve_rejects_path_outside_artifacts_dir(self, tech_stack_artifacts_dir):
        with pytest.raises(ValueError, match="outside the artifacts directory"):
            handle_approve_tech_stack("/etc/passwd")


# ---------------------------------------------------------------------------
# Step 3 — Instance schema lifecycle
# ---------------------------------------------------------------------------

class TestInstanceSchema:
    """
    Verifies that _ensure_instance_schema creates a schema.json from the base
    schema on first call, and that handle_update_schema correctly extends it.
    """

    pytestmark = pytest.mark.lifecycle

    def test_schema_created_from_base_for_model_domain(self, artifacts_dir):
        (artifacts_dir / "my-app" / "model_domain").mkdir(parents=True)
        _ensure_instance_schema("my-app", "model_domain")
        schema_path = artifacts_dir / "my-app" / "model_domain" / "schema.json"
        assert schema_path.exists()
        schema = json.loads(schema_path.read_text())
        assert "bounded_contexts" in schema["fields"]
        assert schema["fields"]["bounded_contexts"]["kind"] == "mandatory"

    def test_schema_idempotent_on_repeat_calls(self, artifacts_dir):
        (artifacts_dir / "my-app" / "model_domain").mkdir(parents=True)
        _ensure_instance_schema("my-app", "model_domain")
        _ensure_instance_schema("my-app", "model_domain")  # second call must not overwrite
        schema_path = artifacts_dir / "my-app" / "model_domain" / "schema.json"
        assert schema_path.exists()

    def test_empty_schema_for_stage_with_no_base(self, artifacts_dir):
        (artifacts_dir / "my-app" / "brief").mkdir(parents=True)
        _ensure_instance_schema("my-app", "brief")
        schema = json.loads((artifacts_dir / "my-app" / "brief" / "schema.json").read_text())
        assert schema == {"fields": {}}

    def test_update_schema_adds_field(self, artifacts_dir):
        (artifacts_dir / "my-app" / "model_domain").mkdir(parents=True)
        _ensure_instance_schema("my-app", "model_domain")
        handle_update_schema("my-app", "model_domain", "risk_drivers", "optional", "Key risks that shape the model")
        schema_path = artifacts_dir / "my-app" / "model_domain" / "schema.json"
        schema = json.loads(schema_path.read_text())
        assert "risk_drivers" in schema["fields"]
        assert schema["fields"]["risk_drivers"]["kind"] == "optional"

    def test_update_schema_appends_decision_log(self, artifacts_dir):
        (artifacts_dir / "my-app" / "model_domain").mkdir(parents=True)
        _ensure_instance_schema("my-app", "model_domain")
        handle_update_schema("my-app", "model_domain", "risk_drivers", "optional", "Key risks")
        schema = json.loads((artifacts_dir / "my-app" / "model_domain" / "schema.json").read_text())
        assert len(schema["decision_log"]) == 1
        assert schema["decision_log"][0]["trigger"] == "schema_field_added"
        assert schema["decision_log"][0]["field_name"] == "risk_drivers"


# ---------------------------------------------------------------------------
# Step 4 — Model artifact lifecycle
# ---------------------------------------------------------------------------

import pytest

class TestModelV1:
    """v1 write for all four model types."""

    pytestmark = pytest.mark.lifecycle

    @pytest.mark.parametrize("model_type,archetype", [
        ("domain",    "domain_system"),
        ("data_flow", "data_pipeline"),
        ("system",    "system_integration"),
        ("workflow",  "process_system"),
    ])
    def test_v1_creates_artifact_file(self, prd_artifacts_dir, model_type, archetype):
        from tool_handler import handle_write_model
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype=archetype))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        artifact = handle_write_model(make_model_input(slug="my-app", model_type=model_type))
        stage = f"model_{model_type}"
        assert (prd_artifacts_dir / "my-app" / stage / "v1.json").exists()
        assert artifact["version"] == 1
        assert artifact["model_type"] == model_type
        assert artifact["status"] == "draft"

    @pytest.mark.parametrize("model_type,archetype", [
        ("domain",    "domain_system"),
        ("data_flow", "data_pipeline"),
        ("system",    "system_integration"),
        ("workflow",  "process_system"),
    ])
    def test_v1_creates_schema_file(self, prd_artifacts_dir, model_type, archetype):
        from tool_handler import handle_write_model
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype=archetype))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        handle_write_model(make_model_input(slug="my-app", model_type=model_type))
        stage = f"model_{model_type}"
        schema_path = prd_artifacts_dir / "my-app" / stage / "schema.json"
        assert schema_path.exists()
        schema = json.loads(schema_path.read_text())
        assert "fields" in schema

    def test_v1_references_approved_prd(self, prd_artifacts_dir):
        from tool_handler import handle_write_model
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        artifact = handle_write_model(make_model_input(slug="my-app", model_type="domain"))
        assert len(artifact["references"]) == 1
        assert "prd" in artifact["references"][0]

    def test_layered_workflow_references_approved_model_system(self, prd_artifacts_dir):
        """In layered topology, model_workflow v1 references model_system, not prd."""
        from tool_handler import handle_write_model, handle_approve_model
        handle_write_prd(make_prd_input(
            slug="my-app",
            primary_archetype="system_integration",
            secondary_archetype="process_system",
        ))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        handle_write_model(make_model_input(slug="my-app", model_type="system"))
        handle_approve_model(str(prd_artifacts_dir / "my-app" / "model_system" / "v1.json"))
        artifact = handle_write_model(make_model_input(slug="my-app", model_type="workflow"))
        assert len(artifact["references"]) == 1
        assert "model_system" in artifact["references"][0]


class TestApproveModel:
    """Approval gate: mandatory field validation."""

    pytestmark = pytest.mark.lifecycle

    def test_approve_succeeds_with_all_mandatory_fields(self, prd_artifacts_dir):
        from tool_handler import handle_write_model, handle_approve_model
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        handle_write_model(make_model_input(slug="my-app", model_type="domain"))
        artifact = handle_approve_model(str(prd_artifacts_dir / "my-app" / "model_domain" / "v1.json"))
        assert artifact["status"] == "approved"

    def test_approve_adds_decision_log_entry(self, prd_artifacts_dir):
        from tool_handler import handle_write_model, handle_approve_model
        handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
        handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
        handle_write_model(make_model_input(slug="my-app", model_type="domain"))
        artifact = handle_approve_model(str(prd_artifacts_dir / "my-app" / "model_domain" / "v1.json"))
        approval_entry = artifact["decision_log"][-1]
        assert approval_entry["trigger"] == "approval"
        assert approval_entry["author"] == "human"
