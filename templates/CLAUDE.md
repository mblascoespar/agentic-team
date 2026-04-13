# agentic-team

A multi-agent pipeline for taking ideas from concept to implementation-ready specs.
Workflows are modeled as DAGs. Each step produces a versioned artifact. All agent
invocations are **human-initiated** — Claude never triggers an agent autonomously.

---

## Available commands

| Command | Input | Output |
|---------|-------|--------|
| `/brainstorm` | raw idea | Brief artifact |
| `/product-owner` | Brief (approved) | PRD artifact |
| `/domain-agent` | PRD (approved) | Domain Model artifact |
| `/architecture-agent` | Domain Model (approved) | Design artifact |
| `/tech-stack-agent` | Design (approved) | Tech Stack artifact |

Each command accepts an optional argument:
- No argument — lists in-progress and ready-to-start artifacts for that stage
- Slug (e.g. `my-project`) — resumes or starts work on that project
- Artifact path (e.g. `artifacts/my-project/prd/v2.json`) — opens a specific version

---

## Artifact conventions

All artifacts are written to `artifacts/` in this project root:

```
artifacts/
  <slug>/
    brief/     v1.json, v2.json, ...
    prd/       v1.json, v2.json, ...
    domain/    v1.json, v2.json, ...
    design/    v1.json, v2.json, ...
    tech_stack/ v1.json, v2.json, ...
```

Each file is a complete snapshot. Versions accumulate — nothing is overwritten.

---

## Rules

- Agents are invoked only by explicit user command — never autonomously
- Each stage requires the previous stage to be approved before it can start
- Human approval gates exist at every stage: Brief → PRD → Domain → Design → Tech Stack
