# Hive: A Small Multi-Agent Orchestrator

> **Revision note:** This version incorporates correctness, robustness, and clarity improvements identified during formal review. The core architecture and philosophy are unchanged; added material focuses on atomic task claiming, safer worktree identity, canonical task states, explicit human responsibility boundaries, and a defined agent-spawn failure mode.

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
blocked | too_big | failed
```

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
│ • Task states   │   │ • Health check  │   │ • Claim task    │
│ • Dependencies  │   │ • Stuck detect  │   │ • Spawn agent   │
│ • Work discovery│   │ • Status report │   │ • Observe state │
└─────────────────┘   └─────────────────┘   └─────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  TMUX Session   │   │  TMUX Session   │   │  TMUX Session   │
│ (worker-task)  │   │ (worker-task)   │   │   (planner)     │
└─────────────────┘   └─────────────────┘   └─────────────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │    SHARED REPO      │
         │                     │
         │  ├── .beads/        │
         │  ├── .hive/         │
         │  ├── worktrees/     │
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

---

## Agent Spawn Failure Handling

A common failure mode is that an agent session starts but never becomes active (missing binary, instant crash, etc.).

### Defined Rule

After spawning an agent:

- If **no tmux pane output** and **no Beads state change** occurs within a configurable grace period (e.g. 30s):

```
status → failed
reason → agent_spawn_failed
```

This prevents tasks from remaining stuck in `in_progress` indefinitely.

---

## Two-Phase Workflow

### Phase 1: Planning (Human + Agent)

Planning is interactive and blocking. No worker may start until the plan is approved.

**Outputs:**
- Tasks in Beads with acceptance criteria
- Dependency graph
- Parallelization notes
- Risk flags

Tasks must obey the **single-session rule**. Oversized tasks are decomposed during planning.

---

### Phase 2: Execution (Workers)

Workers run a Ralph loop until no claimable tasks remain.

Parallel execution is explicitly opt-in and conservative.

---

## The Ralph Loop (Per Worker)

1. Query Beads for claimable tasks
2. Atomically claim a task
3. Create a unique worktree from `main`
4. Generate `CLAUDE.md` context
5. Spawn agent in tmux
6. Observe Beads for completion signal
7. Kill agent session
8. Merge or preserve worktree based on outcome

The agent **never** exits the loop; only Beads state changes matter.

---

## Merge Policy

### Default: Auto-Merge

On successful completion:
- Merge task branch into `main`
- Cleanup worktree

This is required to unblock dependent tasks.

### Merge Outcomes

| Task Result | Action |
|------------|--------|
| done, clean merge | Merge + cleanup |
| done, conflict | Abort merge, mark `blocked`, preserve worktree |
| too_big | Cleanup, await human decomposition |
| blocked | Preserve worktree |
| failed | Cleanup |

---

## Configuration

```toml
[execution]
task_timeout = "60m"
spawn_grace_period = "30s"

[merge]
auto_merge = true
require_tests = false
test_command = "make test"

[parallel]
default_workers = 1
max_workers = 4
```

---

## Mental Model (One Page)

- **Hive**: task orchestrator + git worktree manager
- **Agents**: disposable, single-task workers
- **Beads**: durable memory and coordination layer
- **Git**: the only shared state
- **Humans**: approve plans, resolve ambiguity, handle conflicts

If you understand this page, you understand Hive.

---

## Status

With these constraints and guardrails, Hive is:

- Correct under parallel execution
- Recoverable under failure
- Small enough to reason about
- Explicit about what it automates — and what it does not

This document is considered **build-ready**.
