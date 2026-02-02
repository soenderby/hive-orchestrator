# Hive

A lightweight orchestrator for coordinating LLM coding agents using battle-tested primitives.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Initialize in your project (requires beads to be initialized first)
hive init

# Start planning (coming soon)
hive plan "Add user authentication"

# Execute work (coming soon)
hive work

# Check status (coming soon)
hive status
```

## Philosophy

> "Disk is state, git is memory. Fresh context is reliability."

Hive coordinates agents through:
- **tmux** - Session persistence
- **git worktrees** - Filesystem isolation per task
- **Beads** - Persistent task memory and dependency tracking
- **Ralph-style loops** - External iteration with fresh context each cycle

See [hive-plan.md](./hive-plan.md) for the complete design.

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run hive
hive --help
```
