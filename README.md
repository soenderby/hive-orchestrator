# Hive

A lightweight orchestrator for coordinating LLM coding agents using battle-tested primitives.

## Philosophy

> "Disk is state, git is memory. Fresh context is reliability."

Hive coordinates agents through:
- **tmux** - Session persistence and monitoring
- **git worktrees** - Filesystem isolation per task
- **Beads** - Persistent task memory and dependency tracking
- **Ralph-style loops** - External iteration with fresh context each cycle

**Core principles:**
1. **Plan first, execute second** — Human + agent collaborate on a quality plan before any worker starts
2. **One task, one session** — An agent performs exactly one task, then stops
3. **Serial by default** — Parallelism is opt-in and conservative
4. **Small tasks** — Tasks must fit in a single agent session (~30–60 minutes)
5. **Beads is the source of truth** — All coordination flows through task state, not messages

## Installation

```bash
pip install -e .
```

**Prerequisites:**
- Python 3.12+
- Git
- tmux
- [Beads](https://github.com/beadsx/beads) (`pip install beads`)
- Claude Code (`claude-code`) or another LLM coding agent

## Quick Start

```bash
# 1. Initialize beads in your project
cd your-project
bd init

# 2. Initialize hive
hive init

# 3. Create a plan
hive plan "Add user authentication system"

# 4. Approve the plan (after reviewing)
hive plan --approve

# 5. Execute work serially (safest)
hive work

# 6. Or execute with parallel workers (for independent tasks)
hive work --parallel 2

# 7. Monitor progress
hive status
```

## Commands

### `hive init`

Initialize Hive in the current project.

```bash
hive init
```

Creates:
- `.hive/` directory structure
- `.hive/config.toml` - Configuration file
- `.hive/workers.json` - Worker registry
- `.hive/plan.md` - Planning workspace
- `worktrees/` directory for task isolation

**Prerequisites:** Beads must be initialized first (`bd init`).

### `hive plan`

Interactive planning session for task breakdown.

```bash
# Start planning with a goal
hive plan "Implement user authentication"

# Show current plan
hive plan --show

# Approve plan for execution
hive plan --approve

# Continue from a too_big task
hive plan --continue
```

**Workflow:**
1. Human describes the goal
2. Plan is saved to `.hive/plan.md`
3. Human reviews and refines the plan
4. Use `--approve` to mark plan ready for execution
5. If a task is marked `too_big`, use `--continue` to see decomposition instructions

### `hive work`

Execute tasks using Ralph loop orchestration.

```bash
# Serial execution (one worker, safest)
hive work

# Parallel execution (N workers)
hive work --parallel 2

# Custom configuration
hive work --poll-interval 10 --task-timeout 7200 --spawn-grace 60
```

**Options:**
- `--parallel N` - Number of parallel workers (default: 1)
- `--poll-interval` - Polling interval in seconds (default: 5)
- `--task-timeout` - Task timeout in seconds (default: 3600)
- `--spawn-grace` - Spawn grace period in seconds (default: 30)
- `--agent-command` - Agent command to run (default: "claude-code")
- `--worker-id` - Custom worker ID (default: worker-<pid>)

**The Ralph Loop:**

Each worker iteration:
1. Get next ready task from Beads
2. Atomically claim task (compare-and-swap)
3. Create unique worktree (`worktrees/<worker-id>-<task-id>/`)
4. Generate CLAUDE.md context from task details + plan
5. Spawn agent in tmux session
6. Grace period check (detect spawn failures)
7. Poll Beads for completion (checks every `--poll-interval`)
8. Kill tmux session
9. Handle outcome:
   - **closed** → Merge to main, cleanup worktree
   - **too_big** → Cleanup, human decomposes
   - **blocked** → Preserve worktree for inspection
   - **failed/timeout** → Cleanup worktree

**Parallel Execution:**

When `--parallel N` is specified:
- Spawns N independent worker processes
- Each worker runs the Ralph loop independently
- Workers coordinate via atomic task claims
- No double-assignment (guaranteed by Beads)
- Each worker has unique worktree (`worker-1-task-abc`, `worker-2-task-def`)

### `hive status`

Show current workers, tasks, and progress.

```bash
# Human-readable status
hive status

# JSON output for scripting
hive status --json
```

**Shows:**
- Active workers and their current tasks
- Task statistics by status (open, in_progress, closed, blocked, too_big, failed)
- Overall progress percentage

### Task Management

Use Beads (`bd`) commands directly for task management:

```bash
# List tasks
bd list
bd list --status=open
bd list --json

# Show task details
bd show <task-id>

# Add discovered work
bd create --title="Fix discovered bug" --priority=1 --deps=discovered-from:<parent-task-id>

# Mark task as too big
bd update <task-id> --status=too_big
```

For full Beads documentation, see: https://github.com/beadsx/beads

### `hive merge`

Assist with manual merge resolution for conflicted tasks.

```bash
# Resolve conflicts for a task
hive merge hive-abc

# Resolve conflicts for specific worktree
hive merge worker-1-hive-abc

# Just cleanup after manual merge
hive merge hive-abc --cleanup-only

# Force cleanup even with uncommitted changes
hive merge hive-abc --cleanup-only --force
```

**Workflow:**
1. Shows conflict status and files
2. Guides you through resolution
3. After resolution, merges to main
4. Cleans up worktree and branch
5. Prompts to close task in Beads

**Identifier formats:**
- Task ID: `hive-abc`
- Worker-task combo: `worker-1-hive-abc`
- Full worktree path: `worktrees/worker-1-hive-abc`

### `hive sync`

Synchronize all worker branches with remote.

```bash
# Push and pull all task branches
hive sync

# Push only
hive sync --push

# Pull only
hive sync --pull

# Show what would be done
hive sync --dry-run
```

**Use cases:**
- Share work-in-progress branches with team
- Pull updates from remote workers
- Keep all task branches synchronized

### `hive daemon`

Monitor workers and detect stuck tasks in the background.

```bash
# Start daemon
hive daemon start

# Start with custom settings
hive daemon start --check-interval 30 --stuck-threshold 600 --notify

# Start in foreground (for debugging)
hive daemon start --foreground

# Check daemon status
hive daemon status

# Check status with JSON output
hive daemon status --json

# View daemon logs
hive daemon logs

# Follow logs (like tail -f)
hive daemon logs --follow

# Stop daemon
hive daemon stop
```

**Features:**
- Polls worker registry for stuck workers (no activity for threshold)
- Logs stuck worker events to `.hive/daemon.log`
- Optional desktop notifications on stuck workers
- Runs in background, safe to close terminal

**Options:**
- `--check-interval` - How often to check (seconds, default: 60)
- `--stuck-threshold` - No activity threshold (seconds, default: 300)
- `--notify` - Enable desktop notifications (requires `notify-send`)

**Use cases:**
- Long-running parallel workers
- Detect hung or crashed agents
- Monitor overnight task execution

## Configuration

`.hive/config.toml`:

```toml
[workers]
spawn_grace_period_seconds = 30  # How long to wait before detecting spawn failure
max_parallel_workers = 8          # Hard limit on parallel workers

[tasks]
default_timeout_seconds = 3600    # Default task timeout (1 hour)
poll_interval_seconds = 5         # How often to check Beads for completion

[agent]
command = "claude-code"           # Agent command to spawn
shell = "bash"                    # Shell to use
```

## Task States

Tasks flow through these states:

1. **open** - Ready to be claimed by a worker
2. **in_progress** - Currently being worked on
3. **closed** - Completed successfully
4. **blocked** - Blocked by dependencies or conflicts
5. **too_big** - Needs to be decomposed into smaller tasks
6. **failed** - Failed to complete

**State Transitions:**

```
open → in_progress → closed
    ↓             ↓
  failed      too_big
                 ↓
             blocked
```

**Important:** A task may only transition from `open → in_progress` once (atomic claim guarantee).

## Merge Policy

After a task completes successfully:

1. **Automatic merge to main** (if no conflicts)
   - Worker merges task branch
   - Removes worktree
   - Task marked as closed

2. **Merge conflict** (if conflicts detected)
   - Worker marks task as `blocked`
   - Preserves worktree for human inspection
   - Human resolves conflict manually
   - Human merges and closes task

**Manual merge resolution (recommended):**

```bash
# Use the merge command for guided resolution
hive merge hive-abc
# Follow the prompts to resolve conflicts
# After resolution, run again to complete merge
hive merge hive-abc

# Close task
bd close hive-abc
```

**Manual merge resolution (alternative):**

```bash
# Find conflicted task
hive status

# Navigate to worktree
cd worktrees/worker-1-hive-abc

# Resolve conflicts manually
git status
# ... edit files ...
git add .
git commit

# Use merge command to complete cleanup
cd ../..
hive merge hive-abc

# Close task
bd close hive-abc
```

## Parallelization Rules

**Default: Serial execution.** One worker, one task at a time. This is the safest mode.

**Parallel when:**
1. Tasks have no `blocked-by` relationship
2. Tasks touch different areas of the codebase
3. Human explicitly runs `hive work --parallel N`

**How parallel workers coordinate:**
- Each worker claims tasks via atomic `bd update --claim`
- If a task is already `in_progress`, the claim fails and worker retries
- Blocked tasks wait until their dependencies are `closed` AND merged
- Each worker operates in isolated worktree

**Conflict avoidance:**
- Planning phase should identify tasks that might conflict
- Conflicting tasks should have explicit `blocked-by` relationships
- When in doubt, run serial

## Worktree Management

Each task gets its own isolated worktree:

```
worktrees/<worker-id>-<task-id>/
```

**Why unique naming?**
- Prevents accidental deletion after crashes
- Allows recovery if worker crashes and restarts
- Enables parallel execution without collisions
- Preserves failed work for debugging

**Lifecycle:**

```bash
# Create (done by ralph loop)
git worktree add worktrees/worker-1-hive-abc -b task-hive-abc main

# Worker operates here
cd worktrees/worker-1-hive-abc
# ... agent does work ...

# Merge (done by ralph loop or human)
git checkout main
git merge task-hive-abc
git branch -d task-hive-abc

# Cleanup (done by ralph loop or human)
git worktree remove worktrees/worker-1-hive-abc
```

## Spawn Failure Detection

After spawning an agent, Hive waits for a grace period (default 30s) to verify the agent started successfully.

**Checks:**
1. Did the task status change? (agent is working)
2. Is there output in tmux? (agent produced something)
3. Does tmux session still exist? (didn't crash immediately)

**If all checks fail:**
- Mark task as `failed` with reason `agent_spawn_failed`
- Cleanup worktree
- Continue to next task

**Common causes:**
- Missing `claude-code` binary
- Agent crashes on startup
- Permission issues

## Context Generation

Each task receives fresh context via `CLAUDE.md` in its worktree.

**Includes:**
- Task ID and title
- Task description
- Acceptance criteria
- Project plan (from `.hive/plan.md`)
- Instructions for completion:
  - Mark done: `bd close $TASK_ID`
  - Mark too big: `bd update $TASK_ID --status too_big`
  - Mark blocked: `bd update $TASK_ID --status blocked`
  - Discovered work: `bd create --title="..." --discovered-from=$TASK_ID`

## Dependency Tracking

Tasks can depend on other tasks via `blocked-by` relationships.

```bash
# Create tasks
bd create --title="Implement user model" --type=task
bd create --title="Add user endpoints" --type=task

# Add dependency (endpoints depend on model)
bd dep add hive-endpoints hive-model

# Check what's ready
bd ready
```

**Ralph loop respects dependencies:**
- Only returns tasks where ALL dependencies are `closed` (done AND merged)
- In-progress dependencies block dependent tasks
- Failed dependencies block dependent tasks

## Discovered Work

Agents can discover additional work during execution.

**From agent:**

```bash
# Agent discovers a bug while working on feature
bd create --title="Fix discovered validation bug" --deps=discovered-from:hive-abc
```

This links the new work to the parent task for traceability.

## Too-Big Workflow

If a task is too large for a single session, the agent marks it as `too_big`.

**Process:**

1. Agent marks task: `bd update hive-abc --status too_big`
2. Human runs: `hive plan --continue`
3. Hive shows decomposition instructions
4. Human breaks task into subtasks:

```bash
bd create --title="Subtask 1" --type=task --priority=1
bd create --title="Subtask 2" --type=task --priority=1
bd dep add hive-subtask2 hive-subtask1  # If order matters
bd close hive-abc --reason="Decomposed into subtasks"
```

5. Workers continue with smaller tasks

## Common Workflows

### Single Developer, Serial Execution

```bash
# 1. Plan work
hive plan "Add search feature"
hive plan --approve

# 2. Execute serially
hive work

# 3. Monitor (in another terminal)
watch -n 5 hive status
```

### Team, Parallel Execution

```bash
# 1. Plan work collaboratively
hive plan "Refactor API layer"
hive plan --approve

# 2. Start multiple workers
hive work --parallel 3

# 3. Monitor progress
hive status --json | jq '.workers'
```

### Handling Merge Conflicts

```bash
# 1. Status shows blocked task
hive status
# Output: Task hive-abc blocked (merge conflict)

# 2. Use merge command (shows conflict status)
hive merge hive-abc
# Output: Shows conflicted files and next steps

# 3. Navigate to worktree and resolve
cd worktrees/worker-1-hive-abc
git status
vim conflicted-file.py
git add conflicted-file.py
git commit

# 4. Complete the merge
cd ../..
hive merge hive-abc
# Automatically merges to main, cleans up worktree

# 5. Close task
bd close hive-abc
```

### Decomposing Large Tasks

```bash
# 1. Worker marks task too big
# (Agent runs: bd update hive-abc --status too_big)

# 2. Get decomposition guide
hive plan --continue

# 3. Create subtasks
bd create --title="Part 1: Database schema" --priority=1
bd create --title="Part 2: API endpoints" --priority=1
bd create --title="Part 3: Frontend UI" --priority=1

# 4. Add dependencies if needed
bd dep add hive-part2 hive-part1
bd dep add hive-part3 hive-part2

# 5. Close original task
bd close hive-abc --reason="Decomposed into 3 parts"

# 6. Continue execution
hive work
```

## Troubleshooting

### Worker Not Starting

**Symptom:** `hive work` exits immediately with "No tasks remaining"

**Causes:**
- No tasks in `open` state
- All tasks are blocked by dependencies

**Solution:**

```bash
bd ready  # Check what's available
bd list --status=open  # See open tasks
bd show <task-id>  # Check dependencies
```

### Spawn Failures

**Symptom:** Tasks marked as `failed` with `agent_spawn_failed`

**Causes:**
- `claude-code` not in PATH
- Agent crashes on startup
- Permission issues

**Solution:**

```bash
# Test agent manually
claude-code --version

# Check PATH
which claude-code

# Try spawning manually
tmux new-session -d -s test-session
tmux send-keys -t test-session "claude-code" Enter
tmux attach -t test-session
```

### Stuck Workers

**Symptom:** `hive status` shows workers with old `last_activity`

**Causes:**
- Agent hung or stuck
- Task taking longer than expected
- Network issues

**Solution:**

```bash
# Check worker's tmux session
tmux attach -t hive-worker-1-task-abc

# Kill stuck worker
tmux kill-session -t hive-worker-1-task-abc

# Mark task as failed
bd update task-abc --status failed --notes "Worker stuck, killed manually"

# Cleanup worktree
git worktree remove --force worktrees/worker-1-task-abc
```

### Merge Conflicts

**Symptom:** Task marked as `blocked`, worktree preserved

**Solution:** See "Handling Merge Conflicts" workflow above.

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=hive --cov-report=html

# Run specific test
pytest tests/test_work.py::test_claim_task_success

# Lint code
ruff check hive/

# Format code
ruff format hive/
```

## Architecture

See [hive-plan.md](./hive-plan.md) for the complete design document, including:
- Detailed architecture diagrams
- Design decisions and rationale
- Implementation phases
- Data structures
- Edge case handling

## License

MIT
