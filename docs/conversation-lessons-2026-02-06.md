# Conversation Lessons and Insights (2026-02-06)

## Context
We discussed evolving Hive’s planning workflow, introducing a `breakdown` command, and designing a new Rule of Five review feature to improve plan quality before task breakdown.

## Key Outcomes
- **`hive breakdown` replaces `hive plan`**: breakdown reads an existing plan and creates Beads epics/tasks/subtasks using an LLM. Default behavior should execute Beads commands; `--dry-run` is optional.
- **Default prompt with override**: both breakdown and review should use default prompts stored in the repo, with optional overrides.
- **Plan storage**: create a `plans/` directory and store dated plan docs there.
- **Review feature should be optional and conversational**: no enforcement, no auto‑rewrite by default, but the agent should offer to draft changes on request.

## Design Principles That Emerged
- **Structured feedback improves reproducibility**: unstructured feedback leads to low‑quality, inconsistent outcomes. A scaffolded report makes reviews more reliable.
- **Conversation matters**: a live back‑and‑forth surfaces misunderstandings and helps align on improvements without forcing changes.
- **Human judgment remains central**: the agent should help, not decide. Offer edits, don’t impose them.
- **Minimal MVP avoids brittle automation**: skip JSON parsing and heavy automation early; focus on high‑quality review reports and optional rewrites.

## Critical Insights
- **Vague success criteria is a real risk**: it’s hard to know when a plan is “done.” A structured review report helps define completeness.
- **Top‑N changes is too limiting**: for design improvement, exhaustive suggestions are often more useful than a truncated list.
- **Avoid premature complexity**: checklists and one‑shot modes can be future enhancements, not initial scope.
- **Keep prompt behavior isolated**: review prompts should be separate from AGENTS.md to avoid unintended impact on other workflows.

## Decisions and Clarifications
- The review output should be a **report**, not a rewritten plan by default.
- The report should be **pass‑by‑pass** (Rule of Five) and include concrete suggestions.
- The agent should **offer to apply changes** but only when requested.
- **Interactive tmux session** is preferred for the review command in MVP.
- **Artifacts stored next to the plan** (`<plan_path>.review.md`) for discoverability.

## Open Questions Noted
- Whether to add a `--report-only` mode later.
- Whether to move review artifacts into `.hive/reviews/` once volume grows.
- Whether to add a “taskability” check (plan -> easy to break down) as future work.

## Why This Was Valuable
- The process balanced critical feedback with practical constraints.
- We kept the workflow simple while increasing quality and user control.
- We prioritized outcomes: better plan content, not just more process.

