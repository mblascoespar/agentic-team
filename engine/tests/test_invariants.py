"""
Invariant tests — orchestrator field ownership and input validation.

Two categories:

1. Field ownership: the handler, not the agent, controls all metadata fields.
   An agent-provided value for any of these fields on v2+ must be silently
   ignored in favour of the value locked in the existing artifact.

2. Input validation: the engine rejects corrupt inputs before any file write.
   Every validation check raises ValueError with an actionable message.

Fields under ownership test: id, slug, created_at, source_idea (PRD),
references, status, content isolation.

Run this suite alone:  pytest -m invariant
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_handler import (
    handle_write_prd, handle_approve_prd,
    handle_write_domain_model, handle_write_brief, handle_write_design, handle_write_tech_stack,
    handle_write_model, handle_approve_model,
    handle_update_schema, _ensure_instance_schema,
)
from conftest import make_prd_input, make_domain_input, make_brief_input, make_design_input, make_tech_stack_input, make_model_input

pytestmark = pytest.mark.invariant


# ---------------------------------------------------------------------------
# PRD — id
# ---------------------------------------------------------------------------

def test_prd_id_stable_across_versions(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input())
    v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
    assert v1["id"] == v2["id"]


def test_prd_id_not_influenced_by_agent_on_v2(prd_artifacts_dir):
    """Injecting an id field is rejected by schema validation (additionalProperties: false)."""
    v1 = handle_write_prd(make_prd_input())
    inp = make_prd_input()
    inp["id"] = "prd-injected"
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp, existing_prd=v1)


# ---------------------------------------------------------------------------
# PRD — slug
# ---------------------------------------------------------------------------

def test_prd_slug_locked_after_v1(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input(slug="original-slug"))
    v2 = handle_write_prd(make_prd_input(slug="attacker-slug"), existing_prd=v1)
    assert v2["slug"] == "original-slug"


def test_prd_slug_change_does_not_create_new_folder(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input(slug="original-slug"))
    handle_write_prd(make_prd_input(slug="attacker-slug"), existing_prd=v1)
    assert (prd_artifacts_dir / "original-slug" / "prd" / "v2.json").exists()
    assert not (prd_artifacts_dir / "attacker-slug" / "prd" / "v2.json").exists()


# ---------------------------------------------------------------------------
# PRD — created_at
# ---------------------------------------------------------------------------

def test_prd_created_at_immutable_on_v2(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input())
    v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
    assert v2["created_at"] == v1["created_at"]


def test_prd_created_at_immutable_across_three_versions(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input())
    v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
    v3 = handle_write_prd(make_prd_input(), existing_prd=v2)
    assert v3["created_at"] == v1["created_at"]


# ---------------------------------------------------------------------------
# PRD — source_idea
# ---------------------------------------------------------------------------

def test_prd_source_idea_immutable_on_v2(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input(source_idea="Original idea"))
    v2 = handle_write_prd(make_prd_input(source_idea="Hijacked idea"), existing_prd=v1)
    assert v2["source_idea"] == "Original idea"


# ---------------------------------------------------------------------------
# PRD — status always draft on write
# ---------------------------------------------------------------------------

def test_prd_status_always_draft_on_v1(prd_artifacts_dir):
    assert handle_write_prd(make_prd_input())["status"] == "draft"


def test_prd_status_always_draft_on_v2(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input())
    assert handle_write_prd(make_prd_input(), existing_prd=v1)["status"] == "draft"


# ---------------------------------------------------------------------------
# PRD — references populated from upstream Brief on v1; carried forward on v2+
# ---------------------------------------------------------------------------

def test_prd_references_contains_upstream_brief_on_v1(prd_artifacts_dir):
    a = handle_write_prd(make_prd_input())
    assert len(a["references"]) == 1
    assert a["references"][0].endswith("test-project/brief/v1.json")


def test_prd_references_carried_forward_on_v2(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input())
    v2 = handle_write_prd(make_prd_input(), existing_prd=v1)
    assert v2["references"] == v1["references"]


# ---------------------------------------------------------------------------
# PRD — content isolation: no orchestrator field leaks in
# ---------------------------------------------------------------------------

def test_prd_content_contains_only_whitelisted_keys(prd_artifacts_dir):
    from tool_handler import _PRD_CONTENT_KEYS
    artifact = handle_write_prd(make_prd_input())
    assert set(artifact["content"].keys()) <= set(_PRD_CONTENT_KEYS)


def test_prd_orchestrator_fields_not_in_content(prd_artifacts_dir):
    orchestrator = {"id", "slug", "version", "parent_version", "created_at",
                    "updated_at", "status", "references", "decision_log", "source_idea"}
    artifact = handle_write_prd(make_prd_input())
    assert orchestrator.isdisjoint(artifact["content"].keys())


def test_prd_decision_log_entry_not_in_content(prd_artifacts_dir):
    inp = make_prd_input()
    inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "x", "changed_fields": []}
    artifact = handle_write_prd(inp)
    assert "decision_log_entry" not in artifact["content"]


# ---------------------------------------------------------------------------
# PRD — input validation (schema / slug — fail before find_latest)
# ---------------------------------------------------------------------------

def test_prd_write_rejects_missing_slug(artifacts_dir):
    inp = make_prd_input()
    del inp["slug"]
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_write_rejects_invalid_slug_traversal(artifacts_dir):
    with pytest.raises(ValueError, match="slug.*invalid"):
        handle_write_prd(make_prd_input(slug="../../etc"))


def test_prd_write_rejects_invalid_slug_spaces(artifacts_dir):
    with pytest.raises(ValueError, match="slug.*invalid"):
        handle_write_prd(make_prd_input(slug="my app"))


def test_prd_write_rejects_missing_title(artifacts_dir):
    inp = make_prd_input()
    del inp["title"]
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_write_rejects_missing_problem(artifacts_dir):
    inp = make_prd_input()
    del inp["problem"]
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_write_rejects_empty_target_users(artifacts_dir):
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(make_prd_input(target_users=[]))


def test_prd_write_rejects_empty_features(artifacts_dir):
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(make_prd_input(features=[]))


def test_prd_write_rejects_invalid_feature_priority(artifacts_dir):
    inp = make_prd_input(features=[{
        "name": "X", "description": "Y", "user_story": "Z", "priority": "urgent"
    }])
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_write_rejects_missing_success_metrics(artifacts_dir):
    inp = make_prd_input()
    del inp["success_metrics"]
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_write_rejects_success_metric_missing_measurement_method(artifacts_dir):
    inp = make_prd_input(success_metrics=[{"metric": "Deploy time"}])
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_write_rejects_missing_scope_in(artifacts_dir):
    inp = make_prd_input()
    del inp["scope_in"]
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_v1_fails_without_approved_brief(artifacts_dir):
    """Engine gate: write_prd v1 raises ValueError when no approved Brief exists."""
    with pytest.raises(ValueError, match="no approved Brief"):
        handle_write_prd(make_prd_input(slug="no-brief-here"))


# ---------------------------------------------------------------------------
# PRD — archetype: validation, locking, content presence
# ---------------------------------------------------------------------------

def test_prd_write_rejects_missing_primary_archetype(artifacts_dir):
    inp = make_prd_input()
    del inp["primary_archetype"]
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_write_rejects_invalid_primary_archetype(artifacts_dir):
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(make_prd_input(primary_archetype="magic_system"))


def test_prd_write_rejects_missing_archetype_reasoning(artifacts_dir):
    inp = make_prd_input()
    del inp["archetype_reasoning"]
    with pytest.raises(ValueError, match="ERROR \\[write_prd\\]"):
        handle_write_prd(inp)


def test_prd_write_rejects_unsupported_archetype_combination(prd_artifacts_dir):
    """data_pipeline + process_system is not a valid combination."""
    with pytest.raises(ValueError, match="unsupported archetype combination"):
        handle_write_prd(make_prd_input(
            slug="test-pipeline",
            primary_archetype="data_pipeline",
            secondary_archetype="process_system",
        ))


@pytest.mark.parametrize("slug,archetype", [
    ("test-pipeline",    "data_pipeline"),
    ("test-integration", "system_integration"),
    ("test-workflow",    "process_system"),
])
def test_prd_write_accepts_valid_single_archetype(prd_artifacts_dir, slug, archetype):
    artifact = handle_write_prd(make_prd_input(slug=slug, primary_archetype=archetype))
    assert artifact["content"]["primary_archetype"] == archetype


def test_prd_write_accepts_valid_layered_combination(prd_artifacts_dir):
    artifact = handle_write_prd(make_prd_input(
        slug="test-layered",
        primary_archetype="system_integration",
        secondary_archetype="process_system",
    ))
    assert artifact["content"]["primary_archetype"] == "system_integration"
    assert artifact["content"]["secondary_archetype"] == "process_system"


def test_prd_archetype_locked_on_v1_primary_cannot_change(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input(primary_archetype="domain_system"))
    v2 = handle_write_prd(
        make_prd_input(primary_archetype="data_pipeline"),
        existing_prd=v1,
    )
    assert v2["content"]["primary_archetype"] == "domain_system"


def test_prd_archetype_locked_on_v1_reasoning_cannot_change(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input(archetype_reasoning="Original reasoning."))
    v2 = handle_write_prd(
        make_prd_input(archetype_reasoning="Agent tries to change this."),
        existing_prd=v1,
    )
    assert v2["content"]["archetype_reasoning"] == "Original reasoning."


def test_prd_archetype_confidence_optional_does_not_raise(prd_artifacts_dir):
    """Omitting archetype_confidence on v1 must not cause a KeyError."""
    inp = make_prd_input()
    inp.pop("archetype_confidence", None)
    artifact = handle_write_prd(inp)
    assert "primary_archetype" in artifact["content"]
    assert "archetype_confidence" not in artifact["content"]


def test_prd_archetype_locked_across_three_versions(prd_artifacts_dir):
    v1 = handle_write_prd(make_prd_input(primary_archetype="domain_system"))
    v2 = handle_write_prd(make_prd_input(primary_archetype="data_pipeline"), existing_prd=v1)
    v3 = handle_write_prd(make_prd_input(primary_archetype="process_system"), existing_prd=v2)
    assert v3["content"]["primary_archetype"] == "domain_system"


def test_prd_archetype_secondary_cannot_be_added_on_v2(prd_artifacts_dir):
    """Agent cannot inject secondary_archetype on v2 if it was absent from v1."""
    v1 = handle_write_prd(make_prd_input(primary_archetype="domain_system"))
    assert "secondary_archetype" not in v1["content"]
    v2 = handle_write_prd(
        make_prd_input(primary_archetype="domain_system", secondary_archetype="process_system"),
        existing_prd=v1,
    )
    assert "secondary_archetype" not in v2["content"]


# ---------------------------------------------------------------------------
# Domain model — id
# ---------------------------------------------------------------------------

def test_domain_id_stable_across_versions(domain_artifacts_dir):
    v1 = handle_write_domain_model(make_domain_input())
    v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
    assert v1["id"] == v2["id"]


def test_domain_id_not_influenced_by_agent_on_v2(domain_artifacts_dir):
    """Injecting an id field is rejected by schema validation (additionalProperties: false)."""
    v1 = handle_write_domain_model(make_domain_input())
    inp = make_domain_input()
    inp["id"] = "domain-injected"
    with pytest.raises(ValueError, match="ERROR \\[write_domain_model\\]"):
        handle_write_domain_model(inp, existing_domain=v1)


# ---------------------------------------------------------------------------
# Domain model — slug
# ---------------------------------------------------------------------------

def test_domain_slug_locked_after_v1(domain_artifacts_dir):
    v1 = handle_write_domain_model(make_domain_input(slug="original-slug"))
    v2 = handle_write_domain_model(make_domain_input(slug="attacker-slug"), existing_domain=v1)
    assert v2["slug"] == "original-slug"


def test_domain_slug_change_does_not_create_new_folder(domain_artifacts_dir):
    v1 = handle_write_domain_model(make_domain_input(slug="original-slug"))
    handle_write_domain_model(make_domain_input(slug="attacker-slug"), existing_domain=v1)
    assert (domain_artifacts_dir / "original-slug" / "domain" / "v2.json").exists()
    assert not (domain_artifacts_dir / "attacker-slug" / "domain" / "v2.json").exists()


# ---------------------------------------------------------------------------
# Domain model — created_at
# ---------------------------------------------------------------------------

def test_domain_created_at_immutable_on_v2(domain_artifacts_dir):
    v1 = handle_write_domain_model(make_domain_input())
    v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
    assert v2["created_at"] == v1["created_at"]


def test_domain_created_at_immutable_across_three_versions(domain_artifacts_dir):
    v1 = handle_write_domain_model(make_domain_input())
    v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
    v3 = handle_write_domain_model(make_domain_input(), existing_domain=v2)
    assert v3["created_at"] == v1["created_at"]


# ---------------------------------------------------------------------------
# Domain model — references locked after v1 (engine-set on creation)
# ---------------------------------------------------------------------------

def test_domain_references_set_by_engine_on_v1(domain_artifacts_dir):
    v1 = handle_write_domain_model(make_domain_input())
    assert len(v1["references"]) == 1
    assert v1["references"][0].endswith("test-project/prd/v1.json")


def test_domain_references_locked_after_v1(domain_artifacts_dir):
    v1 = handle_write_domain_model(make_domain_input())
    v2 = handle_write_domain_model(make_domain_input(), existing_domain=v1)
    assert v2["references"] == v1["references"]


# ---------------------------------------------------------------------------
# Domain model — status always draft on write
# ---------------------------------------------------------------------------

def test_domain_status_always_draft_on_v1(domain_artifacts_dir):
    assert handle_write_domain_model(make_domain_input())["status"] == "draft"


def test_domain_status_always_draft_on_v2(domain_artifacts_dir):
    v1 = handle_write_domain_model(make_domain_input())
    assert handle_write_domain_model(make_domain_input(), existing_domain=v1)["status"] == "draft"


# ---------------------------------------------------------------------------
# Domain model — content isolation
# ---------------------------------------------------------------------------

def test_domain_orchestrator_fields_not_in_content(domain_artifacts_dir):
    orchestrator = {"id", "slug", "version", "parent_version", "created_at",
                    "updated_at", "status", "references", "decision_log"}
    artifact = handle_write_domain_model(make_domain_input())
    assert orchestrator.isdisjoint(artifact["content"].keys())


def test_domain_prd_path_not_in_content(domain_artifacts_dir):
    """prd_path is an engine-internal field and must never appear in artifact content."""
    artifact = handle_write_domain_model(make_domain_input())
    assert "prd_path" not in artifact["content"]


def test_domain_assumptions_stored_in_content(domain_artifacts_dir):
    artifact = handle_write_domain_model(make_domain_input(assumptions=["Payment is a separate context assuming future multi-currency support."]))
    assert "assumptions" in artifact["content"]
    assert len(artifact["content"]["assumptions"]) == 1


def test_domain_assumptions_separate_from_open_questions(domain_artifacts_dir):
    artifact = handle_write_domain_model(make_domain_input(
        assumptions=["Payment is a separate context."],
        open_questions=["Should rollback be manual?"],
    ))
    assert artifact["content"]["assumptions"] != artifact["content"]["open_questions"]


def test_domain_decision_log_entry_not_in_content(domain_artifacts_dir):
    inp = make_domain_input()
    inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "x", "changed_fields": []}
    artifact = handle_write_domain_model(inp)
    assert "decision_log_entry" not in artifact["content"]


# ---------------------------------------------------------------------------
# Domain model — input validation
# ---------------------------------------------------------------------------

def test_domain_write_rejects_missing_slug(domain_artifacts_dir):
    inp = make_domain_input()
    del inp["slug"]
    with pytest.raises(ValueError, match="ERROR \\[write_domain_model\\]"):
        handle_write_domain_model(inp)


def test_domain_write_rejects_invalid_slug(domain_artifacts_dir):
    with pytest.raises(ValueError, match="slug.*invalid"):
        handle_write_domain_model(make_domain_input(slug="../../etc"))


def test_domain_write_rejects_empty_bounded_contexts(domain_artifacts_dir):
    with pytest.raises(ValueError, match="ERROR \\[write_domain_model\\]"):
        handle_write_domain_model(make_domain_input(bounded_contexts=[]))


def test_domain_write_rejects_bounded_context_missing_name(domain_artifacts_dir):
    ctx = {
        "responsibility": "owns something",
        "aggregates": [], "commands": [], "queries": [], "events": [],
    }
    with pytest.raises(ValueError, match="ERROR \\[write_domain_model\\]"):
        handle_write_domain_model(make_domain_input(bounded_contexts=[ctx]))


def test_domain_write_rejects_invalid_context_map_relationship(domain_artifacts_dir):
    ctx_map = [{"upstream": "A", "downstream": "B", "relationship": "invalid-pattern"}]
    with pytest.raises(ValueError, match="ERROR \\[write_domain_model\\]"):
        handle_write_domain_model(make_domain_input(context_map=ctx_map))


def test_domain_write_rejects_missing_bounded_contexts(domain_artifacts_dir):
    inp = make_domain_input()
    del inp["bounded_contexts"]
    with pytest.raises(ValueError, match="ERROR \\[write_domain_model\\]"):
        handle_write_domain_model(inp)


def test_domain_v1_fails_without_approved_prd(prd_artifacts_dir):
    """Engine gate: write_domain_model v1 raises ValueError when no approved PRD exists."""
    with pytest.raises(ValueError, match="no approved PRD"):
        handle_write_domain_model(make_domain_input(slug="no-prd-here"))


# ---------------------------------------------------------------------------
# Brief — id
# ---------------------------------------------------------------------------

def test_brief_id_stable_across_versions(artifacts_dir):
    v1 = handle_write_brief(make_brief_input())
    v2 = handle_write_brief(make_brief_input(), existing_brief=v1)
    assert v1["id"] == v2["id"]


def test_brief_id_not_influenced_by_agent_on_v2(artifacts_dir):
    """Injecting an id field is rejected by schema validation (additionalProperties: false)."""
    v1 = handle_write_brief(make_brief_input())
    inp = make_brief_input()
    inp["id"] = "brief-injected"
    with pytest.raises(ValueError, match="ERROR \\[write_brief\\]"):
        handle_write_brief(inp, existing_brief=v1)


# ---------------------------------------------------------------------------
# Brief — slug
# ---------------------------------------------------------------------------

def test_brief_slug_locked_after_v1(artifacts_dir):
    v1 = handle_write_brief(make_brief_input(slug="original-slug"))
    v2 = handle_write_brief(make_brief_input(slug="attacker-slug"), existing_brief=v1)
    assert v2["slug"] == "original-slug"


def test_brief_slug_change_does_not_create_new_folder(artifacts_dir):
    v1 = handle_write_brief(make_brief_input(slug="original-slug"))
    handle_write_brief(make_brief_input(slug="attacker-slug"), existing_brief=v1)
    assert (artifacts_dir / "original-slug" / "brief" / "v2.json").exists()
    assert not (artifacts_dir / "attacker-slug" / "brief" / "v2.json").exists()


# ---------------------------------------------------------------------------
# Brief — created_at
# ---------------------------------------------------------------------------

def test_brief_created_at_immutable_on_v2(artifacts_dir):
    v1 = handle_write_brief(make_brief_input())
    v2 = handle_write_brief(make_brief_input(), existing_brief=v1)
    assert v2["created_at"] == v1["created_at"]


def test_brief_created_at_immutable_across_three_versions(artifacts_dir):
    v1 = handle_write_brief(make_brief_input())
    v2 = handle_write_brief(make_brief_input(), existing_brief=v1)
    v3 = handle_write_brief(make_brief_input(), existing_brief=v2)
    assert v3["created_at"] == v1["created_at"]


# ---------------------------------------------------------------------------
# Brief — idea locked after v1
# ---------------------------------------------------------------------------

def test_brief_idea_immutable_on_v2(artifacts_dir):
    v1 = handle_write_brief(make_brief_input(idea="Original idea text"))
    v2 = handle_write_brief(make_brief_input(idea="Hijacked idea text"), existing_brief=v1)
    assert v2["content"]["idea"] == "Original idea text"


# ---------------------------------------------------------------------------
# Brief — status always draft on write
# ---------------------------------------------------------------------------

def test_brief_status_always_draft_on_v1(artifacts_dir):
    assert handle_write_brief(make_brief_input())["status"] == "draft"


def test_brief_status_always_draft_on_v2(artifacts_dir):
    v1 = handle_write_brief(make_brief_input())
    assert handle_write_brief(make_brief_input(), existing_brief=v1)["status"] == "draft"


# ---------------------------------------------------------------------------
# Brief — references always empty (entry node)
# ---------------------------------------------------------------------------

def test_brief_references_always_empty_on_v1(artifacts_dir):
    assert handle_write_brief(make_brief_input())["references"] == []


def test_brief_references_always_empty_on_v2(artifacts_dir):
    v1 = handle_write_brief(make_brief_input())
    assert handle_write_brief(make_brief_input(), existing_brief=v1)["references"] == []


# ---------------------------------------------------------------------------
# Brief — content isolation
# ---------------------------------------------------------------------------

def test_brief_orchestrator_fields_not_in_content(artifacts_dir):
    orchestrator = {"id", "slug", "version", "parent_version", "created_at",
                    "updated_at", "status", "references", "decision_log"}
    artifact = handle_write_brief(make_brief_input())
    assert orchestrator.isdisjoint(artifact["content"].keys())


def test_brief_decision_log_entry_not_in_content(artifacts_dir):
    inp = make_brief_input()
    inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "x", "changed_fields": []}
    artifact = handle_write_brief(inp)
    assert "decision_log_entry" not in artifact["content"]


# ---------------------------------------------------------------------------
# Brief — input validation
# ---------------------------------------------------------------------------

def test_brief_write_rejects_missing_slug(artifacts_dir):
    inp = make_brief_input()
    del inp["slug"]
    with pytest.raises(ValueError, match="ERROR \\[write_brief\\]"):
        handle_write_brief(inp)


def test_brief_write_rejects_invalid_slug(artifacts_dir):
    with pytest.raises(ValueError, match="slug.*invalid"):
        handle_write_brief(make_brief_input(slug="../../etc"))


def test_brief_write_rejects_missing_idea(artifacts_dir):
    inp = make_brief_input()
    del inp["idea"]
    with pytest.raises(ValueError, match="ERROR \\[write_brief\\]"):
        handle_write_brief(inp)


def test_brief_write_rejects_missing_alternatives(artifacts_dir):
    inp = make_brief_input()
    del inp["alternatives"]
    with pytest.raises(ValueError, match="ERROR \\[write_brief\\]"):
        handle_write_brief(inp)


def test_brief_write_rejects_too_few_alternatives(artifacts_dir):
    inp = make_brief_input(alternatives=[
        {"description": "Only one option", "tradeoffs": "No comparison possible"}
    ])
    with pytest.raises(ValueError, match="ERROR \\[write_brief\\]"):
        handle_write_brief(inp)


def test_brief_write_rejects_missing_chosen_direction(artifacts_dir):
    inp = make_brief_input()
    del inp["chosen_direction"]
    with pytest.raises(ValueError, match="ERROR \\[write_brief\\]"):
        handle_write_brief(inp)


def test_brief_write_rejects_invalid_complexity_scope(artifacts_dir):
    inp = make_brief_input(complexity_assessment={"scope": "huge", "decomposition_needed": False})
    with pytest.raises(ValueError, match="ERROR \\[write_brief\\]"):
        handle_write_brief(inp)


# ---------------------------------------------------------------------------
# Design — id
# ---------------------------------------------------------------------------

def test_design_id_stable_across_versions(design_artifacts_dir):
    v1 = handle_write_design(make_design_input())
    v2 = handle_write_design(make_design_input(), existing_design=v1)
    assert v1["id"] == v2["id"]


def test_design_id_not_influenced_by_agent_on_v2(design_artifacts_dir):
    """Injecting an id field is rejected by schema validation (additionalProperties: false)."""
    v1 = handle_write_design(make_design_input())
    inp = make_design_input()
    inp["id"] = "design-injected"
    with pytest.raises(ValueError, match="ERROR \\[write_design\\]"):
        handle_write_design(inp, existing_design=v1)


# ---------------------------------------------------------------------------
# Design — slug
# ---------------------------------------------------------------------------

def test_design_slug_locked_after_v1(design_artifacts_dir):
    v1 = handle_write_design(make_design_input(slug="original-slug"))
    v2 = handle_write_design(make_design_input(slug="attacker-slug"), existing_design=v1)
    assert v2["slug"] == "original-slug"


def test_design_slug_change_does_not_create_new_folder(design_artifacts_dir):
    v1 = handle_write_design(make_design_input(slug="original-slug"))
    handle_write_design(make_design_input(slug="attacker-slug"), existing_design=v1)
    assert (design_artifacts_dir / "original-slug" / "design" / "v2.json").exists()
    assert not (design_artifacts_dir / "attacker-slug" / "design" / "v2.json").exists()


# ---------------------------------------------------------------------------
# Design — created_at
# ---------------------------------------------------------------------------

def test_design_created_at_immutable_on_v2(design_artifacts_dir):
    v1 = handle_write_design(make_design_input())
    v2 = handle_write_design(make_design_input(), existing_design=v1)
    assert v2["created_at"] == v1["created_at"]


def test_design_created_at_immutable_across_three_versions(design_artifacts_dir):
    v1 = handle_write_design(make_design_input())
    v2 = handle_write_design(make_design_input(), existing_design=v1)
    v3 = handle_write_design(make_design_input(), existing_design=v2)
    assert v3["created_at"] == v1["created_at"]


# ---------------------------------------------------------------------------
# Design — status always draft on write
# ---------------------------------------------------------------------------

def test_design_status_always_draft_on_v1(design_artifacts_dir):
    assert handle_write_design(make_design_input())["status"] == "draft"


def test_design_status_always_draft_on_v2(design_artifacts_dir):
    v1 = handle_write_design(make_design_input())
    assert handle_write_design(make_design_input(), existing_design=v1)["status"] == "draft"


# ---------------------------------------------------------------------------
# Design — references locked after v1 (engine-set on creation)
# ---------------------------------------------------------------------------

def test_design_references_set_by_engine_on_v1(design_artifacts_dir):
    v1 = handle_write_design(make_design_input())
    assert len(v1["references"]) == 1
    assert v1["references"][0].endswith("test-project/model_domain/v1.json")


def test_design_references_locked_after_v1(design_artifacts_dir):
    v1 = handle_write_design(make_design_input())
    v2 = handle_write_design(make_design_input(), existing_design=v1)
    assert v2["references"] == v1["references"]


# ---------------------------------------------------------------------------
# Design — content isolation
# ---------------------------------------------------------------------------

def test_design_orchestrator_fields_not_in_content(design_artifacts_dir):
    orchestrator = {"id", "slug", "version", "parent_version", "created_at",
                    "updated_at", "status", "references", "decision_log"}
    artifact = handle_write_design(make_design_input())
    assert orchestrator.isdisjoint(artifact["content"].keys())


def test_design_decision_log_entry_not_in_content(design_artifacts_dir):
    inp = make_design_input()
    inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "x", "changed_fields": []}
    artifact = handle_write_design(inp)
    assert "decision_log_entry" not in artifact["content"]


# ---------------------------------------------------------------------------
# Design — semantic guards (handler-level, not enforceable by JSON schema alone)
# ---------------------------------------------------------------------------

def test_design_acl_needed_requires_translation_approach(design_artifacts_dir):
    """acl_needed=true without translation_approach must raise ValueError."""
    inp = make_design_input(integration_patterns=[{
        "source_context": "A",
        "target_context": "B",
        "relationship_type": "anti-corruption-layer",
        "integration_style": "sync",
        "api_surface_type": "REST",
        "acl_needed": True,
        "translation_approach": "",
        "consistency_guarantee": "strong",
        "rationale": {
            "source_signal": "ACL relationship",
            "rule_applied": "ACL → acl_needed=true",
            "derived_value": "true",
        },
    }])
    with pytest.raises(ValueError, match="translation_approach"):
        handle_write_design(inp)


def test_design_cqrs_applied_requires_read_models(design_artifacts_dir):
    """cqrs_applied=true without cqrs_read_models must raise ValueError."""
    inp = make_design_input(layering_strategy=[{
        "context": "Deployment",
        "pattern": "hexagonal",
        "cqrs_applied": True,
        "cqrs_read_models": [],
        "rationale": {
            "source_signal": "Separate commands and queries",
            "rule_applied": "explicit command/query split → CQRS",
            "derived_value": "true",
        },
    }])
    with pytest.raises(ValueError, match="cqrs_read_models"):
        handle_write_design(inp)


# ---------------------------------------------------------------------------
# Design — input validation
# ---------------------------------------------------------------------------

def test_design_write_rejects_missing_slug(design_artifacts_dir):
    inp = make_design_input()
    del inp["slug"]
    with pytest.raises(ValueError, match="ERROR \\[write_design\\]"):
        handle_write_design(inp)


def test_design_write_rejects_invalid_slug(design_artifacts_dir):
    with pytest.raises(ValueError, match="slug.*invalid"):
        handle_write_design(make_design_input(slug="../../etc"))


def test_design_write_rejects_empty_layering_strategy(design_artifacts_dir):
    with pytest.raises(ValueError, match="ERROR \\[write_design\\]"):
        handle_write_design(make_design_input(layering_strategy=[]))


def test_design_write_rejects_invalid_pattern(design_artifacts_dir):
    inp = make_design_input(layering_strategy=[{
        "context": "X", "pattern": "microkernel", "cqrs_applied": False,
        "rationale": {"source_signal": "x", "rule_applied": "x", "derived_value": "x"},
    }])
    with pytest.raises(ValueError, match="ERROR \\[write_design\\]"):
        handle_write_design(inp)


def test_design_write_rejects_empty_what_not_to_test(design_artifacts_dir):
    inp = make_design_input(testing_strategy=[{
        "layer": "domain", "test_type": "unit",
        "what_to_test": "invariants",
        "what_not_to_test": "",
    }])
    with pytest.raises(ValueError, match="ERROR \\[write_design\\]"):
        handle_write_design(inp)


def test_design_write_rejects_nfr_source_not_human_provided(design_artifacts_dir):
    inp = make_design_input(nfrs=[{
        "category": "latency", "constraint": "p99 < 200ms",
        "scope": "global", "source": "derived",
    }])
    with pytest.raises(ValueError, match="ERROR \\[write_design\\]"):
        handle_write_design(inp)


def test_design_v1_fails_without_approved_model(domain_artifacts_dir):
    """Engine gate: write_design v1 raises ValueError when no approved model artifact exists."""
    # "original-slug" has an approved PRD (domain_system archetype) but no model_domain artifact
    with pytest.raises(ValueError, match="no approved model_domain"):
        handle_write_design(make_design_input(slug="original-slug"))


# ---------------------------------------------------------------------------
# Tech Stack — id
# ---------------------------------------------------------------------------

def test_tech_stack_id_stable_across_versions(tech_stack_artifacts_dir):
    v1 = handle_write_tech_stack(make_tech_stack_input())
    v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
    assert v1["id"] == v2["id"]


def test_tech_stack_id_not_influenced_by_agent_on_v2(tech_stack_artifacts_dir):
    """Injecting an id field is rejected by schema validation (additionalProperties: false)."""
    v1 = handle_write_tech_stack(make_tech_stack_input())
    inp = make_tech_stack_input()
    inp["id"] = "tech-stack-injected"
    with pytest.raises(ValueError, match="ERROR \\[write_tech_stack\\]"):
        handle_write_tech_stack(inp, existing_tech_stack=v1)


# ---------------------------------------------------------------------------
# Tech Stack — slug
# ---------------------------------------------------------------------------

def test_tech_stack_slug_locked_after_v1(tech_stack_artifacts_dir):
    v1 = handle_write_tech_stack(make_tech_stack_input(slug="original-slug"))
    v2 = handle_write_tech_stack(make_tech_stack_input(slug="attacker-slug"), existing_tech_stack=v1)
    assert v2["slug"] == "original-slug"


def test_tech_stack_slug_change_does_not_create_new_folder(tech_stack_artifacts_dir):
    v1 = handle_write_tech_stack(make_tech_stack_input(slug="original-slug"))
    handle_write_tech_stack(make_tech_stack_input(slug="attacker-slug"), existing_tech_stack=v1)
    assert (tech_stack_artifacts_dir / "original-slug" / "tech_stack" / "v2.json").exists()
    assert not (tech_stack_artifacts_dir / "attacker-slug" / "tech_stack" / "v2.json").exists()


# ---------------------------------------------------------------------------
# Tech Stack — created_at
# ---------------------------------------------------------------------------

def test_tech_stack_created_at_immutable_on_v2(tech_stack_artifacts_dir):
    v1 = handle_write_tech_stack(make_tech_stack_input())
    v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
    assert v2["created_at"] == v1["created_at"]


def test_tech_stack_created_at_immutable_across_three_versions(tech_stack_artifacts_dir):
    v1 = handle_write_tech_stack(make_tech_stack_input())
    v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
    v3 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v2)
    assert v3["created_at"] == v1["created_at"]


# ---------------------------------------------------------------------------
# Tech Stack — status always draft on write
# ---------------------------------------------------------------------------

def test_tech_stack_status_always_draft_on_v1(tech_stack_artifacts_dir):
    assert handle_write_tech_stack(make_tech_stack_input())["status"] == "draft"


def test_tech_stack_status_always_draft_on_v2(tech_stack_artifacts_dir):
    v1 = handle_write_tech_stack(make_tech_stack_input())
    assert handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)["status"] == "draft"


# ---------------------------------------------------------------------------
# Tech Stack — references populated from upstream design on v1; carried forward on v2+
# ---------------------------------------------------------------------------

def test_tech_stack_references_set_by_engine_on_v1(tech_stack_artifacts_dir):
    v1 = handle_write_tech_stack(make_tech_stack_input())
    assert len(v1["references"]) == 1
    assert v1["references"][0].endswith("test-project/design/v1.json")


def test_tech_stack_references_locked_after_v1(tech_stack_artifacts_dir):
    v1 = handle_write_tech_stack(make_tech_stack_input())
    v2 = handle_write_tech_stack(make_tech_stack_input(), existing_tech_stack=v1)
    assert v2["references"] == v1["references"]


# ---------------------------------------------------------------------------
# Tech Stack — content isolation
# ---------------------------------------------------------------------------

def test_tech_stack_orchestrator_fields_not_in_content(tech_stack_artifacts_dir):
    orchestrator = {"id", "slug", "version", "parent_version", "created_at",
                    "updated_at", "status", "references", "decision_log"}
    artifact = handle_write_tech_stack(make_tech_stack_input())
    assert orchestrator.isdisjoint(artifact["content"].keys())


def test_tech_stack_decision_log_entry_not_in_content(tech_stack_artifacts_dir):
    inp = make_tech_stack_input()
    inp["decision_log_entry"] = {"trigger": "initial_draft", "summary": "x", "changed_fields": []}
    artifact = handle_write_tech_stack(inp)
    assert "decision_log_entry" not in artifact["content"]


# ---------------------------------------------------------------------------
# Tech Stack — semantic guard: rejection_reason must be non-empty
# ---------------------------------------------------------------------------

def test_tech_stack_rejects_empty_rejection_reason(tech_stack_artifacts_dir):
    inp = make_tech_stack_input(adrs=[{
        "decision_point": "API framework",
        "architectural_signal": "integration_patterns[0].api_surface_type: REST",
        "candidates": [
            {"name": "FastAPI", "tradeoffs": "Async-native"},
            {"name": "Flask", "tradeoffs": "Mature"},
        ],
        "constraints_surfaced": [],
        "chosen": "FastAPI",
        "rationale": "Better async support",
        "rejections": [{"candidate": "Flask", "rejection_reason": ""}],
    }])
    with pytest.raises(ValueError, match="rejection_reason"):
        handle_write_tech_stack(inp)


def test_tech_stack_rejects_whitespace_only_rejection_reason(tech_stack_artifacts_dir):
    inp = make_tech_stack_input(adrs=[{
        "decision_point": "API framework",
        "architectural_signal": "integration_patterns[0].api_surface_type: REST",
        "candidates": [
            {"name": "FastAPI", "tradeoffs": "Async-native"},
            {"name": "Flask", "tradeoffs": "Mature"},
        ],
        "constraints_surfaced": [],
        "chosen": "FastAPI",
        "rationale": "Better async support",
        "rejections": [{"candidate": "Flask", "rejection_reason": "   "}],
    }])
    with pytest.raises(ValueError, match="rejection_reason"):
        handle_write_tech_stack(inp)


# ---------------------------------------------------------------------------
# Tech Stack — input validation
# ---------------------------------------------------------------------------

def test_tech_stack_write_rejects_missing_slug(tech_stack_artifacts_dir):
    inp = make_tech_stack_input()
    del inp["slug"]
    with pytest.raises(ValueError, match="ERROR \\[write_tech_stack\\]"):
        handle_write_tech_stack(inp)


def test_tech_stack_write_rejects_invalid_slug(tech_stack_artifacts_dir):
    with pytest.raises(ValueError, match="slug.*invalid"):
        handle_write_tech_stack(make_tech_stack_input(slug="../../etc"))


def test_tech_stack_write_rejects_empty_adrs(tech_stack_artifacts_dir):
    with pytest.raises(ValueError, match="ERROR \\[write_tech_stack\\]"):
        handle_write_tech_stack(make_tech_stack_input(adrs=[]))


def test_tech_stack_write_rejects_too_few_candidates(tech_stack_artifacts_dir):
    inp = make_tech_stack_input(adrs=[{
        "decision_point": "API framework",
        "architectural_signal": "integration_patterns[0].api_surface_type: REST",
        "candidates": [{"name": "FastAPI", "tradeoffs": "Only one candidate"}],
        "constraints_surfaced": [],
        "chosen": "FastAPI",
        "rationale": "Only option",
        "rejections": [],
    }])
    with pytest.raises(ValueError, match="ERROR \\[write_tech_stack\\]"):
        handle_write_tech_stack(inp)


def test_tech_stack_write_rejects_missing_adrs_field(tech_stack_artifacts_dir):
    inp = make_tech_stack_input()
    del inp["adrs"]
    with pytest.raises(ValueError, match="ERROR \\[write_tech_stack\\]"):
        handle_write_tech_stack(inp)


def test_tech_stack_v1_fails_without_approved_design(design_artifacts_dir):
    """Engine gate: write_tech_stack v1 raises ValueError when no approved design exists."""
    with pytest.raises(ValueError, match="no approved Design artifact"):
        handle_write_tech_stack(make_tech_stack_input(slug="no-design-here"))


# ---------------------------------------------------------------------------
# update_schema — input validation
# ---------------------------------------------------------------------------

def test_update_schema_rejects_duplicate_field(artifacts_dir):
    """Adding a field that already exists in the schema must raise."""
    _ensure_instance_schema("my-app", "model_domain")
    handle_update_schema("my-app", "model_domain", "extra_field", "optional", "Some field")
    with pytest.raises(ValueError, match="already exists"):
        handle_update_schema("my-app", "model_domain", "extra_field", "optional", "Duplicate")


def test_update_schema_rejects_invalid_kind(artifacts_dir):
    _ensure_instance_schema("my-app", "model_domain")
    with pytest.raises(ValueError, match="kind must be"):
        handle_update_schema("my-app", "model_domain", "new_field", "required", "Some field")


def test_update_schema_rejects_empty_description(artifacts_dir):
    _ensure_instance_schema("my-app", "model_domain")
    with pytest.raises(ValueError, match="description must not be empty"):
        handle_update_schema("my-app", "model_domain", "new_field", "optional", "")


def test_update_schema_rejects_missing_schema_file(artifacts_dir):
    """Stage that has never been written has no schema.json — must raise."""
    with pytest.raises(ValueError, match="no schema found"):
        handle_update_schema("my-app", "model_domain", "new_field", "optional", "Some field")

# ---------------------------------------------------------------------------
# write_model / approve_model — input validation
# ---------------------------------------------------------------------------

def test_write_model_rejects_unsupported_model_type(prd_artifacts_dir):
    handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
    handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
    with pytest.raises(ValueError, match="unsupported model_type"):
        handle_write_model({"slug": "my-app", "model_type": "invalid", "content": {}})


def test_write_model_rejects_type_not_in_topology(prd_artifacts_dir):
    """data_pipeline slug cannot write a domain model."""
    handle_write_prd(make_prd_input(slug="my-app", primary_archetype="data_pipeline"))
    handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
    with pytest.raises(ValueError, match="not in the topology"):
        handle_write_model({"slug": "my-app", "model_type": "domain", "content": {}})


def test_write_model_requires_approved_prd(prd_artifacts_dir):
    handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
    # PRD is draft — topology undetermined
    with pytest.raises(ValueError, match="cannot determine topology"):
        handle_write_model({"slug": "my-app", "model_type": "domain", "content": {}})


def test_approve_model_rejects_missing_mandatory_fields(prd_artifacts_dir):
    handle_write_prd(make_prd_input(slug="my-app", primary_archetype="domain_system"))
    handle_approve_prd(str(prd_artifacts_dir / "my-app" / "prd" / "v1.json"))
    # Write model with empty content — mandatory fields will be missing
    handle_write_model({"slug": "my-app", "model_type": "domain", "content": {}})
    artifact_path = str(prd_artifacts_dir / "my-app" / "model_domain" / "v1.json")
    with pytest.raises(ValueError, match="missing mandatory fields"):
        handle_approve_model(artifact_path)
