# Hive: A Small Multi-Agent Orchestrator

> **Status:** This document is considered **build-ready**.

---

## Overview

**Hive** is a lightweight orchestrator for coordinating LLM coding agents using battle-tested primitives:

- **tmux** — Session persistence
- **git worktrees** — Filesystem isolation per task
- **Beads** — Persistent task memory and dependency tracking
- **Ralph-style loops** — External iteration with fresh context each cycle

### Philosophy

> "Disk is state, git is memory. Fresh context is reliability."

**Core principles:**

1. **Plan first, execute second** — Human + agent collaborate on a quality plan before any worker starts
2. **One task, one session** — An agent performs exactly one task, then stops
3. **Serial by default** — Parallelism is opt-in and conservative
4. **Small tasks** — Tasks must fit in a single agent session (~30–60 minutes)
5. **Beads is the source of truth** — All coordination flows through task state, not messages

### What Is a Ralph Loop?

A **Ralph loop** is an external orchestration loop that:
- Claims exactly one task
- Spawns a fresh agent with minimal context
- Observes completion via disk-backed state (Beads + git)
- Terminates the agent explicitly

This avoids context accumulation and makes failure recovery explicit and inspectable.

---

## Non-Goals

Hive explicitly does **not** attempt to provide:

- Long-running or self-looping agents
- Conversational agent handoffs
- Autonomous task decomposition
- Cloud-scale orchestration
- Event-driven or message-based coordination

These are deliberately excluded to keep the system small, inspectable, and reliable.

---

## Canonical Task Model

### Task States (Authoritative)

All task states are **lowercase** and must be used consistently by humans, agents, and scripts:

```
planned → in_progress → done
                ↓
        blocked | too_big | failed
```

| State | Meaning |
|-------|---------|
| `planned` | Task exists, not started |
| `in_progress` | Worker is executing |
| `done` | Completed and merged |
| `blocked` | Waiting on dependency or human |
| `too_big` | Needs decomposition |
| `failed` | Error, needs human review |

### Atomic Claim Requirement

A task **must be atomically claimed** before execution.

**Invariant:** A task may only transition from `planned → in_progress` once.

This is guaranteed by one of the following (implementation choice):

- `bd update` fails if the current status is not `planned`, **or**
- A dedicated `bd claim <task_id> --worker <id>` operation with compare-and-swap semantics

All worker loops rely on this invariant for correctness under parallel execution.

---

## Human Responsibilities (Explicit Boundary)

Hive automates execution, not judgment. Humans are responsible for:

- Approving plans before execution
- Decomposing tasks marked `too_big`
- Resolving merge conflicts
- Deciding when parallel execution is safe
- Interpreting failed or blocked tasks

Hive will never attempt to automate these decisions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         HIVE CLI                             │
│     hive init | plan | work | status | task | merge          │
└──────────────────────────────┬──────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│     BEADS       │   │   HIVE DAEMON   │   │   RALPH LOOP    │
│  (Task Memory)  │   │   (Minimal)     │   │  (Per Worker)   │
│                 │   │                 │   │                 │
│ • Plan storage  │   │ • Health check  │   │ • Claim task    │
│ • Task queue    │   │ • Stuck detect  │   │ • Spawn agent   │
│ • Dependencies  │   │ • Status report │   │ • Observe state │
│ • Work discovery│   │                 │   │                 │
└─────────────────┘   └─────────────────┘   └─────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  TMUX Session   │   │  TMUX Session   │   │  TMUX Session   │
│   (Worker 1)    │   │   (Worker 2)    │   │   (Planner)     │
│                 │   │                 │   │                 │
│ ┌─────────────┐ │   │ ┌─────────────┐ │   │ ┌─────────────┐ │
│ │ Claude Code │ │   │ │ Claude Code │ │   │ │ Claude Code │ │
│ └─────────────┘ │   │ └─────────────┘ │   │ └─────────────┘ │
│       │         │   │       │         │   │                 │
│       ▼         │   │       ▼         │   │  (Interactive   │
│ ┌─────────────┐ │   │ ┌─────────────┐ │   │   with human)   │
│ │  Worktree   │ │   │ │  Worktree   │ │   │                 │
│ │ worker-1-   │ │   │ │ worker-2-   │ │   │                 │
│ │ task-abc    │ │   │ │ task-def    │ │   │                 │
│ └─────────────┘ │   │ └─────────────┘ │   │                 │
└─────────────────┘   └─────────────────┘   └─────────────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │    SHARED REPO      │
         │                     │
         │  ├── .beads/        │  ◄── Task graph
         │  ├── .hive/         │  ◄── Config + state
         │  ├── worktrees/     │  ◄── Agent workdirs
         │  └── .git/          │
         └─────────────────────┘
```

---

## Worktree Identity (Correctness-Critical)

Each task receives its **own unique worktree**, keyed by worker **and** task ID:

```
worktrees/<worker-id>-<task-id>/
```

This prevents:
- Accidental deletion after crashes
- State corruption during restarts
- Loss of agent output needed for human inspection

The active worktree path is recorded in:
- `.hive/workers.json`
- (Optionally) Beads task notes

**Worktree lifecycle:**
```bash
# Create (done by ralph loop)
git worktree add worktrees/worker-1-hv-abc -b task-hv-abc main

