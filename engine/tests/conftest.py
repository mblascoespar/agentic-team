"""
Shared fixtures for agent tests.
"""
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal valid tool inputs
# ---------------------------------------------------------------------------

def make_prd_input(slug="test-project", **overrides) -> dict:
    base = {
        "slug": slug,
        "source_idea": "Build something useful",
        "title": "Test Project",
        "problem": "A specific problem for a specific user",
        "target_users": ["Backend engineer at a mid-size SaaS company"],
        "goals": ["Engineers ship faster with fewer incidents"],
        "success_metrics": [
            {"metric": "Deploy time", "measurement_method": "Measured in CI logs"}
        ],
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


def make_brief_input(slug="test-project", **overrides) -> dict:
    base = {
        "slug": slug,
        "idea": "Build a tool that helps developers ship faster",
        "alternatives": [
            {
                "description": "Point solution: one-command rollback only",
                "tradeoffs": "Fast to build, narrow scope; does not address upstream pipeline issues",
            },
            {
                "description": "Platform: full deploy pipeline with rollback, staging, and monitoring",
                "tradeoffs": "Higher value but significantly larger scope; slower to validate",
            },
        ],
        "chosen_direction": {
            "direction": "Point solution focused on one-command rollback for backend engineers",
            "rationale": "Chosen over the platform because it solves the most acute pain fastest; platform scope deferred",
        },
        "competitive_scan": "Existing tools like Argo and Spinnaker require full cluster setup. No lightweight CLI-native option exists.",
        "complexity_assessment": {
            "scope": "small",
            "decomposition_needed": False,
        },
        "open_questions": ["Does the target environment require audit logging?"],
    }
    base.update(overrides)
    return base


def make_domain_input(slug="test-project", **overrides) -> dict:
    """Engine resolves the upstream PRD from slug — no prd_path needed."""
    base = {
        "slug": slug,
        "bounded_contexts": [
            {
                "name": "Deployment",
                "responsibility": "Owns the lifecycle of a deployment from trigger to completion.",
                "aggregates": [
                    {
                        "name": "Deployment",
                        "root_entity": "Deployment",
                        "entities": ["DeploymentStep"],
                        "invariants": ["A deployment cannot be rolled back after it is marked complete"],
                    }
                ],
                "commands": [{"name": "TriggerDeployment", "description": "Starts a new deployment"}],
                "queries": [{"name": "GetDeploymentStatus", "description": "Returns current deployment state"}],
                "events": [{"name": "DeploymentCompleted", "description": "Emitted when a deployment finishes"}],
            }
        ],
        "context_map": [],
        "open_questions": ["Should rollback be automatic or manual?"],
    }
    base.update(overrides)
    return base


def make_design_input(slug="test-project", **overrides) -> dict:
    """Engine resolves the upstream domain model from slug — no domain_path needed."""
    base = {
        "slug": slug,
        "layering_strategy": [
            {
                "context": "Deployment",
                "pattern": "hexagonal",
                "cqrs_applied": False,
                "rationale": {
                    "source_signal": "Deployment context has external adapters for CI systems and requires domain isolation",
                    "rule_applied": "many external dependencies + I/O isolation needed → hexagonal",
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
                    "source_signal": "Deployment aggregate has single-root transactional boundary",
                    "rule_applied": "within-aggregate consistency is always strong by DDD definition",
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
                    "source_signal": "Deployment aggregate has complex invariants and requires relational queries for status tracking",
                    "rule_applied": "complex invariants + relational query needs → relational",
                    "derived_value": "relational",
                },
            }
        ],
        "cross_cutting": {
            "auth": {
                "authentication_layer": "API boundary (outermost layer)",
                "authorization_layer": "Application service layer",
                "rationale": "Derived from hexagonal layering — auth at port entry, authz at use case",
            },
            "error_propagation": {
                "domain_exceptions": "Invariant violations never leave the domain layer",
                "application_exceptions": "Use case failures translated at the application boundary",
                "infrastructure_exceptions": "I/O failures translated at the adapter boundary",
                "translation_rules": "Domain exceptions mapped to application errors at use case boundary; infrastructure errors mapped to application errors at adapter boundary",
            },
            "observability": {
                "trace_boundaries": "Trace starts at API port entry, ends at infrastructure adapter exit",
                "logging_per_layer": [
                    {"layer": "domain", "what_to_log": "Invariant violations only"},
                    {"layer": "application", "what_to_log": "Command/query dispatch and use case outcomes"},
                    {"layer": "infrastructure", "what_to_log": "External I/O calls and their results"},
                ],
                "metrics_exposure": "Exposed at API boundary: request count, error rate, latency",
            },
        },
        "testing_strategy": [
            {
                "layer": "domain",
                "test_type": "unit",
                "what_to_test": "Aggregate invariants, value object equality, domain events",
                "what_not_to_test": "Persistence behavior, infrastructure adapters, HTTP concerns",
            },
            {
                "layer": "application",
                "test_type": "integration",
                "what_to_test": "Use case orchestration with mocked adapters",
                "what_not_to_test": "Domain logic re-tests, UI, persistence internals",
            },
        ],
        "nfrs": [
            {
                "category": "latency",
                "constraint": "p99 latency < 500ms",
                "scope": "global",
                "source": "human_provided",
            }
        ],
        "open_questions": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_approved_brief(slug: str, artifacts_dir: Path) -> None:
    """Write and approve a brief for slug in the given artifacts_dir."""
    from tool_handler import handle_write_brief, handle_approve_brief
    handle_write_brief(make_brief_input(slug=slug))
    handle_approve_brief(str(artifacts_dir / slug / "brief" / "v1.json"))


def make_tech_stack_input(slug="test-project", **overrides) -> dict:
    """Engine resolves the upstream design artifact from slug — no design_path needed."""
    base = {
        "slug": slug,
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
                        "tradeoffs": "Mature, simple, broad ecosystem; sync-first requires more boilerplate for async",
                    },
                ],
                "constraints_surfaced": ["team has existing FastAPI experience"],
                "chosen": "FastAPI",
                "rationale": "FastAPI chosen for async support aligned with hexagonal design and team familiarity",
                "rejections": [
                    {
                        "candidate": "Flask",
                        "rejection_reason": "Sync-first model conflicts with async integration style; team lacks Flask experience",
                    }
                ],
            }
        ],
        "open_questions": [],
    }
    base.update(overrides)
    return base


