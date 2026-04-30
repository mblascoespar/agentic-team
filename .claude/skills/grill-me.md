# Grill Me Skill (Shared Challenge Protocol)

Use this skill when the agent must challenge a plan/idea through dependency-ordered questioning to reach explicit shared understanding.

## Core behavior

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Protocol

1. Restate the current plan in one concise paragraph.
2. Build a dependency-ordered decision tree.
3. Resolve parent decisions before child decisions.
4. Ask exactly one question per turn.
5. Include a recommended answer with every question.
6. If a question is answerable from artifacts/code, inspect and report findings instead of asking.
7. After each user response, update the dependency map and ask the next highest-leverage unresolved question.
8. Stop only when meaningful branches are resolved and shared understanding is explicit.

## Question format

- Question: <single focused question>
- Why this matters: <one sentence>
- Recommended answer: <best current recommendation>
- If you agree: <decision fixed + next branch>

## Completion criteria

- Goals and constraints are explicit.
- Major design branches were resolved.
- Dependency order was respected.
- Risks and assumptions are listed.
- Final agreed decisions are summarized clearly.

## Override rule

If the command-specific prompt conflicts with this skill, follow the command-specific rule for that command.