# Worker operates here
cd worktrees/worker-1-hv-abc
# ... agent does work ...

# Merge (done by hive merge)
git checkout main
git merge task-hv-abc
git branch -d task-hv-abc

# Cleanup (done by hive cleanup)
git worktree remove worktrees/worker-1-hv-abc
```

### Directory Structure

```
project/
├── .git/                      # Shared git database
├── .beads/                    # Shared task memory
├── .hive/
│   ├── config.toml            # Configuration
│   ├── workers.json           # Active worker registry
│   └── plan.md                # Current plan (human readable)
├── worktrees/
│   ├── worker-1-hv-a1b2/      # Isolated filesystem (worker + task)
│   │   ├── ... (project files)
│   │   └── CLAUDE.md          # Generated context
│   └── worker-2-hv-c3d4/
└── ... (main branch files)
```

---

## Agent Spawn Failure Handling

A common failure mode is that an agent session starts but never becomes active (missing binary, instant crash, etc.).

### Defined Rule

After spawning an agent:

- If **no tmux pane output** and **no Beads state change** occurs within a configurable grace period (default: 30s):

```
status → failed
reason → agent_spawn_failed
```

This prevents tasks from remaining stuck in `in_progress` indefinitely.

---

## Two-Phase Workflow

### Phase 1: Planning (Human + Agent)

Before any worker executes, create a quality plan collaboratively.

```bash
hive plan "Add user authentication with OAuth"
```

This starts an interactive planning session:

```
┌─────────────────────────────────────────────────────────────┐
│                    PLANNING SESSION                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Human provides goal  │
              │  + constraints        │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Agent asks questions │
              │  to clarify scope     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Agent proposes       │
              │  approach + breakdown │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Human reviews,       │
              │  requests changes     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Iterate until        │
              │  plan is solid        │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Agent creates Beads  │
              │  with dependencies    │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Human approves plan  │
              │  hive plan --approve  │
              └───────────────────────┘
```

**Planning outputs:**
- Tasks in Beads with clear acceptance criteria
- Dependency graph (what blocks what)
- Parallelization notes (what can run concurrently)
- Risk flags (tasks that might conflict)

**Task size rule:** Each task should be completable in a single agent session (~30-60 min of work). If a task is too big, break it down during planning.

### Phase 2: Execution (Worker Agents)

Once the plan is approved, workers execute it.

```bash
# Serial execution (safest)
hive work

# Parallel execution (only for independent tasks)
hive work --parallel 2
```

---

## The Ralph Loop

**The Ralph Loop** runs for each worker:

```
┌─────────────────────────────────────────────────────────────┐
│                      RALPH LOOP                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                 ┌────────────────┐
                 │ Get next task  │
                 │ from Beads     │
                 └───────┬────────┘
                         │
                    (no tasks)
                         ├─────────────────► EXIT
                         │
                    (task found)
                         │
                         ▼
                 ┌────────────────┐
                 │ Atomic claim   │
                 │ status →       │
                 │ in_progress    │
                 └───────┬────────┘
                         │
                    (claim failed = race)
                         ├─────────────────► (retry from top)
                         │
                    (claim succeeded)
                         │
                         ▼
                 ┌────────────────┐
                 │ Create unique  │
                 │ worktree from  │
                 │ main           │
                 └───────┬────────┘
                         │
                         ▼
                 ┌────────────────┐
                 │ Generate       │
                 │ CLAUDE.md      │
                 └───────┬────────┘
                         │
                         ▼
                 ┌────────────────┐
                 │ Spawn agent    │
                 │ in tmux        │
                 └───────┬────────┘
                         │
                         ▼
                 ┌────────────────┐
                 │ Grace period   │◄──────┐
                 │ check (30s)    │       │
                 └───────┬────────┘       │
                         │                │
                    (no activity)         │
                         ├───► mark failed, cleanup
                         │                │
                    (activity detected)   │
                         │                │
                         ▼                │
                 ┌────────────────┐       │
                 │ Poll Beads     │◄──────┤
                 │ for status     │       │
                 │ change         │       │ (still in_progress)
                 └───────┬────────┘       │
                         │                │
                    ┌────┴────┐           │
                    │         │           │
              (changed)  (timeout) ───────┤
                    │         │           │
                    │         ▼           │
                    │    ┌─────────┐      │
                    │    │ Mark    │      │
                    │    │ failed  │      │
                    │    └────┬────┘      │
                    │         │           │
                    ▼         │           │
           ┌────────────────┐ │           │
           │ Kill tmux      │◄┘           │
           │ session        │             │
           └───────┬────────┘             │
                   │                      │
        ┌──────────┼──────────┬───────────┘
        │          │          │
        ▼          ▼          ▼
      done      too_big   blocked/failed
        │          │          │
        ▼          │          │
