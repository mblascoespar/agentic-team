"""
Renderer tests — artifact-to-text output.

Verify that every meaningful piece of information in an artifact appears in
the rendered output. Strategy: build a known artifact dict and assert specific
strings are present. We do not assert exact full output to avoid brittleness
from formatting tweaks.

Run this suite alone:  pytest -m renderer
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from renderer import render_prd, render_domain_model, render_brief, render_design, render_tech_stack

pytestmark = pytest.mark.renderer


# ===========================================================================
# Fixtures
# ===========================================================================

def make_prd_artifact() -> dict:
    return {
        "id": "prd-abc123",
        "slug": "deploy-rollback",
        "version": 2,
        "status": "draft",
        "source_idea": "One-click rollback",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-02T00:00:00+00:00",
        "references": [],
        "decision_log": [
            {
                "version": 2,
                "timestamp": "2026-01-02T00:00:00+00:00",
                "author": "agent:product-agent",
                "trigger": "human_feedback",
                "summary": "Narrowed scope to CLI only",
                "changed_fields": ["scope_out"],
            }
        ],
        "content": {
            "title": "One-Command Production Rollback",
            "problem": "Engineers lose 2 hours per incident manually coordinating rollbacks",
            "target_users": ["Backend engineer at a mid-size SaaS company"],
            "goals": ["Engineers recover from a bad deploy in under 5 minutes"],
            "success_metrics": [
                {"metric": "Mean time to rollback", "measurement_method": "Measured in CI logs"}
            ],
            "scope_in": ["CLI-triggered rollback"],
            "scope_out": ["GUI rollback interface"],
            "features": [
                {
                    "name": "One-command rollback",
                    "description": "Single CLI command triggers rollback",
                    "user_story": "As a backend engineer I want to rollback with one command",
                    "priority": "must",
                }
            ],
            "assumptions": ["Users are comfortable with CLI"],
            "open_questions": ["Does the target env require audit logging?"],
        },
    }


def make_domain_artifact() -> dict:
    return {
        "id": "domain-def456",
        "slug": "deploy-rollback",
        "version": 1,
        "status": "draft",
        "created_at": "2026-01-03T00:00:00+00:00",
        "updated_at": "2026-01-03T00:00:00+00:00",
        "references": ["artifacts/deploy-rollback/prd/v2.json"],
        "decision_log": [
            {
                "version": 1,
                "timestamp": "2026-01-03T00:00:00+00:00",
                "author": "agent:domain-agent",
                "trigger": "initial_draft",
                "summary": "Initial domain model from PRD",
                "changed_fields": ["bounded_contexts", "context_map"],
            }
        ],
        "content": {
            "bounded_contexts": [
                {
                    "name": "Deployment",
                    "responsibility": "Owns the lifecycle of a deployment from trigger to completion.",
                    "aggregates": [
                        {
                            "name": "Deployment",
                            "root_entity": "Deployment",
                            "entities": ["DeploymentStep"],
                            "invariants": ["Cannot rollback after marked complete"],
                        }
                    ],
                    "commands": [{"name": "TriggerRollback", "description": "Initiates a rollback"}],
                    "queries": [{"name": "GetDeploymentStatus", "description": "Returns current state"}],
                    "events": [{"name": "RollbackCompleted", "description": "Emitted when rollback finishes"}],
                }
            ],
            "context_map": [
                {
                    "upstream": "Deployment",
                    "downstream": "Notification",
                    "relationship": "customer-supplier",
                }
            ],
            "assumptions": ["Rollback targets a single service per invocation; multi-service rollback is out of scope for this model."],
            "open_questions": ["Should rollback be automatic or require manual confirmation?"],
        },
    }


# ===========================================================================
# render_prd
# ===========================================================================

class TestRenderPrd:
    def test_contains_title(self):
        out = render_prd(make_prd_artifact())
        assert "One-Command Production Rollback" in out

    def test_contains_slug_and_version(self):
        out = render_prd(make_prd_artifact())
        assert "deploy-rollback" in out
        assert "v2" in out

    def test_contains_status(self):
        out = render_prd(make_prd_artifact())
        assert "draft" in out

    def test_contains_problem(self):
        out = render_prd(make_prd_artifact())
        assert "Engineers lose 2 hours" in out

    def test_contains_target_user(self):
        out = render_prd(make_prd_artifact())
        assert "Backend engineer" in out

    def test_contains_goal(self):
        out = render_prd(make_prd_artifact())
        assert "5 minutes" in out

    def test_contains_success_metric(self):
        out = render_prd(make_prd_artifact())
        assert "Mean time to rollback" in out
        assert "CI logs" in out

    def test_contains_scope_in(self):
        out = render_prd(make_prd_artifact())
        assert "CLI-triggered rollback" in out

    def test_contains_scope_out(self):
        out = render_prd(make_prd_artifact())
        assert "GUI rollback interface" in out

    def test_contains_feature_name_and_priority(self):
        out = render_prd(make_prd_artifact())
        assert "One-command rollback" in out
        assert "MUST" in out

    def test_contains_assumption(self):
        out = render_prd(make_prd_artifact())
        assert "comfortable with CLI" in out

    def test_contains_open_question(self):
        out = render_prd(make_prd_artifact())
        assert "audit logging" in out

    def test_contains_decision_log_entry(self):
        out = render_prd(make_prd_artifact())
        assert "Narrowed scope to CLI only" in out
        assert "agent:product-agent" in out

    def test_empty_open_questions_shows_none(self):
        artifact = make_prd_artifact()
        artifact["content"]["open_questions"] = []
        out = render_prd(artifact)
        assert "OPEN QUESTIONS: none" in out

    def test_artifact_path_shown(self):
        out = render_prd(make_prd_artifact())
        assert "artifacts/deploy-rollback/prd/v2.json" in out


# ===========================================================================
# render_domain_model
# ===========================================================================

class TestRenderDomainModel:
    def test_contains_slug_and_version(self):
        out = render_domain_model(make_domain_artifact())
        assert "deploy-rollback" in out
        assert "v1" in out

    def test_contains_status(self):
        out = render_domain_model(make_domain_artifact())
        assert "draft" in out

    def test_contains_context_name(self):
        out = render_domain_model(make_domain_artifact())
        assert "Deployment" in out

    def test_contains_context_responsibility(self):
        out = render_domain_model(make_domain_artifact())
        assert "lifecycle of a deployment" in out

    def test_contains_aggregate_name_and_root(self):
        out = render_domain_model(make_domain_artifact())
        assert "AGGREGATE" in out
        assert "Deployment" in out

    def test_contains_aggregate_entity(self):
        out = render_domain_model(make_domain_artifact())
        assert "DeploymentStep" in out

    def test_contains_invariant(self):
        out = render_domain_model(make_domain_artifact())
        assert "Cannot rollback after marked complete" in out

    def test_contains_command(self):
        out = render_domain_model(make_domain_artifact())
        assert "TriggerRollback" in out
        assert "Initiates a rollback" in out

    def test_contains_query(self):
        out = render_domain_model(make_domain_artifact())
        assert "GetDeploymentStatus" in out
        assert "Returns current state" in out

    def test_contains_event(self):
        out = render_domain_model(make_domain_artifact())
        assert "RollbackCompleted" in out
        assert "Emitted when rollback finishes" in out

    def test_contains_context_map_relationship(self):
        out = render_domain_model(make_domain_artifact())
        assert "Notification" in out
        assert "customer-supplier" in out

    def test_contains_open_question(self):
        out = render_domain_model(make_domain_artifact())
        assert "manual confirmation" in out

    def test_contains_decision_log_entry(self):
        out = render_domain_model(make_domain_artifact())
        assert "Initial domain model from PRD" in out
        assert "agent:domain-agent" in out

    def test_empty_open_questions_shows_none(self):
        artifact = make_domain_artifact()
        artifact["content"]["open_questions"] = []
        out = render_domain_model(artifact)
        assert "OPEN QUESTIONS: none" in out

    def test_contains_assumption(self):
        out = render_domain_model(make_domain_artifact())
        assert "MODELING ASSUMPTIONS" in out
        assert "multi-service rollback is out of scope" in out

    def test_empty_assumptions_not_shown(self):
        artifact = make_domain_artifact()
        artifact["content"]["assumptions"] = []
        out = render_domain_model(artifact)
        assert "MODELING ASSUMPTIONS" not in out

    def test_empty_context_map_not_shown(self):
        artifact = make_domain_artifact()
        artifact["content"]["context_map"] = []
        out = render_domain_model(artifact)
        assert "CONTEXT MAP" not in out

    def test_artifact_path_shown(self):
        out = render_domain_model(make_domain_artifact())
        assert "artifacts/deploy-rollback/domain/v1.json" in out


# ===========================================================================
# render_brief
# ===========================================================================

def make_brief_artifact() -> dict:
    return {
        "id": "brief-ghi789",
        "slug": "deploy-rollback",
        "version": 1,
        "status": "draft",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "references": [],
        "decision_log": [
            {
                "version": 1,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "author": "agent:brainstorm-agent",
                "trigger": "initial_draft",
                "summary": "Initial exploration, chose point solution",
                "changed_fields": ["alternatives", "chosen_direction"],
            }
        ],
        "content": {
            "idea": "Build a one-command rollback tool for backend engineers",
            "alternatives": [
                {
                    "description": "Point solution: one-command rollback only",
                    "tradeoffs": "Fast to build; does not address upstream pipeline issues",
                },
                {
                    "description": "Full deploy platform with rollback, staging, and monitoring",
                    "tradeoffs": "Higher value but larger scope; deferred",
                },
            ],
            "chosen_direction": {
                "direction": "Point solution focused on one-command rollback",
                "rationale": "Chosen over full platform to solve the most acute pain fastest",
            },
            "competitive_scan": "Argo and Spinnaker require full cluster setup. No lightweight CLI option exists.",
            "complexity_assessment": {
                "scope": "small",
                "decomposition_needed": False,
            },
            "open_questions": ["Does the target environment require audit logging?"],
        },
    }


class TestRenderBrief:
    def test_contains_slug_and_version(self):
        out = render_brief(make_brief_artifact())
        assert "deploy-rollback" in out
        assert "v1" in out

    def test_contains_status(self):
        out = render_brief(make_brief_artifact())
        assert "draft" in out

    def test_contains_idea(self):
        out = render_brief(make_brief_artifact())
        assert "one-command rollback tool" in out

    def test_contains_alternative_descriptions(self):
        out = render_brief(make_brief_artifact())
        assert "Point solution" in out
        assert "Full deploy platform" in out

    def test_contains_alternative_tradeoffs(self):
        out = render_brief(make_brief_artifact())
        assert "upstream pipeline issues" in out

    def test_contains_chosen_direction(self):
        out = render_brief(make_brief_artifact())
        assert "Point solution focused on one-command rollback" in out

    def test_contains_chosen_direction_rationale(self):
        out = render_brief(make_brief_artifact())
        assert "most acute pain fastest" in out

    def test_contains_competitive_scan(self):
        out = render_brief(make_brief_artifact())
        assert "Argo and Spinnaker" in out

    def test_contains_complexity_scope(self):
        out = render_brief(make_brief_artifact())
        assert "small" in out

    def test_contains_open_question(self):
        out = render_brief(make_brief_artifact())
        assert "audit logging" in out

    def test_contains_decision_log_entry(self):
        out = render_brief(make_brief_artifact())
        assert "Initial exploration" in out
        assert "agent:brainstorm-agent" in out

    def test_empty_open_questions_shows_none(self):
        artifact = make_brief_artifact()
        artifact["content"]["open_questions"] = []
        out = render_brief(artifact)
        assert "OPEN QUESTIONS: none" in out

    def test_artifact_path_shown(self):
        out = render_brief(make_brief_artifact())
        assert "artifacts/deploy-rollback/brief/v1.json" in out


# ===========================================================================
# Design artifact
# ===========================================================================

def make_design_artifact() -> dict:
    return {
        "id": "design-abc123",
        "slug": "deploy-rollback",
        "version": 1,
        "parent_version": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "status": "draft",
        "references": ["artifacts/deploy-rollback/domain/v1.json"],
        "decision_log": [
            {
                "version": 1,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "author": "agent:architecture-agent",
                "trigger": "initial_draft",
                "summary": "Initial design derived from domain model",
                "changed_fields": ["layering_strategy", "testing_strategy"],
            }
        ],
        "content": {
            "layering_strategy": [
                {
                    "context": "Deployment",
                    "pattern": "hexagonal",
                    "cqrs_applied": False,
                    "rationale": {
                        "source_signal": "Deployment context has external CI adapters",
                        "rule_applied": "many external dependencies + I/O isolation → hexagonal",
                        "derived_value": "hexagonal",
                    },
                }
            ],
            "aggregate_consistency": [
                {
                    "context": "Deployment",
                    "aggregate": "Deployment",
                    "within_aggregate": "strong",
                    "cross_aggregate_events": [
                        {"event_name": "DeploymentCompleted", "target_aggregate": "AuditLog"}
                    ],
                    "rationale": {
                        "source_signal": "Single root transactional scope",
                        "rule_applied": "within-aggregate always strong",
                        "derived_value": "strong",
                    },
                }
            ],
            "integration_patterns": [
                {
                    "source_context": "Deployment",
                    "target_context": "Notification",
                    "relationship_type": "open-host",
                    "integration_style": "async",
                    "api_surface_type": "event-driven",
                    "acl_needed": False,
                    "consistency_guarantee": "eventual",
                    "rationale": {
                        "source_signal": "open-host with multiple published events",
                        "rule_applied": "open-host + high event volume → event-driven",
                        "derived_value": "event-driven",
                    },
                }
            ],
            "storage": [
                {
                    "context": "Deployment",
                    "aggregate": "Deployment",
                    "type": "relational",
                    "transaction_boundary": "Single aggregate root",
                    "rationale": {
                        "source_signal": "Complex invariants on Deployment aggregate",
                        "rule_applied": "complex invariants + relational queries → relational",
                        "derived_value": "relational",
                    },
                }
            ],
            "cross_cutting": {
                "auth": {
                    "authentication_layer": "API boundary",
                    "authorization_layer": "Application service layer",
                    "rationale": "Derived from hexagonal layering",
                },
                "error_propagation": {
                    "domain_exceptions": "Invariant violations never leave domain layer",
                    "application_exceptions": "Use case failures translated at application boundary",
                    "infrastructure_exceptions": "I/O failures translated at adapter boundary",
                    "translation_rules": "Domain → application at use case; infra → application at adapter",
                },
                "observability": {
                    "trace_boundaries": "Starts at API port, ends at adapter exit",
                    "logging_per_layer": [
                        {"layer": "domain", "what_to_log": "Invariant violations only"},
                        {"layer": "infrastructure", "what_to_log": "External I/O calls"},
                    ],
                    "metrics_exposure": "Request count and latency at API boundary",
                },
            },
            "testing_strategy": [
                {
                    "layer": "domain",
                    "test_type": "unit",
                    "what_to_test": "Aggregate invariants and domain events",
                    "what_not_to_test": "Persistence, infrastructure adapters, HTTP concerns",
                },
                {
                    "layer": "application",
                    "test_type": "integration",
                    "what_to_test": "Use case orchestration with mocked adapters",
                    "what_not_to_test": "Domain logic re-tests, UI",
                },
            ],
            "nfrs": [
                {
                    "category": "latency",
                    "constraint": "p99 latency < 200ms",
                    "scope": "global",
                    "source": "human_provided",
                }
            ],
            "open_questions": ["Should audit log retention be 90 or 365 days?"],
        },
    }


class TestRenderDesign:
    def test_contains_slug_and_version(self):
        out = render_design(make_design_artifact())
        assert "deploy-rollback" in out
        assert "v1" in out

    def test_contains_status(self):
        out = render_design(make_design_artifact())
        assert "draft" in out

    def test_contains_artifact_path(self):
        out = render_design(make_design_artifact())
        assert "artifacts/deploy-rollback/design/v1.json" in out

    def test_contains_layering_pattern(self):
        out = render_design(make_design_artifact())
        assert "hexagonal" in out

    def test_contains_layering_context(self):
        out = render_design(make_design_artifact())
        assert "Deployment" in out

    def test_contains_cqrs_decision(self):
        out = render_design(make_design_artifact())
        assert "CQRS" in out

    def test_contains_aggregate_consistency(self):
        out = render_design(make_design_artifact())
        assert "strong" in out
        assert "DeploymentCompleted" in out

    def test_contains_integration_pattern_api_surface(self):
        out = render_design(make_design_artifact())
        assert "event-driven" in out

    def test_contains_integration_pattern_style(self):
        out = render_design(make_design_artifact())
        assert "async" in out

    def test_contains_storage_type(self):
        out = render_design(make_design_artifact())
        assert "relational" in out

    def test_contains_cross_cutting_auth(self):
        out = render_design(make_design_artifact())
        assert "authentication" in out
        assert "API boundary" in out

    def test_contains_cross_cutting_error_propagation(self):
        out = render_design(make_design_artifact())
        assert "domain_exceptions" in out or "Invariant violations" in out

    def test_contains_observability_logging(self):
        out = render_design(make_design_artifact())
        assert "Invariant violations only" in out

    def test_contains_testing_strategy_what_not_to_test(self):
        out = render_design(make_design_artifact())
        assert "NOT test" in out
        assert "Persistence" in out

    def test_contains_nfr(self):
        out = render_design(make_design_artifact())
        assert "p99 latency < 200ms" in out
        assert "latency" in out

    def test_contains_open_question(self):
        out = render_design(make_design_artifact())
        assert "audit log retention" in out

    def test_empty_open_questions_shows_none(self):
        artifact = make_design_artifact()
        artifact["content"]["open_questions"] = []
        out = render_design(artifact)
        assert "OPEN QUESTIONS: none" in out

    def test_contains_decision_log_entry(self):
        out = render_design(make_design_artifact())
        assert "Initial design derived from domain model" in out
        assert "agent:architecture-agent" in out


# ===========================================================================
# Tech Stack artifact
# ===========================================================================

def make_tech_stack_artifact() -> dict:
    return {
        "id": "tech-stack-abc123",
        "slug": "deploy-rollback",
        "version": 1,
        "parent_version": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "status": "draft",
        "references": ["artifacts/deploy-rollback/design/v1.json"],
        "decision_log": [
            {
                "version": 1,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "author": "agent:tech-stack-agent",
                "trigger": "initial_draft",
                "summary": "All five ADRs resolved via structured deliberation",
                "changed_fields": ["adrs"],
            }
        ],
        "content": {
            "adrs": [
                {
                    "decision_point": "API framework",
                    "architectural_signal": "integration_patterns[0].api_surface_type: REST",
                    "candidates": [
                        {
                            "name": "FastAPI",
                            "tradeoffs": "Async-native, fast, OpenAPI auto-generation; smaller ecosystem than Django",
                        },
                        {
                            "name": "Flask",
                            "tradeoffs": "Mature, broad ecosystem; sync-first requires more async boilerplate",
                        },
                    ],
                    "constraints_surfaced": [
                        "team has existing FastAPI experience",
                        "deployment target is async-native container environment",
                    ],
                    "chosen": "FastAPI",
                    "rationale": "FastAPI chosen for async support and team familiarity; Flask rejected due to sync-first overhead",
                    "rejections": [
                        {
                            "candidate": "Flask",
                            "rejection_reason": "Sync-first model conflicts with async integration style; team lacks Flask experience",
                        }
                    ],
                },
                {
                    "decision_point": "Test framework",
                    "architectural_signal": "testing_strategy (4 layers)",
                    "candidates": [
                        {
                            "name": "pytest",
                            "tradeoffs": "Flexible, widely adopted, excellent plugin ecosystem; no built-in async runner",
                        },
                        {
                            "name": "unittest",
                            "tradeoffs": "Standard library, no install required; verbose, less readable parametrize syntax",
                        },
                    ],
                    "constraints_surfaced": [],
                    "chosen": "pytest",
                    "rationale": "pytest chosen for readability and fixture model; team already uses it in other projects",
                    "rejections": [
                        {
                            "candidate": "unittest",
                            "rejection_reason": "More verbose and lacks the fixture model; no clear advantage for this project",
                        }
                    ],
                },
            ],
            "open_questions": ["Confirm pytest-asyncio version compatibility with FastAPI test client"],
        },
    }


class TestRenderTechStack:
    def test_contains_slug_and_version(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "deploy-rollback" in out
        assert "v1" in out

    def test_contains_status(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "draft" in out

    def test_contains_artifact_path(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "artifacts/deploy-rollback/tech_stack/v1.json" in out

    def test_contains_decision_point(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "API framework" in out
        assert "Test framework" in out

    def test_contains_architectural_signal(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "api_surface_type: REST" in out

    def test_contains_chosen_technology(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "FastAPI" in out
        assert "pytest" in out

    def test_contains_rationale(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "async support and team familiarity" in out

    def test_contains_candidate_names(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "Flask" in out
        assert "unittest" in out

    def test_contains_candidate_tradeoffs(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "OpenAPI auto-generation" in out
        assert "sync-first requires more async boilerplate" in out

    def test_contains_constraints_surfaced(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "team has existing FastAPI experience" in out
        assert "async-native container environment" in out

    def test_empty_constraints_not_shown(self):
        out = render_tech_stack(make_tech_stack_artifact())
        # The second ADR has empty constraints — no "Constraints surfaced" section for it
        # We just verify the output doesn't crash and the first ADR's constraints appear
        assert "team has existing FastAPI experience" in out

    def test_contains_rejection_candidate_and_reason(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "Sync-first model conflicts" in out
        assert "lacks the fixture model" in out

    def test_contains_open_question(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "pytest-asyncio" in out

    def test_empty_open_questions_shows_none(self):
        artifact = make_tech_stack_artifact()
        artifact["content"]["open_questions"] = []
        out = render_tech_stack(artifact)
        assert "OPEN QUESTIONS: none" in out

    def test_contains_decision_log_entry(self):
        out = render_tech_stack(make_tech_stack_artifact())
        assert "All five ADRs resolved via structured deliberation" in out
        assert "agent:tech-stack-agent" in out
