# Getting Started with Hive

Hive is a lightweight orchestrator for coordinating LLM coding agents. It helps AI agents work on your codebase safely using battle-tested primitives: tmux for persistence, git worktrees for isolation, and Beads for task tracking.

## Prerequisites

Before installing Hive, ensure you have:

- **Python 3.8+** (3.12+ recommended)
- **Git** (with a git repository initialized)
- **tmux** (for session management)
- **Beads** (task management tool)
- **Claude Code** (or another LLM coding agent)

## Installation

### 1. Install Beads

```bash
pip install beads
```

### 2. Install Hive

Clone the repository and install in editable mode:

```bash
git clone https://github.com/yourusername/hive.git
cd hive
pip install -e .
```

This creates the `hive` command in your system.

## Setup on a New Project

Navigate to your project directory and initialize both Beads and Hive:

```bash
# Go to your project
cd your-project

# Initialize Beads (task tracking)
bd init

# Initialize Hive (orchestration)
hive init
```

This creates:
- `.beads/` — Task database and git hooks
- `.hive/` — Hive configuration and workspace
- `worktrees/` — Directory for task isolation (git worktrees)

## Basic Workflow

### Step 1: Create a Plan

Start by describing what you want to accomplish:

```bash
hive plan "Add user authentication system"
```

This opens an interactive planning session with an AI agent. The agent will:
- Analyze your codebase
- Break down the goal into concrete tasks
- Create a plan in `.hive/plan.md`

### Step 2: Approve the Plan

Review the generated plan:

```bash
hive plan --show
```

If it looks good, approve it:

```bash
hive plan --approve
```

This converts the plan into actionable Beads issues with proper dependencies.

### Step 3: Execute Tasks

Start the worker to execute tasks:

```bash
hive work
```

This runs in serial mode (one task at a time), which is safest for most projects.

For independent tasks, you can enable parallel execution:

```bash
hive work --parallel 2
```

### Step 4: Monitor Progress

In another terminal, watch the progress:

```bash
hive status
```

Or continuously monitor:

```bash
watch -n 5 hive status
```

### Step 5: That's It!

Hive will:
- Automatically pick ready tasks from Beads
- Create isolated worktrees for each task
- Spawn agents to work on them
- Merge completed work back to your main branch
- Handle failures and conflicts gracefully

## Common Commands

### Planning
```bash
hive plan "goal description"    # Start interactive planning
hive plan --show                 # View current plan
hive plan --approve              # Approve and create tasks
hive plan --continue             # Continue from too_big task
```

### Execution
```bash
hive work                        # Run serial (1 worker)
hive work --parallel 3           # Run with 3 parallel workers
hive status                      # Check progress
hive status --json               # Get status as JSON
```

### Task Management (via Beads)
```bash
bd list                          # List all tasks
bd list --status=open            # Show open tasks
bd ready                         # Show tasks ready to work
bd show <task-id>                # View task details
bd close <task-id>               # Mark task complete
```

### Merge Conflicts
```bash
hive merge <task-id>            # Get help resolving conflicts
```

When conflicts occur:
1. Run `hive merge <task-id>`
2. Navigate to the worktree shown
3. Resolve conflicts manually
4. Commit the resolution
5. Run `hive merge <task-id>` again to complete

### Synchronization
```bash
hive sync                        # Push/pull all task branches
hive sync --push                 # Push only
hive sync --pull                 # Pull only
```

### Background Monitoring
```bash
hive daemon start                # Start monitoring daemon
hive daemon status               # Check daemon status
hive daemon logs                 # View daemon logs
hive daemon stop                 # Stop daemon
```

## Configuration

The `.hive/config.toml` file contains settings:

```toml
[hive]
version = "0.1.0"

[workers]
spawn_grace_period_seconds = 30
max_parallel_workers = 1
poll_interval = 5
task_timeout = 3600

[worktrees]
base_dir = "worktrees"

[agent]
command = "claude-code"
shell = "bash"

[branch]
default_branch = "main"
```

Most defaults work well, but you can customize:
- `max_parallel_workers` — Hard limit on concurrent workers
- `task_timeout` — How long a task can run (seconds)
- `agent.command` — Which AI agent to use

## Example Session

Here's a complete example workflow:

```bash
# 1. Initialize (one-time setup)
cd my-app
bd init
hive init

# 2. Plan your work
hive plan "Add email notification system"
# Review the plan
hive plan --show
# Approve it
hive plan --approve

# 3. Execute (in one terminal)
hive work

# 4. Monitor (in another terminal)
watch -n 5 hive status

# 5. When complete, check results
git log --oneline
bd stats
```

## Key Concepts

- **One task, one session** — Each agent works on exactly one task, then stops
- **Worktrees for isolation** — Every task gets its own git worktree, preventing conflicts
- **Beads is the source of truth** — All task state lives in Beads, enabling coordination
- **Serial by default** — Parallelism is opt-in because it's harder to debug
- **Fresh context** — Each task starts with clean context from the plan and task details

## Troubleshooting

**Agent fails to spawn:**
```bash
hive daemon start --foreground
```
This runs the daemon in foreground mode to see errors.

**Merge conflicts:**
```bash
hive status  # Find blocked tasks
hive merge <task-id>  # Get resolution instructions
```

**Task stuck:**
```bash
tmux ls  # Find the session
tmux attach -t hive-worker-1  # Attach to see what's happening
```

**Reset a worker:**
```bash
tmux kill-session -t hive-worker-1
# Manually update task status in Beads
bd update <task-id> --status open
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [AGENTS.md](AGENTS.md) for agent-specific instructions
- Review `.hive/plan.md` to understand plan structure
- Experiment with `hive work --parallel` for independent tasks

## Core Philosophy

Hive follows these principles:

1. **Plan first, execute second** — Collaborate with AI on a quality plan before coding
2. **Small tasks** — Tasks should complete in 30-60 minutes
3. **Disk is state** — All coordination happens through files, not memory
4. **Fresh context is reliability** — External iteration prevents context drift

Happy orchestrating!