┌──────────────┐   │          │
│ Merge to     │   │          │
│ main         │   │          │
└──────┬───────┘   │          │
       │           │          │
  ┌────┴────┐      │          │
  │         │      │          │
clean    conflict  │          │
  │         │      │          │
  ▼         ▼      ▼          ▼
┌─────┐ ┌──────┐ ┌─────┐ ┌─────────┐
│Clean│ │Mark  │ │Clean│ │Keep     │
│up   │ │block │ │up   │ │worktree │
│work │ │keep  │ │work │ │for      │
│tree │ │work  │ │tree │ │inspect  │
└──┬──┘ │tree  │ └──┬──┘ └────┬────┘
   │    └──┬───┘    │         │
   │       │        │         │
   └───────┴────────┴─────────┘
                   │
                   ▼
            (continue loop)
```

### How Completion Signaling Works

The agent doesn't "exit" — it signals completion through Beads:

1. Agent runs `bd close $TASK_ID` when done
2. Ralph loop polls Beads every 5 seconds
3. When status changes from `in_progress`, loop knows agent is finished
4. Loop kills the tmux session and proceeds

This is reliable because Beads is already the source of truth for task state.

### The Script: `hive-ralph-loop.sh`

```bash
#!/bin/bash
# hive-ralph-loop.sh
#
# Runs one worker through the task queue until empty.
# Each task gets a fresh agent session.

set -euo pipefail

WORKER_ID="${1:-worker-$$}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
TASK_TIMEOUT="${TASK_TIMEOUT:-3600}"  # 60 min default
SPAWN_GRACE="${SPAWN_GRACE:-30}"      # 30s spawn check

log() { echo "[$(date +%H:%M:%S)] [$WORKER_ID] $*"; }

cleanup_worktree() {
    local worktree_path=$1
    local branch=$2
    log "Cleaning up worktree: $worktree_path"
    git worktree remove "$worktree_path" --force 2>/dev/null || true
    git branch -D "$branch" 2>/dev/null || true
}

kill_session() {
    local session=$1
    tmux kill-session -t "$session" 2>/dev/null || true
}

check_tmux_activity() {
    local session=$1
    # Check if there's any pane content beyond the initial prompt
    local content=$(tmux capture-pane -t "$session" -p 2>/dev/null | wc -l)
    [ "$content" -gt 2 ]
}

# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------

log "Starting ralph loop"

while true; do
    # -------------------------------------------------
    # 1. GET NEXT TASK
    # -------------------------------------------------

    TASK_JSON=$(bd ready --json 2>/dev/null | jq -r '.[0] // empty')

    if [ -z "$TASK_JSON" ]; then
        log "No tasks remaining. Exiting."
        exit 0
    fi

    TASK_ID=$(echo "$TASK_JSON" | jq -r '.id')
    TASK_TITLE=$(echo "$TASK_JSON" | jq -r '.title')

    log "Picked task: $TASK_ID - $TASK_TITLE"

    # -------------------------------------------------
    # 2. ATOMIC CLAIM (must succeed or retry)
    # -------------------------------------------------

    if ! bd update "$TASK_ID" --status in_progress --notes "Claimed by $WORKER_ID"; then
        log "Failed to claim task (race condition or invalid state). Retrying..."
        sleep 1
        continue
    fi

    # -------------------------------------------------
    # 3. CREATE UNIQUE WORKTREE (worker + task)
    # -------------------------------------------------

    BRANCH="task-$TASK_ID"
    WORKTREE_PATH="worktrees/${WORKER_ID}-${TASK_ID}"
    TMUX_SESSION="hive-${WORKER_ID}-${TASK_ID}"

    log "Creating worktree: $WORKTREE_PATH on branch: $BRANCH"

    # Remove stale worktree if exists (from prior crash)
    git worktree remove "$WORKTREE_PATH" --force 2>/dev/null || true
    git branch -D "$BRANCH" 2>/dev/null || true

    # Create fresh worktree from main
    if ! git worktree add "$WORKTREE_PATH" -b "$BRANCH" main; then
        log "ERROR: Failed to create worktree"
        bd update "$TASK_ID" --status failed --notes "Worktree creation failed"
        continue
    fi

    # -------------------------------------------------
    # 4. GENERATE CONTEXT
    # -------------------------------------------------

    log "Generating CLAUDE.md"

    TASK_DETAILS=$(bd show "$TASK_ID" --json)

    cat > "$WORKTREE_PATH/CLAUDE.md" << CONTEXT_EOF
# Task: $TASK_TITLE

## Task ID
$TASK_ID

## Description
$(echo "$TASK_DETAILS" | jq -r '.description // "No description"')

## Acceptance Criteria
$(echo "$TASK_DETAILS" | jq -r '.acceptance // "No acceptance criteria specified"')

## Instructions

You are a worker agent. Complete this single task, then signal completion.

### Rules

1. **Focus only on this task.** Don't scope creep.

