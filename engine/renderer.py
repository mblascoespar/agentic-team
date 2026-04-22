import json as _json


# ---------------------------------------------------------------------------
# Shared rendering helpers
# ---------------------------------------------------------------------------

def _render_section(label: str, value) -> list[str]:
    """Render a single content field generically — handles str, list, dict."""
    lines: list[str] = [label]
    if isinstance(value, str):
        lines.append(f"  {value}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                lines.append(f"  • {item}")
            elif isinstance(item, dict):
                lines.append("  ──")
                for k, v in item.items():
                    lines.append(
                        f"    {k}: {_json.dumps(v, ensure_ascii=False)}"
                        if isinstance(v, (list, dict))
                        else f"    {k}: {v}"
                    )
            else:
                lines.append(f"  • {_json.dumps(item, ensure_ascii=False)}")
    elif isinstance(value, dict):
        for k, v in value.items():
            lines.append(
                f"  {k}: {_json.dumps(v, ensure_ascii=False)}"
                if isinstance(v, (list, dict))
                else f"  {k}: {v}"
            )
    else:
        lines.append(f"  {value}")
    lines.append("")
    return lines


def _render_decision_log(artifact: dict) -> list[str]:
    if not artifact.get("decision_log"):
        return []
    lines = ["DECISION LOG"]
    for entry in artifact["decision_log"]:
        lines += [
            f"  v{entry['version']} · {entry['timestamp'][:10]} · "
            f"{entry['author']} · {entry['trigger']}",
            f"    {entry['summary']}",
        ]
        if entry.get("changed_fields"):
            lines += [f"    fields: {', '.join(entry['changed_fields'])}"]
    lines += [""]
    return lines


def render_model(artifact: dict) -> str:
    """Render any model artifact (domain, data_flow, system, workflow).

    Content fields are rendered generically — mandatory fields from the instance
    schema are labeled [mandatory]; optional fields are unlabeled.
    The schema is not loaded here; callers may pass it via the schema kwarg for
    field-kind annotations (used by the model agent session display).
    """
    model_type = artifact.get("model_type", "unknown")
    stage = f"model_{model_type.replace('data_flow', 'data_flow')}"
    c = artifact.get("content", {})
    lines = [
        f"Model ({model_type}): {artifact['slug']}  "
        f"(v{artifact['version']} · {artifact['status']})",
        f"Path: artifacts/{artifact['slug']}/{stage}/v{artifact['version']}.json",
        "",
    ]

    for field, value in c.items():
        lines.append(f"── {field.replace('_', ' ').upper()}")
        if isinstance(value, list):
            for item in value:
                lines.append(
                    f"  • {item}" if isinstance(item, str)
                    else f"  • {_json.dumps(item, ensure_ascii=False)}"
                )
        elif isinstance(value, dict):
            for k, v in value.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append(f"  {value}")
        lines.append("")

    if artifact.get("decision_log"):
        lines += ["DECISION LOG"]
        for entry in artifact["decision_log"]:
            lines += [
                f"  v{entry['version']} · {entry['timestamp'][:10]} · "
                f"{entry['author']} · {entry['trigger']}",
                f"    {entry['summary']}",
            ]
        lines += [""]

    return "\n".join(lines)


def render_tech_stack(artifact: dict) -> str:
    c = artifact["content"]
    lines = [
        f"Tech Stack: {artifact['slug']}  (v{artifact['version']} · {artifact['status']})",
        f"Path: artifacts/{artifact['slug']}/tech_stack/v{artifact['version']}.json",
        "",
    ]

    for adr in c.get("adrs", []):
        lines += [
            f"DECISION: {adr['decision_point']}",
            f"  Signal: {adr['architectural_signal']}",
            f"  Chosen: {adr['chosen']}",
            f"  Rationale: {adr['rationale']}",
        ]
        if adr.get("candidates"):
            lines += ["  Candidates:"]
            for cand in adr["candidates"]:
                lines += [
                    f"    • {cand['name']}",
                    f"      Tradeoffs: {cand['tradeoffs']}",
                ]
        if adr.get("constraints_surfaced"):
            lines += ["  Constraints surfaced:"]
            for constraint in adr["constraints_surfaced"]:
                lines += [f"    • {constraint}"]
        if adr.get("rejections"):
            lines += ["  Not chosen:"]
            for rej in adr["rejections"]:
                lines += [f"    • {rej['candidate']}: {rej['rejection_reason']}"]
        lines += [""]

    if c.get("open_questions"):
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]

    if artifact.get("decision_log"):
        lines += ["DECISION LOG"]
        for entry in artifact["decision_log"]:
            lines += [
                f"  v{entry['version']} · {entry['timestamp'][:10]} · {entry['author']} · {entry['trigger']}",
                f"    {entry['summary']}",
            ]
            if entry.get("changed_fields"):
                lines += [f"    fields: {', '.join(entry['changed_fields'])}"]
        lines += [""]

    return "\n".join(lines)


