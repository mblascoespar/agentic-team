"""
Shared fixtures for agent tests.
"""
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal valid artifact bodies (content only — no slug, no wrapper)
# ---------------------------------------------------------------------------

def make_brief_body(**overrides) -> dict:
    base = {
        "idea": "Build a tool that helps developers ship faster",
        "alternatives": [
            {
                "description": "Point solution: one-command rollback only",
                "tradeoffs": "Fast to build, narrow scope",
            },
            {
                "description": "Platform: full deploy pipeline",
                "tradeoffs": "Higher value but larger scope",
            },
        ],
        "chosen_direction": {
            "direction": "Point solution focused on one-command rollback",
            "rationale": "Solves the most acute pain fastest",
        },
        "competitive_scan": "No lightweight CLI-native option exists.",
        "complexity_assessment": {"scope": "small", "decomposition_needed": False},
        "open_questions": ["Does the target environment require audit logging?"],
    }
    base.update(overrides)
    return base


def make_prd_body(**overrides) -> dict:
    base = {
        "title": "Test Project",
        "primary_archetype": "domain_system",
        "archetype_reasoning": "Rich business rules with complex invariants warrant a domain system classification.",
        "problem": "A specific problem for a specific user",
        "target_users": ["Backend engineer at a mid-size SaaS company"],
        "goals": ["Engineers ship faster with fewer incidents"],
        "success_metrics": [{"metric": "Deploy time", "measurement_method": "Measured in CI logs"}],
        "scope_in": ["Feature A"],
        "scope_out": ["Feature B"],
        "features": [
            {
                "name": "Feature A",
                "description": "Does something useful",
                "user_story": "As a user I want X so that Y",
                "priority": "must",
                "acceptance_criteria": ["Given X, when Y, then Z"],
            }
        ],
        "assumptions": ["Users are comfortable with CLI"],
        "open_questions": ["What is the deployment target?"],
    }
    base.update(overrides)
    return base


def make_model_body(model_type: str = "domain", **overrides) -> dict:
    """Return a minimal valid content body for write_artifact(stage='model_{type}')."""
    content_by_type: dict[str, dict] = {
        "domain": {
            "bounded_contexts": [{"name": "Core", "responsibility": "Owns core logic"}],
            "context_map": [],
            "open_questions": [],
        },
        "data_flow": {
            "sources": [{"name": "Input", "schema": "raw events"}],
            "stages": [{"name": "Transform", "transformation": "normalize"}],
            "sinks": [{"name": "Output", "schema": "normalized events"}],
            "open_questions": [],
        },
        "system": {
            "systems": [{"name": "ExtAPI", "owned": False}],
            "integrations": [{"from": "us", "to": "ExtAPI", "protocol": "REST"}],
            "constraints": ["Rate limit: 100 req/s"],
            "open_questions": [],
        },
        "workflow": {
            "actors": [{"name": "Operator", "role": "human"}],
            "steps": [{"name": "Install", "trigger": "manual", "action": "run script"}],
            "automation_boundary": "Script is automated; approval is manual",
            "open_questions": [],
        },
        "evolution": {
            "current_state": {"description": "Existing system", "key_behaviors": ["routes requests"], "components": []},
            "frozen_surface": [{"name": "MCP API", "kind": "api", "description": "Tool signatures", "dependents": ["agents"]}],
            "change_surface": [{"name": "routing", "current_behavior": "single topology", "target_behavior": "per-archetype", "breaking_for": [], "rationale": "support multiple archetypes"}],
            "migration_path": [{"step": "Step 1", "description": "Add archetype field", "gates": [], "rollback_boundary": "revert schema"}],
            "regression_risk": [{"area": "get_available_artifacts", "trigger": "topology change", "failure_mode": "silent", "guard": "test_contracts.py"}],
            "open_questions": [],
        },
    }
    body = dict(content_by_type.get(model_type, {}))
    body.update(overrides)
    return body