# Slugs used in PRD handler tests (invariants, lifecycle, contracts).
_PRD_TEST_SLUGS = ("test-project", "original-slug", "my-project", "my-app", "deploy-rollback")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def artifacts_dir(tmp_path, monkeypatch):
    """
    Redirect ARTIFACTS_DIR to a temp directory so tests never touch the real artifacts/.
    No artifacts are pre-created — suitable for Brief tests and get_available_artifacts tests.
    """
    import tool_handler
    monkeypatch.setattr(tool_handler, "_ARTIFACTS_DIR_OVERRIDE", tmp_path)
    return tmp_path


@pytest.fixture
def prd_artifacts_dir(artifacts_dir):
    """
    Like artifacts_dir but with approved Briefs pre-created for all slugs used in
    PRD tests. Required because handle_write_prd v1 resolves the upstream Brief
    from slug via find_latest.
    """
    for slug in _PRD_TEST_SLUGS:
        _create_approved_brief(slug, artifacts_dir)
    return artifacts_dir


@pytest.fixture
def domain_artifacts_dir(prd_artifacts_dir):
    """
    Like prd_artifacts_dir but with approved PRDs pre-created for all slugs used
    in domain model tests. Required because handle_write_domain_model v1 resolves
    the upstream PRD from slug via find_latest.
    """
    from tool_handler import handle_write_prd, handle_approve_prd

    for slug in ("test-project", "original-slug", "my-app", "deploy-rollback"):
        handle_write_prd(make_prd_input(slug=slug))
        handle_approve_prd(str(prd_artifacts_dir / slug / "prd" / "v1.json"))

    return prd_artifacts_dir


@pytest.fixture
def design_artifacts_dir(domain_artifacts_dir):
    """
    Like domain_artifacts_dir but with approved Domain Models pre-created for all
    slugs used in design tests. Required because handle_write_design v1 resolves
    the upstream domain model from slug via find_latest.
    """
    from tool_handler import handle_write_domain_model, handle_approve_domain_model

    for slug in ("test-project", "original-slug", "my-app", "deploy-rollback"):
        handle_write_domain_model(make_domain_input(slug=slug))
        handle_approve_domain_model(str(domain_artifacts_dir / slug / "domain" / "v1.json"))

    return domain_artifacts_dir


@pytest.fixture
def tech_stack_artifacts_dir(design_artifacts_dir):
    """
    Like design_artifacts_dir but with approved Design artifacts pre-created for
    all slugs used in tech stack tests. Required because handle_write_tech_stack v1
    resolves the upstream design artifact from slug via find_latest.
    """
    from tool_handler import handle_write_design, handle_approve_design

    for slug in ("test-project", "original-slug", "my-app", "deploy-rollback"):
        handle_write_design(make_design_input(slug=slug))
        handle_approve_design(str(design_artifacts_dir / slug / "design" / "v1.json"))

    return design_artifacts_dir