def render_prd(artifact: dict) -> str:
    c = artifact["content"]
    lines = [
        f"PRD: {c['title']}  (v{artifact['version']} · {artifact['slug']} · {artifact['status']})",
        f"Path: artifacts/{artifact['slug']}/prd/v{artifact['version']}.json",
        "",
        "PROBLEM",
        c["problem"],
        "",
        "TARGET USERS",
        *[f"  • {u}" for u in c["target_users"]],
        "",
        "GOALS",
        *[f"  • {g}" for g in c["goals"]],
        "",
        "SUCCESS METRICS",
        *[f"  • {m['metric']} — measured by: {m['measurement_method']}" for m in c["success_metrics"]],
        "",
        "SCOPE IN",
        *[f"  • {s}" for s in c["scope_in"]],
        "",
        "SCOPE OUT",
        *([f"  • {s}" for s in c["scope_out"]] if c["scope_out"] else ["  (none explicit)"]),
        "",
        "FEATURES",
    ]

    for f in c["features"]:
        lines += [
            f"  [{f['priority'].upper()}] {f['name']}",
            f"    {f['description']}",
            f"    {f['user_story']}",
        ]
        if f.get("acceptance_criteria"):
            lines += ["    Acceptance criteria:"]
            for ac in f["acceptance_criteria"]:
                lines += [f"      - {ac}"]

    lines += [""]

    if c["assumptions"]:
        lines += ["ASSUMPTIONS", *[f"  • {a}" for a in c["assumptions"]], ""]

    if c["open_questions"]:
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]

    if artifact.get("decision_log"):
        lines += ["DECISION LOG"]
        for entry in artifact["decision_log"]:
            lines += [
                f"  v{entry['version']} · {entry['timestamp'][:10]} · {entry['author']} · {entry['trigger']}",
                f"    {entry['summary']}",
            ]
            if entry.get("changed_fields"):
                lines += [f"    fields: {', '.join(entry['changed_fields'])}"]
        lines += [""]

    return "\n".join(lines)


def render_brief(artifact: dict) -> str:
    c = artifact["content"]
    lines = [
        f"Brief: {artifact['slug']}  (v{artifact['version']} · {artifact['status']})",
        f"Path: artifacts/{artifact['slug']}/brief/v{artifact['version']}.json",
        "",
        "IDEA",
        c["idea"],
        "",
        "ALTERNATIVES",
    ]

    for alt in c.get("alternatives", []):
        lines += [
            f"  • {alt['description']}",
            f"    Tradeoffs: {alt['tradeoffs']}",
        ]

    lines += [""]

    cd = c.get("chosen_direction", {})
    lines += [
        "CHOSEN DIRECTION",
        f"  {cd.get('direction', '')}",
        f"  Rationale: {cd.get('rationale', '')}",
        "",
        "COMPETITIVE SCAN",
        c.get("competitive_scan", ""),
        "",
    ]

    ca = c.get("complexity_assessment", {})
    lines += [
        "COMPLEXITY ASSESSMENT",
        f"  Scope: {ca.get('scope', '')}",
        f"  Decomposition needed: {ca.get('decomposition_needed', '')}",
        "",
    ]

    if c.get("open_questions"):
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]

    if artifact.get("decision_log"):
        lines += ["DECISION LOG"]
        for entry in artifact["decision_log"]:
            lines += [
                f"  v{entry['version']} · {entry['timestamp'][:10]} · {entry['author']} · {entry['trigger']}",
                f"    {entry['summary']}",
            ]
            if entry.get("changed_fields"):
                lines += [f"    fields: {', '.join(entry['changed_fields'])}"]
        lines += [""]

    return "\n".join(lines)