def make_design_body(**overrides) -> dict:
    base = {
        "layering_strategy": [
            {
                "context": "Deployment",
                "pattern": "hexagonal",
                "cqrs_applied": False,
                "rationale": {
                    "source_signal": "Deployment context has external adapters",
                    "rule_applied": "many external dependencies → hexagonal",
                    "derived_value": "hexagonal",
                },
            }
        ],
        "aggregate_consistency": [
            {
                "context": "Deployment",
                "aggregate": "Deployment",
                "within_aggregate": "strong",
                "cross_aggregate_events": [],
                "rationale": {
                    "source_signal": "Single-root transactional boundary",
                    "rule_applied": "within-aggregate consistency is always strong",
                    "derived_value": "strong",
                },
            }
        ],
        "integration_patterns": [],
        "storage": [
            {
                "context": "Deployment",
                "aggregate": "Deployment",
                "type": "relational",
                "transaction_boundary": "Single aggregate root per transaction",
                "rationale": {
                    "source_signal": "Complex invariants + relational query needs",
                    "rule_applied": "complex invariants → relational",
                    "derived_value": "relational",
                },
            }
        ],
        "cross_cutting": {
            "auth": {
                "authentication_layer": "API boundary",
                "authorization_layer": "Application service layer",
                "rationale": "Auth at port entry, authz at use case",
            },
            "error_propagation": {
                "domain_exceptions": "Never leave domain layer",
                "application_exceptions": "Translated at application boundary",
                "infrastructure_exceptions": "Translated at adapter boundary",
                "translation_rules": "Domain → application at use case; infra → application at adapter",
            },
            "observability": {
                "trace_boundaries": "API port entry to infrastructure adapter exit",
                "logging_per_layer": [
                    {"layer": "domain", "what_to_log": "Invariant violations only"},
                ],
                "metrics_exposure": "Request count, error rate, latency at API boundary",
            },
        },
        "testing_strategy": [
            {
                "layer": "domain",
                "test_type": "unit",
                "what_to_test": "Aggregate invariants",
                "what_not_to_test": "Persistence behavior",
            },
        ],
        "nfrs": [
            {"category": "latency", "constraint": "p99 < 500ms", "scope": "global", "source": "human_provided"},
        ],
        "open_questions": [],
    }
    base.update(overrides)
    return base


def make_tech_stack_body(**overrides) -> dict:
    base = {
        "adrs": [
            {
                "decision_point": "API framework",
                "architectural_signal": "integration_patterns REST",
                "candidates": [
                    {"name": "FastAPI", "tradeoffs": "Async-native, fast"},
                    {"name": "Flask", "tradeoffs": "Mature, sync-first"},
                ],
                "constraints_surfaced": ["team has FastAPI experience"],
                "chosen": "FastAPI",
                "rationale": "Async support + team familiarity",
                "rejections": [{"candidate": "Flask", "rejection_reason": "Sync-first conflicts with async style"}],
            }
        ],
        "open_questions": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_and_approve(slug: str, stage: str, body: dict, artifacts_dir: Path) -> None:
    from tool_handler import handle_write_artifact, handle_approve_artifact, find_latest
    handle_write_artifact(slug, stage, body)
    latest = find_latest(slug, stage)
    handle_approve_artifact(str(latest))


def _create_approved_brief(slug: str, artifacts_dir: Path) -> None:
    _write_and_approve(slug, "brief", make_brief_body(), artifacts_dir)


def _create_approved_prd(slug: str, artifacts_dir: Path, **body_overrides) -> None:
    _write_and_approve(slug, "prd", make_prd_body(**body_overrides), artifacts_dir)


def _create_approved_model(slug: str, model_type: str, artifacts_dir: Path) -> None:
    stage = f"model_{model_type}"
    _write_and_approve(slug, stage, make_model_body(model_type), artifacts_dir)


def _create_approved_design(slug: str, artifacts_dir: Path) -> None:
    _write_and_approve(slug, "design", make_design_body(), artifacts_dir)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ALL_TEST_SLUGS = (
    "test-project", "original-slug", "my-project", "my-app", "deploy-rollback",
    "test-pipeline", "test-integration", "test-workflow", "test-layered", "test-evolution",
)

_PRD_TEST_SLUGS = _ALL_TEST_SLUGS


@pytest.fixture
def artifacts_dir(tmp_path, monkeypatch):
    """Redirect artifacts dir to tmp. No pre-created artifacts."""
    import tool_handler
    monkeypatch.setattr(tool_handler, "_ARTIFACTS_DIR_OVERRIDE", tmp_path)
    return tmp_path


@pytest.fixture
def brief_artifacts_dir(artifacts_dir):
    """artifacts_dir with approved briefs for all test slugs."""
    for slug in _ALL_TEST_SLUGS:
        _create_approved_brief(slug, artifacts_dir)
    return artifacts_dir


@pytest.fixture
def prd_artifacts_dir(brief_artifacts_dir):
    """brief_artifacts_dir with approved domain_system PRDs for all test slugs."""
    for slug in _ALL_TEST_SLUGS:
        _create_approved_prd(slug, brief_artifacts_dir)
    return brief_artifacts_dir


@pytest.fixture
def model_artifacts_dir(prd_artifacts_dir):
    """prd_artifacts_dir with approved model_domain artifacts for domain_system slugs."""
    for slug in ("test-project", "original-slug", "my-app", "deploy-rollback"):
        _create_approved_model(slug, "domain", prd_artifacts_dir)
    return prd_artifacts_dir


@pytest.fixture
def design_artifacts_dir(model_artifacts_dir):
    """model_artifacts_dir with approved design artifacts."""
    for slug in ("test-project", "original-slug", "my-app", "deploy-rollback"):
        _create_approved_design(slug, model_artifacts_dir)
    return model_artifacts_dir


@pytest.fixture
def tech_stack_artifacts_dir(design_artifacts_dir):
    """design_artifacts_dir with approved tech_stack artifacts."""
    for slug in ("test-project", "original-slug", "my-app", "deploy-rollback"):
        _write_and_approve(slug, "tech_stack", make_tech_stack_body(), design_artifacts_dir)
    return design_artifacts_dir
