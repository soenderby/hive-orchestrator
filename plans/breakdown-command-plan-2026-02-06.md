# Plan: Replace `hive plan` with `hive breakdown`

Date: 2026-02-06

## Goal
Introduce a `hive breakdown` command that reads a plan document and uses an agent to create Beads epics/tasks/subtasks. Remove `hive plan`. Add a default prompt (overrideable), and run Beads commands by default (no `--apply` required). Ensure the codebase is structured to support future command changes and add review tasks.

## Scope
- New command: `hive breakdown <plan_path>`
- Default prompt template with override support
- Agent output parsing + Beads command execution
- Remove `hive plan` command + docs + tests
- Add review tasks focused on command structure extensibility

## Decisions (Confirmed)
- Command name: `hive breakdown`
- Required positional argument: `<plan_path>`
- Default behavior: execute Beads commands
- Optional `--dry-run` to print commands without executing
- Default prompt provided by the repo; can be overridden
- Use Beads directly (no `--apply` flag)
- Remove `hive plan`

## Open Questions
- Output format: strict JSON vs. shell command list
- How to persist prompt templates: `hive/prompts/` vs. `.hive/prompts/`
- Expected agent invocation contract (stdin vs. file + env vars)

## Implementation Plan
1. **Command Design**
   - Add `hive/commands/breakdown.py` with Click command.
   - Signature: `hive breakdown <plan_path> [--prompt <path>] [--dry-run]`.
   - Validate `.beads/` exists; error clearly if missing.

2. **Prompt Storage**
   - Add `hive/prompts/breakdown.md` (repo default).
   - Use this prompt unless `--prompt` provided.

3. **Agent Invocation**
   - Use configured agent command (from config).
   - Provide prompt + plan content to agent (define protocol).
   - Suggested contract: JSON output with epics/tasks/subtasks and deps.

4. **Output Parsing + Beads Execution**
   - Parse agent output.
   - Generate and execute `bd create` / `bd dep add` commands.
   - If `--dry-run`, print commands only.

5. **Remove `hive plan`**
   - Remove command registration in `hive/cli.py`.
   - Remove `hive/commands/plan.py`.
   - Update README/GETTING_STARTED references.
   - Replace tests in `tests/test_plan.py` with `tests/test_breakdown.py`.

6. **Structure Review Tasks**
   - Review command registration patterns and discoverability.
   - Evaluate how easy it is to add/remove/change commands.
   - Identify needed refactors to keep command changes safe.

## Testing Plan
- Unit tests for breakdown command with mocked agent output.
- Unit tests for prompt override and dry-run behavior.
- Ensure Beads command calls are well-formed.

## Risks
- Agent output variability could cause parsing errors.
- Prompt contract needs to be explicit and stable.
- Removing `hive plan` impacts docs/tests and user expectations.

## Review Tasks to Add
- Code structure review for command extensibility
- Refactor proposals (if needed) to simplify command changes