def _render_design_domain_system(c: dict) -> list[str]:
    lines: list[str] = []

    if c.get("layering_strategy"):
        lines += ["LAYERING STRATEGY"]
        for ls in c["layering_strategy"]:
            cqrs_note = (
                f"  CQRS: yes (read models: {', '.join(ls.get('cqrs_read_models') or [])})"
                if ls.get("cqrs_applied") else "  CQRS: no"
            )
            lines += [f"  {ls['context']}: {ls['pattern']}", cqrs_note]
            r = ls.get("rationale", {})
            lines += [f"  rationale: {r.get('derived_value', '')} — {r.get('rule_applied', '')}"]
            if r.get("override_reason"):
                lines += [f"  override: {r['override_reason']}"]
        lines += [""]

    if c.get("aggregate_consistency"):
        lines += ["AGGREGATE CONSISTENCY"]
        for ac in c["aggregate_consistency"]:
            lines += [f"  {ac['context']}/{ac['aggregate']}: within={ac['within_aggregate']}"]
            for ev in ac.get("cross_aggregate_events") or []:
                lines += [f"    event: {ev['event_name']} → {ev['target_aggregate']}"]
        lines += [""]

    if c.get("integration_patterns"):
        lines += ["INTEGRATION PATTERNS"]
        for ip in c["integration_patterns"]:
            acl_note = (
                f"ACL: yes — {ip.get('translation_approach', '')}"
                if ip.get("acl_needed") else "ACL: no"
            )
            lines += [
                f"  {ip['source_context']} → {ip['target_context']}  [{ip['relationship_type']}]",
                f"    style: {ip['integration_style']}  api: {ip['api_surface_type']}  {acl_note}",
                f"    consistency: {ip['consistency_guarantee']}",
            ]
        lines += [""]

    if c.get("storage"):
        lines += ["STORAGE"]
        for s in c["storage"]:
            lines += [
                f"  {s['context']}/{s['aggregate']}: {s['type']}",
                f"    transaction boundary: {s['transaction_boundary']}",
            ]
            r = s.get("rationale", {})
            lines += [f"    rationale: {r.get('derived_value', '')} — {r.get('rule_applied', '')}"]
        lines += [""]

    cc = c.get("cross_cutting", {})
    if cc:
        lines += ["CROSS-CUTTING CONCERNS"]
        auth = cc.get("auth", {})
        if auth:
            lines += [
                "  Auth",
                f"    authentication: {auth.get('authentication_layer', '')}",
                f"    authorization:  {auth.get('authorization_layer', '')}",
                f"    rationale: {auth.get('rationale', '')}",
            ]
        ep = cc.get("error_propagation", {})
        if ep:
            lines += [
                "  Error propagation",
                f"    domain:         {ep.get('domain_exceptions', '')}",
                f"    application:    {ep.get('application_exceptions', '')}",
                f"    infrastructure: {ep.get('infrastructure_exceptions', '')}",
                f"    translation:    {ep.get('translation_rules', '')}",
            ]
        obs = cc.get("observability", {})
        if obs:
            lines += ["  Observability", f"    trace boundaries: {obs.get('trace_boundaries', '')}"]
            for ll in obs.get("logging_per_layer") or []:
                lines += [f"    log [{ll['layer']}]: {ll['what_to_log']}"]
            lines += [f"    metrics: {obs.get('metrics_exposure', '')}"]
        lines += [""]

    if c.get("testing_strategy"):
        lines += ["TESTING STRATEGY"]
        for ts in c["testing_strategy"]:
            lines += [
                f"  [{ts['layer']}]  type: {ts['test_type']}",
                f"    test:     {ts['what_to_test']}",
                f"    NOT test: {ts['what_not_to_test']}",
            ]
        lines += [""]

    if c.get("nfrs"):
        lines += ["NON-FUNCTIONAL REQUIREMENTS"]
        for nfr in c["nfrs"]:
            lines += [f"  [{nfr['category']}] {nfr['constraint']}  (scope: {nfr['scope']})"]
        lines += [""]

    if c.get("open_questions"):
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]

    return lines


def _render_design_data_pipeline(c: dict) -> list[str]:
    lines: list[str] = []
    for field in ["pipeline_topology", "storage", "failure_handling", "scaling", "observability",
                  "testing_strategy", "nfrs"]:
        if c.get(field) is not None:
            lines += _render_section(field.upper().replace("_", " "), c[field])
    if c.get("open_questions"):
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]
    return lines


def _render_design_system_integration(c: dict) -> list[str]:
    lines: list[str] = []
    for field in ["integration_contracts", "error_handling", "acl_strategy", "observability",
                  "testing_strategy", "nfrs"]:
        if c.get(field) is not None:
            lines += _render_section(field.upper().replace("_", " "), c[field])
    if c.get("open_questions"):
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]
    return lines