2. **If the task is too big** (can't finish in one session):
   \`\`\`bash
   bd update $TASK_ID --status too_big --notes "Explain why and suggest breakdown"
   \`\`\`
   Then stop working. The human will decompose it.

3. **If you discover related work** that should be done later:
   \`\`\`bash
   bd create "Description of discovered work" --discovered-from $TASK_ID
   \`\`\`
   Then continue with your current task.

4. **If you're blocked** and can't proceed:
   \`\`\`bash
   bd update $TASK_ID --status blocked --notes "What you're blocked on"
   \`\`\`
   Then stop working.

5. **When the task is complete:**
   \`\`\`bash
   # Ensure tests pass
   # (run whatever test command is appropriate)

   # Commit your work
   git add -A
   git commit -m "$TASK_TITLE"

   # Mark task done (THIS SIGNALS THE ORCHESTRATOR)
   bd close $TASK_ID --reason "Brief summary of what was done"
   \`\`\`
   Then you can stop — the orchestrator will handle the merge.

### Important

- The task is complete when \`bd close\` succeeds
- Don't worry about merging — the orchestrator handles that
- Tests should pass before marking done
- Commit messages should be descriptive

## Project Context
$(cat .hive/plan.md 2>/dev/null || echo "No plan context available.")
CONTEXT_EOF

    # -------------------------------------------------
    # 5. SPAWN AGENT
    # -------------------------------------------------

    log "Spawning agent in tmux session: $TMUX_SESSION"

    kill_session "$TMUX_SESSION"  # Clean up any stale session

    tmux new-session -d -s "$TMUX_SESSION" -c "$WORKTREE_PATH"
    tmux send-keys -t "$TMUX_SESSION" "claude" Enter

    # -------------------------------------------------
    # 6. SPAWN GRACE PERIOD CHECK
    # -------------------------------------------------

    log "Checking agent spawn (grace period: ${SPAWN_GRACE}s)..."

    sleep "$SPAWN_GRACE"

    # Check for any sign of life
    CURRENT_STATUS=$(bd show "$TASK_ID" --json | jq -r '.status')
    HAS_ACTIVITY=false

    if [ "$CURRENT_STATUS" != "in_progress" ]; then
        HAS_ACTIVITY=true  # Status changed = agent is working
    elif check_tmux_activity "$TMUX_SESSION"; then
        HAS_ACTIVITY=true  # Tmux has output = agent is working
    elif ! tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        HAS_ACTIVITY=false  # Session died = spawn failed
    fi

    if [ "$HAS_ACTIVITY" = false ]; then
        log "SPAWN FAILED: No activity detected within grace period"
        bd update "$TASK_ID" --status failed --notes "agent_spawn_failed: no activity within ${SPAWN_GRACE}s"
        kill_session "$TMUX_SESSION"
        cleanup_worktree "$WORKTREE_PATH" "$BRANCH"
        continue
    fi

    # -------------------------------------------------
    # 7. WAIT FOR COMPLETION (poll Beads)
    # -------------------------------------------------

    log "Waiting for task completion (timeout: ${TASK_TIMEOUT}s)..."

    START_TIME=$(date +%s)
    OUTCOME=""

    while true; do
        # Check timeout
        ELAPSED=$(( $(date +%s) - START_TIME ))
        if [ "$ELAPSED" -ge "$TASK_TIMEOUT" ]; then
            log "TIMEOUT: Task exceeded ${TASK_TIMEOUT}s"
            bd update "$TASK_ID" --status failed --notes "Timeout after ${TASK_TIMEOUT}s"
            OUTCOME="timeout"
            break
        fi

        # Check if tmux session died unexpectedly
        if ! tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
            log "Session died unexpectedly"
            CURRENT_STATUS=$(bd show "$TASK_ID" --json | jq -r '.status')
            if [ "$CURRENT_STATUS" = "in_progress" ]; then
                bd update "$TASK_ID" --status failed --notes "Session crashed"
                OUTCOME="crashed"
            else
                OUTCOME="$CURRENT_STATUS"
            fi
            break
        fi

        # Check Beads for status change
        CURRENT_STATUS=$(bd show "$TASK_ID" --json | jq -r '.status')

        case "$CURRENT_STATUS" in
            done)
                log "Task completed successfully"
                OUTCOME="done"
                break
                ;;
            too_big)
                log "Task marked as too big"
                OUTCOME="too_big"
                break
                ;;
            blocked)
                log "Task is blocked"
                OUTCOME="blocked"
                break
                ;;
            failed)
                log "Task failed"
                OUTCOME="failed"
                break
                ;;
        esac

        sleep "$POLL_INTERVAL"
    done

    # -------------------------------------------------
    # 8. CLEANUP AGENT
    # -------------------------------------------------

    kill_session "$TMUX_SESSION"

    # -------------------------------------------------
    # 9. HANDLE OUTCOME (including merge)
    # -------------------------------------------------

    case "$OUTCOME" in
        done)
            log "Merging branch $BRANCH to main"

            git checkout main

            if git merge "$BRANCH" --no-edit; then
                log "Merge successful"
                cleanup_worktree "$WORKTREE_PATH" "$BRANCH"
            else
                log "MERGE CONFLICT - requires human resolution"
                git merge --abort
                bd update "$TASK_ID" --status blocked \
                    --notes "Merge conflict, needs human resolution. Worktree: $WORKTREE_PATH"
                # Keep worktree for human to resolve
            fi
            ;;

        too_big)
            log "Task needs decomposition by human"
            cleanup_worktree "$WORKTREE_PATH" "$BRANCH"
            ;;

        blocked)
            log "Task blocked, preserving worktree for inspection"
            # Keep worktree, human may want to inspect
            ;;

        failed|timeout|crashed)
            log "Task failed: $OUTCOME"
            cleanup_worktree "$WORKTREE_PATH" "$BRANCH"
            ;;

        *)
            log "Unexpected outcome: $OUTCOME"
            cleanup_worktree "$WORKTREE_PATH" "$BRANCH"
            ;;
    esac

    log "--- Iteration complete ---"
    echo ""

done
```

---

## Parallelization Rules

**Default: Serial execution.** One worker, one task at a time. This is the safest mode.

**Parallel when:**
1. Tasks have no `blocked-by` relationship
2. Tasks touch different areas of the codebase
3. Human explicitly runs `hive work --parallel N`

**How parallel workers coordinate:**
- Each worker claims tasks via atomic `bd update` (or `bd claim`)
- If a task is already `in_progress`, the claim fails and worker retries
- Blocked tasks (via `blocked-by`) wait until their dependencies are `done` AND merged

**Conflict avoidance:**
- Planning phase should identify tasks that might conflict
- Conflicting tasks should have explicit `blocked-by` relationships
- When in doubt, run serial

**The `--parallel N` flag:**
- Spawns N independent ralph loops
- Each loop picks unassigned, unblocked tasks
- Beads atomic claims prevent double-assignment

---

## Merge Policy

### The Problem

Tasks may depend on each other's code:
```
Task A: Create User model        (no dependencies)
Task B: Add auth middleware      (blocked-by A, needs User model)
Task C: Write tests              (blocked-by A and B)
```

If worker-1 completes Task A but we don't merge, worker-2 can't start Task B because `main` doesn't have the User model yet.

### The Policy: Auto-Merge After Each Task

**Default behavior:** When a task completes successfully, immediately merge to main.

```
Timeline:
─────────────────────────────────────────────────────────────────────►

Worker-1: [Task A] ──commit──► bd close ──► merge to main ──► [next]
                                                │
                                                ▼
                                          main now has
                                          User model
                                                │
Worker-2:          [waiting: blocked-by A] ─────► [Task B starts]
                                                   (branches from
                                                    updated main)
```

**Why auto-merge:**
1. Unblocks dependent tasks immediately
2. No human bottleneck
3. Workers always branch from latest main

**Risk:** Merging broken code to main.

**Mitigation:**
- Agent instructions say "tests should pass before marking done"
- Optional: Add test gate before merge (configured in `.hive/config.toml`)

### Merge Outcomes

| Task Result | Action |
|-------------|--------|
| done, clean merge | Merge to main, cleanup worktree |
| done, merge conflict | Abort merge, mark `blocked`, preserve worktree |
| done, tests fail (if enabled) | Mark `failed`, cleanup worktree |
| too_big | No merge, cleanup worktree, human decomposes |
| blocked | No merge, preserve worktree for inspection |
| failed/timeout | No merge, cleanup worktree |

### Merge Conflict Handling

When a merge conflict occurs:

1. Merge is aborted (`git merge --abort`)
2. Task status set to `blocked` with note about conflict
3. Worktree is preserved (contains the agent's work)
4. Human resolves manually:

```bash
cd worktrees/worker-1-hv-abc
git checkout main
git merge task-hv-abc
# resolve conflicts
git commit
bd update hv-abc --status done
cd ../..
hive cleanup worker-1-hv-abc
```

---

## Components

### 1. Hive CLI

```bash
# Initialize
hive init                      # Setup .hive/ and verify beads installed

# Planning
hive plan "goal description"   # Start interactive planning session
hive plan --approve            # Approve current plan, ready for execution
hive plan --show               # Display current plan from beads

# Execution
hive work                      # Run serial execution (one worker)
hive work --parallel N         # Run with N parallel workers
hive work --task <id>          # Run specific task only
hive work --dry-run            # Show what would execute

# Monitoring
hive status                    # Show workers, tasks, progress
hive logs <worker>             # View worker's session log

# Task management (thin wrappers around bd)
hive task list                 # bd list
hive task show <id>            # bd show <id>
hive task add "description"    # bd create (for discovered work)
hive task too-big <id>         # Mark task for decomposition

# Git operations
hive merge <worker>            # Merge worker's branch to main
hive sync                      # Push/pull all branches
hive cleanup                   # Remove finished worktrees
```

### 2. Beads Integration

Beads is the single source of truth for all coordination.

**Key fields:**
```bash
bd create "Implement login endpoint" \
  --priority 1 \
  --blocked-by hv-abc \           # Dependency
  --module "auth" \               # For conflict detection
  --parallel-safe false \         # Default: not safe
  --acceptance "Tests pass, endpoint returns JWT"
```

**Worker discovers work during execution:**
```bash
# Agent finds something that needs doing
bd create "Add rate limiting to login" \
  --discovered-from hv-xyz \      # Links to parent task
  --priority 2
```

### 3. Minimal Daemon (`hived`)

Runs in background, does minimal coordination:

**Responsibilities:**
- Poll for stuck workers (no activity for N minutes)
- Report status when queried
- Optional: notify human of failures (desktop notification, etc.)

**Not responsible for:**
- Task assignment (workers self-assign via atomic claim)
- Event dispatch (poll-based, not push)
- Auto-restart (human decides)

```bash
hived start                    # Start daemon
hived stop                     # Stop daemon
hived status                   # Quick health check
```

### 4. Context Generation

Each worker session gets a fresh `CLAUDE.md` generated from Beads.

The ralph loop script generates this file before spawning each agent. Key sections:

1. **Task details** — ID, title, description, acceptance criteria (from Beads)
2. **Instructions** — Rules for signaling completion, handling edge cases
3. **Project context** — Contents of `.hive/plan.md` for broader context

**Agent instructions include:**
- How to mark task complete: `bd close $TASK_ID`
- How to flag task as too big: `bd update $TASK_ID --status too_big`
- How to signal blocked: `bd update $TASK_ID --status blocked`
- How to file discovered work: `bd create "..." --discovered-from $TASK_ID`

The agent doesn't need to handle merging or cleanup — the ralph loop does that after the agent signals completion.

---

## Configuration

### `.hive/config.toml`

```toml
[hive]
name = "myproject"

[agent]
command = "claude"
args = ["--dangerously-skip-permissions"]

[execution]
task_timeout = "60m"         # Max time per task
poll_interval = "5s"         # How often to check Beads for status
spawn_grace_period = "30s"   # Time to detect spawn failures

[beads]
prefix = "hv"                # Task ID prefix

[merge]
auto_merge = true            # Merge after each task (default: true)
require_tests = false        # Run tests before merge (default: false)
test_command = "make test"   # Test command (if require_tests=true)

[worktrees]
base_path = "worktrees"

[daemon]
stuck_threshold = "15m"      # Alert if no activity
poll_interval = "30s"

[parallel]
default_workers = 1          # Serial by default
max_workers = 4              # Hard limit
```

---

## Example Session

### 1. Initialize

```bash
$ cd myproject
$ hive init
✓ Created .hive/
✓ Beads already initialized (.beads/)
✓ Ready to plan
```

### 2. Plan

```bash
$ hive plan "Add user authentication with Google OAuth"

Starting planning session...
─────────────────────────────────────────────

[Agent] I'll help you plan this feature. A few questions:

1. What should happen after OAuth success - redirect or API token?
2. Do you need to store user profiles, or just validate identity?
3. Any existing auth code I should integrate with?

[Human] API token (JWT). Store basic profile (email, name).
        No existing auth, greenfield.

[Agent] Got it. Here's my proposed breakdown:

## Tasks

1. **Create user model and migration** [hv-a1b2]
   - User table: id, email, name, google_id, created_at
   - Acceptance: Migration runs, model validates email

2. **Implement OAuth callback endpoint** [hv-c3d4]
   - blocked-by: hv-a1b2 (needs User model)
   - GET /auth/google/callback
   - Acceptance: Exchanges code, creates user, returns 200

3. **Implement JWT generation** [hv-e5f6]
   - blocked-by: hv-a1b2 (needs User model)
   - Sign JWT with user ID
   - Acceptance: Returns valid JWT, can decode with secret

4. **Add auth middleware** [hv-g7h8]
   - blocked-by: hv-e5f6 (needs JWT lib)
   - Verify JWT on protected routes
   - Acceptance: Rejects invalid tokens, allows valid

5. **Write integration tests** [hv-i9j0]
   - blocked-by: hv-c3d4, hv-e5f6, hv-g7h8
   - Mock OAuth flow, test JWT validation
   - Acceptance: All tests pass

## Parallelization Notes
- hv-c3d4 and hv-e5f6 can run in parallel (both only need hv-a1b2)
- hv-g7h8 and hv-i9j0 must be serial (dependencies)

Does this look right?

[Human] Looks good. Create the beads.

[Agent] Creating tasks in Beads...

✓ hv-a1b2: Create user model and migration
✓ hv-c3d4: Implement OAuth callback endpoint (blocked-by hv-a1b2)
✓ hv-e5f6: Implement JWT generation (blocked-by hv-a1b2)
✓ hv-g7h8: Add auth middleware (blocked-by hv-e5f6)
✓ hv-i9j0: Write integration tests (blocked-by hv-c3d4, hv-e5f6, hv-g7h8)

Plan saved. Run `hive plan --approve` to start execution.
```

### 3. Approve and Execute

```bash
$ hive plan --approve
✓ Plan approved. 5 tasks ready.

$ hive work
[worker-1] Starting ralph loop
[worker-1] Picked task: hv-a1b2 - Create user model and migration
[worker-1] Creating worktree: worktrees/worker-1-hv-a1b2 on branch: task-hv-a1b2
[worker-1] Generating CLAUDE.md
[worker-1] Spawning agent in tmux session: hive-worker-1-hv-a1b2
[worker-1] Checking agent spawn (grace period: 30s)...
[worker-1] Waiting for task completion (timeout: 3600s)...

# ... agent works ...

[worker-1] Task completed successfully
[worker-1] Merging branch task-hv-a1b2 to main
[worker-1] Merge successful
[worker-1] Cleaning up worktree: worktrees/worker-1-hv-a1b2
[worker-1] --- Iteration complete ---

[worker-1] Picked task: hv-c3d4 - Implement OAuth callback endpoint
# ... continues through all tasks ...

[worker-1] No tasks remaining. Exiting.

$ hive status
┌─────────────────────────────────────────┐
│ HIVE STATUS: myproject                  │
├─────────────────────────────────────────┤
│ Tasks: 5 done, 0 active, 0 blocked      │
│ Workers: 0 active                       │
│ All work complete!                      │
└─────────────────────────────────────────┘
```

### 4. Parallel Execution

```bash
# For tasks that can safely run in parallel:
$ hive work --parallel 2

[worker-1] Starting ralph loop
[worker-2] Starting ralph loop
[worker-1] Picked task: hv-a1b2 - Create user model
[worker-2] No unblocked tasks available, waiting...

# ... worker-1 completes hv-a1b2, merges to main ...

[worker-1] Picked task: hv-c3d4 - OAuth callback
[worker-2] Picked task: hv-e5f6 - JWT generation
# Both can run: they were blocked by hv-a1b2, which is now done+merged

# ... both complete and merge ...

[worker-1] Picked task: hv-g7h8 - Auth middleware
[worker-2] No unblocked tasks available, waiting...
# hv-i9j0 still blocked by hv-g7h8

# ... worker-1 completes hv-g7h8 ...

[worker-1] Picked task: hv-i9j0 - Integration tests
[worker-2] No tasks remaining. Exiting.

# ... worker-1 completes final task ...

[worker-1] No tasks remaining. Exiting.
```

### 5. Handling "Too Big"

```bash
$ hive work

[worker-1] Picked task: hv-xyz - Implement payment system
[worker-1] Spawning agent...
[worker-1] Waiting for task completion...

# ... agent realizes scope is huge ...

[worker-1] Task marked as too big
[worker-1] Cleaning up worktree

$ hive task show hv-xyz
ID: hv-xyz
Title: Implement payment system
Status: too_big
Notes: "This requires Stripe integration, webhook handling,
        invoice generation, and refund logic. Should be 4+ tasks."

# Human decomposes the task
$ hive plan --continue
# ... planning session to break down hv-xyz ...
```

### 6. Handling Merge Conflicts

```bash
[worker-1] Task completed successfully
[worker-1] Merging branch task-hv-abc to main
[worker-1] MERGE CONFLICT - requires human resolution
[worker-1] --- Iteration complete ---

$ hive status
┌─────────────────────────────────────────┐
│ HIVE STATUS: myproject                  │
├─────────────────────────────────────────┤
│ Tasks: 3 done, 0 active, 1 blocked      │
│                                         │
│ Blocked tasks:                          │
│ - hv-abc: Merge conflict (branch saved) │
│                                         │
│ Worktrees:                              │
│ - worktrees/worker-1-hv-abc             │
└─────────────────────────────────────────┘

# Human resolves
$ cd worktrees/worker-1-hv-abc
$ git checkout main
$ git merge task-hv-abc
# ... resolve conflicts ...
$ git add -A && git commit
$ bd update hv-abc --status done
$ cd ../..
$ hive cleanup worker-1-hv-abc
```

### 7. Handling Spawn Failures

```bash
$ hive work

[worker-1] Picked task: hv-xyz - Add feature
[worker-1] Creating worktree: worktrees/worker-1-hv-xyz
[worker-1] Spawning agent in tmux session: hive-worker-1-hv-xyz
[worker-1] Checking agent spawn (grace period: 30s)...
[worker-1] SPAWN FAILED: No activity detected within grace period
[worker-1] Cleaning up worktree: worktrees/worker-1-hv-xyz
[worker-1] --- Iteration complete ---

$ hive task show hv-xyz
ID: hv-xyz
Title: Add feature
Status: failed
Notes: "agent_spawn_failed: no activity within 30s"

# Human investigates (is claude installed? PATH correct?)
```

---

## Implementation Plan

### Phase 1: Core

**Goal:** Basic planning and serial execution

**Deliverables:**
- [ ] `hive init` — setup directories
- [ ] `hive plan` — interactive planning session
- [ ] `hive work` — serial ralph loop (single worker)
- [ ] Context generation (CLAUDE.md)
- [ ] Worktree create/cleanup
- [ ] Spawn failure detection

### Phase 2: Beads Integration

**Goal:** Full task lifecycle

**Deliverables:**
- [ ] `hive task` commands wrapping `bd`
- [ ] Atomic claim semantics
- [ ] Dependency tracking integration
- [ ] `too-big` workflow
- [ ] Discovered work (`--discovered-from`)

### Phase 3: Parallel Execution

**Goal:** Safe multi-worker support

**Deliverables:**
- [ ] `hive work --parallel N`
- [ ] Conflict detection (module-based)
- [ ] Worker coordination via atomic claims
- [ ] `hive status` with multiple workers

### Phase 4: Polish

**Goal:** Production ready

**Deliverables:**
- [ ] Minimal daemon (stuck detection)
- [ ] `hive merge` workflow
- [ ] Error handling and recovery
- [ ] Documentation

---

## Data Structures

### Worker Registry (`.hive/workers.json`)

```json
{
  "workers": [
    {
      "id": "worker-1",
      "pid": 12345,
      "tmux_session": "hive-worker-1-hv-a1b2",
      "worktree": "worktrees/worker-1-hv-a1b2",
      "current_task": "hv-a1b2",
      "started_at": "2026-01-27T10:00:00Z",
      "last_activity": "2026-01-27T10:15:00Z"
    }
  ]
}
```

### Plan Metadata (`.hive/plan.md`)

Human-readable plan for context injection:

```markdown
# Plan: User Authentication

## Goal
Add user authentication with Google OAuth

## Approach
- OAuth flow returns JWT tokens
- Store minimal user profile
- Middleware protects routes

## Module Ownership
- src/models/ — user data
- src/routes/auth.ts — OAuth endpoints
- src/lib/jwt.ts — token handling
- src/middleware/auth.ts — protection

## Notes
- No rate limiting in v1
- Refresh tokens deferred to v2
```

---

## Design Decisions

### Why no Agent Mail?
Tasks in Beads handle coordination. "Blocked" is a task status with notes. "Handoff" is reassignment. Free-form messaging adds complexity without proportional value at small scale. Can add later if needed.

### Why external loops (Ralph-style)?
Agents don't naturally loop well—context accumulates, quality degrades. External loop gives fresh context each iteration. Disk (git, beads) is memory, not context window.

### Why Beads-based completion signaling?
The agent signals completion by running `bd close`. The ralph loop polls Beads for status changes. This is reliable because:
1. Beads is already the source of truth
2. No reliance on agent running shell `exit`
3. Works even if agent gets confused about instructions

### Why atomic task claiming?
Under parallel execution, two workers could pick the same task from `bd ready`. The atomic claim invariant (`planned → in_progress` exactly once) prevents double-execution. This is a correctness requirement, not an optimization.

### Why unique worktrees per task?
The original design used `worktrees/<worker-id>/`, which could be deleted prematurely if a worker crashed and restarted. Using `worktrees/<worker-id>-<task-id>/` ensures each task's work is preserved until explicitly cleaned up.

### Why spawn failure detection?
A common failure mode is the agent binary not being found or crashing immediately. Without explicit detection, the task would remain `in_progress` until timeout (potentially 60 minutes). The grace period check catches this within 30 seconds.

### Why auto-merge after each task?
Dependent tasks need the code from their dependencies. If Task B depends on Task A, B can't start until A's code is in main. Auto-merge eliminates the human bottleneck. Risk of breaking main is mitigated by requiring tests to pass before `bd close`.

### Why serial by default?
Merge conflicts are painful. Most work has subtle dependencies. Parallel execution is an optimization, not the default. Opt-in when explicitly safe.

### Why keep worktree on merge conflict?
The agent's work is valuable. If there's a merge conflict, the human needs to see what the agent did to resolve it. Deleting the worktree would lose that work.

### Why minimal daemon?
Most coordination is poll-based through Beads. Daemon just catches stuck workers. No event dispatch, no auto-restart. Simple is reliable.

---

## Mental Model (One Page)

- **Hive**: task orchestrator + git worktree manager
- **Agents**: disposable, single-task workers
- **Beads**: durable memory and coordination layer
- **Git**: the only shared state
- **Humans**: approve plans, resolve ambiguity, handle conflicts

If you understand this page, you understand Hive.

---

## Dependencies

| Component | Tool | Purpose |
|-----------|------|---------|
| Sessions | tmux | Persistent terminal sessions |
| Isolation | git worktree | Per-task directories |
| Tasks | [Beads](https://github.com/steveyegge/beads) | Task memory + dependencies |
| CLI | Go + Cobra | Fast CLI |
| Agent | Claude Code | LLM coding agent |

---

## References

- [Ralph Wiggum Playbook](https://paddo.dev/blog/ralph-wiggum-playbook/)
- [Beads: Memory for Coding Agents](https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a)
- [Gas Town](https://github.com/steveyegge/gastown)
- [Claude Squad](https://github.com/smtg-ai/claude-squad)
