# Plan: Rule of Five Plan Review Support (Minimal, Conversational)

Date: 2026-02-06

## Goal
Provide optional support to help users review and improve plan documents using the Rule of Five workflow before breakdown into Beads issues. This is guidance-oriented and conversational, not enforced.

## Background
The Rule of Five describes five review passes for LLM outputs: Draft (shape/coverage), Correctness, Clarity, Edge Cases, Excellence. We want to help users apply this workflow to plan documents.

## MVP Definition
- `hive review` opens a tmux session for a structured review conversation.
- The agent produces a pass-by-pass review report and offers to draft revisions on request.
- The review report is saved to `<plan_path>.review.md`.
- The plan document includes a phase tag (e.g., Draft, Reviewed, Ready).

## Non-Goals
- Enforcing review as a mandatory gate
- Automatically running breakdown as part of review
- Automatic rewriting of the plan by default

## Proposed UX (Minimal)
Command:
- `hive review <plan_path> [--prompt <path>] [--dry-run]`

Behavior:
- Reads plan content from `<plan_path>`.
- Starts a review conversation with the configured agent in a tmux session.
- The agent is primed with a Rule of Five prompt (default) and the plan content.
- The agent produces a structured **review report** with concrete feedback and questions.
- The agent explicitly offers to draft a revised plan, but only does so on user request.
- The review report is saved to `<plan_path>.review.md`.
- The agent suggests updating the plan phase tag when the plan is reviewed.

Notes:
- The intent is to create a conversation, not an automated rewrite.
- Optional `--dry-run` prints the prompt that would be sent, without invoking the agent.

## Plan Phase Tag (Decision)
- The phase tag should be placed immediately under the title as a blockquote.
- Example:
  - `> Phase: Draft`
  - `> Phase: Reviewed`
  - `> Phase: Ready`
- Review output should call out phase changes explicitly (e.g., “recommend moving to Reviewed”).

## Happy Path Example
1. User runs: `hive review plans/my-plan.md`
2. Hive opens a tmux session in the plan directory and provides `REVIEW.md` (prompt + plan).
3. Agent writes a structured report to `plans/my-plan.md.review.md`.
4. User reads report and asks follow-up questions in the session.
5. If requested, agent drafts a revised plan.
6. User decides what changes to apply.
7. User updates the plan’s phase tag.

## Prompt Template Strategy
- Store default prompt at `hive/prompts/review-rule-of-five.md`.
- The prompt should:
  - Explain the Rule of Five.
  - Require a structured report with pass-by-pass headings.
  - Require a complete list of improvements found in each pass.
  - Encourage clarifying questions.
  - End with an explicit offer to draft a revised plan on request.
  - Explicitly instruct the agent to write the report to `<plan_path>.review.md`.

## Report Scaffold (Required Headings)
- Summary of Findings
- Pass 1: Draft (Coverage & Structure)
- Pass 2: Correctness (Facts & Logic)
- Pass 3: Clarity (Readability & Organization)
- Pass 4: Edge Cases & Risks
- Pass 5: Excellence (Polish & Professionalism)
- Offer to Apply Changes (explicit invitation)

## Conversation and File Handling
- Spawn agent in tmux (consistent with `hive work`).
- Session working directory should be the plan’s directory.
- Provide prompt + plan content in a file (e.g., `REVIEW.md`).
- Agent writes report to `<plan_path>.review.md`.
- If the report cannot be written, instruct the user to copy/paste from the session.

## Output / Storage
- Save the review report to `<plan_path>.review.md` (alongside the plan).
- Do not modify the original plan.

## Integration Points
- New command in `hive/commands/review.py`.
- Register in `hive/cli.py`.
- Optional note in `hive breakdown` help text: “Run `hive review` first for quality.”

## Testing Plan
- Unit test for prompt resolution and file output path.
- Dry-run test verifies no agent invocation.
- (Optional) documentation smoke test for session spawn.

## Risks
- Review quality depends on agent skill.
- Conversational workflow is less deterministic; harder to test.
- Users might expect an edited plan rather than feedback.

## Edge Cases
- tmux not available: fail fast with guidance to install it.
- plan path not readable or not writable: validate and warn.
- report not written: provide fallback instructions.

## Future Work (Not in MVP)
- One-shot `--report-only` mode
- Taskability checks for easier breakdown
- Review artifacts in `.hive/reviews/`

