# Plan Review With the Rule of Five

## Why This Exists
Design and planning documents are easy to write but hard to make great. The Rule of Five review flow helps you systematically improve a plan by applying five focused passes: coverage, correctness, clarity, edge cases, and polish. This feature exists to help you get higher‑quality plans before you break them down into tasks.

## What It Is
`hive review` starts a focused review conversation with an LLM agent. The agent is primed with the Rule of Five and your plan content, then produces a structured review report with concrete feedback and questions. You stay in control of what changes to apply.

## What It Is Not
- It does not enforce review.
- It does not automatically rewrite your plan.
- It does not guarantee correctness without your judgment.

## When To Use It
Use it when a plan will drive real work and you want higher confidence in its quality. Skip it for quick drafts or exploratory ideas.

## How It Works
1. You provide a plan document.
2. `hive review` opens a tmux session with the agent.
3. The agent produces a structured review report and asks clarifying questions.
4. If you want, you can ask the agent to draft a revised plan.
5. The review report is saved next to the plan as `<plan_path>.review.md`.

## Example
```bash
hive review plans/my-plan.md
```

This will open a tmux session and produce `plans/my-plan.md.review.md`.

## Review Report Structure
The report follows the Rule of Five passes:
- Summary of Findings
- Draft (Coverage & Structure)
- Correctness (Facts & Logic)
- Clarity (Readability & Organization)
- Edge Cases & Risks
- Excellence (Polish & Professionalism)
- Offer to Apply Changes

## Prompt Overrides
You can provide your own prompt:
```bash
hive review plans/my-plan.md --prompt /path/to/prompt.md
```

## Purpose
This feature is designed to help you:
- Surface missing considerations and risks
- Improve correctness and clarity
- Produce plans that are easier to break down into tasks
- Learn from structured feedback while keeping human judgment central