def _render_design_process_system(c: dict) -> list[str]:
    lines: list[str] = []
    for field in ["state_machine", "persistence_strategy", "human_task_routing", "timeout_model",
                  "audit_strategy", "testing_strategy", "nfrs"]:
        if c.get(field) is not None:
            lines += _render_section(field.upper().replace("_", " "), c[field])
    if c.get("open_questions"):
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]
    return lines


def _render_design_system_evolution(c: dict) -> list[str]:
    lines: list[str] = []
    for field in ["migration_path", "compatibility_strategy", "rollback_plan", "regression_guards",
                  "testing_strategy", "nfrs"]:
        if c.get(field) is not None:
            lines += _render_section(field.upper().replace("_", " "), c[field])
    if c.get("open_questions"):
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]
    return lines


def render_design(artifact: dict) -> str:
    archetype = artifact.get("primary_archetype", "domain_system")
    c = artifact["content"]
    archetype_label = archetype.replace("_", " ") if archetype else "unknown"
    lines = [
        f"Design ({archetype_label}): {artifact['slug']}  (v{artifact['version']} · {artifact['status']})",
        f"Path: artifacts/{artifact['slug']}/design/v{artifact['version']}.json",
        "",
    ]
    dispatch = {
        "domain_system":      _render_design_domain_system,
        "data_pipeline":      _render_design_data_pipeline,
        "system_integration": _render_design_system_integration,
        "process_system":     _render_design_process_system,
        "system_evolution":   _render_design_system_evolution,
    }
    renderer = dispatch.get(archetype, _render_design_domain_system)
    lines += renderer(c)
    lines += _render_decision_log(artifact)
    return "\n".join(lines)


def render_domain_model(artifact: dict) -> str:
    c = artifact["content"]
    lines = [
        f"Domain Model: {artifact['slug']}  (v{artifact['version']} · {artifact['status']})",
        f"Path: artifacts/{artifact['slug']}/domain/v{artifact['version']}.json",
        "",
    ]

    for ctx in c.get("bounded_contexts", []):
        lines += [
            f"CONTEXT: {ctx['name']}",
            f"  {ctx['responsibility']}",
            "",
        ]
        for agg in ctx.get("aggregates", []):
            lines += [f"  AGGREGATE: {agg['name']}  (root: {agg['root_entity']})"]
            if agg.get("entities"):
                lines += [f"    entities: {', '.join(agg['entities'])}"]
            for inv in agg.get("invariants", []):
                lines += [f"    invariant: {inv}"]
            lines += [""]
        if ctx.get("commands"):
            lines += ["  COMMANDS"]
            for cmd in ctx["commands"]:
                lines += [f"    {cmd['name']}: {cmd['description']}"]
        if ctx.get("queries"):
            lines += ["  QUERIES"]
            for q in ctx["queries"]:
                lines += [f"    {q['name']}: {q['description']}"]
        if ctx.get("events"):
            lines += ["  EVENTS"]
            for ev in ctx["events"]:
                lines += [f"    {ev['name']}: {ev['description']}"]
        lines += [""]

    if c.get("context_map"):
        lines += ["CONTEXT MAP"]
        for rel in c["context_map"]:
            lines += [f"  {rel['upstream']} → {rel['downstream']}  [{rel['relationship']}]"]
        lines += [""]

    if c.get("assumptions"):
        lines += ["MODELING ASSUMPTIONS", *[f"  • {a}" for a in c["assumptions"]], ""]

    if c.get("open_questions"):
        lines += [
            f"OPEN QUESTIONS ({len(c['open_questions'])})",
            *[f"  {i+1}. {q}" for i, q in enumerate(c["open_questions"])],
            "",
        ]
    else:
        lines += ["OPEN QUESTIONS: none", ""]

    if artifact.get("decision_log"):
        lines += ["DECISION LOG"]
        for entry in artifact["decision_log"]:
            lines += [
                f"  v{entry['version']} · {entry['timestamp'][:10]} · {entry['author']} · {entry['trigger']}",
                f"    {entry['summary']}",
            ]
            if entry.get("changed_fields"):
                lines += [f"    fields: {', '.join(entry['changed_fields'])}"]
        lines += [""]

    return "\n".join(lines)


def render_artifact(artifact: dict, stage: str) -> str:
    """Dispatch to the correct per-stage renderer."""
    if stage.startswith("model_"):
        return render_model(artifact)
    dispatch = {
        "brief":      render_brief,
        "prd":        render_prd,
        "design":     render_design,
        "tech_stack": render_tech_stack,
    }
    renderer = dispatch.get(stage)
    if renderer is None:
        raise ValueError(f"No renderer for stage '{stage}'.")
    return renderer(artifact)
