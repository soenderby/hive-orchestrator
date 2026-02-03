"""Hive init command - setup project structure."""

import os
import json
import sys
from pathlib import Path
import click

try:
    import tomli_w
except ImportError:
    import tomllib as tomli_w  # Python 3.11+


@click.command(name="init")
def init_cmd():
    """Initialize Hive in the current directory.

    This command:
    - Creates .hive/ directory structure
    - Initializes config.toml, workers.json, and plan.md
    - Creates worktrees/ directory
    - Verifies beads is initialized
    """
    project_root = Path.cwd()
    hive_dir = project_root / ".hive"
    worktrees_dir = project_root / "worktrees"
    beads_dir = project_root / ".beads"

    # Check if already initialized
    if hive_dir.exists():
        click.echo("⚠ Hive already initialized (.hive/ exists)")
        if not click.confirm("Reinitialize?", default=False):
            click.echo("Aborted.")
            return

    # Verify beads is initialized
    if not beads_dir.exists():
        click.echo("✗ Beads not initialized (.beads/ not found)")
        click.echo("  Please run 'bd init' first")
        sys.exit(1)

    # Create .hive/ directory
    hive_dir.mkdir(exist_ok=True)
    click.echo("✓ Created .hive/")

    # Create config.toml
    config_path = hive_dir / "config.toml"
    config = {
        "hive": {
            "version": "0.1.0",
        },
        "workers": {
            "spawn_grace_period_seconds": 30,
            "max_parallel_workers": 1,
            "poll_interval": 5,
            "task_timeout": 3600,
        },
        "worktrees": {
            "base_dir": "worktrees",
        },
        "agent": {
            "command": "claude-code",
            "shell": "bash",
        },
        "branch": {
            "default_branch": "main",
        },
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)
    click.echo("✓ Created .hive/config.toml")

    # Create workers.json (empty registry)
    workers_path = hive_dir / "workers.json"
    workers = {
        "workers": [],
        "last_updated": None,
    }

    with open(workers_path, "w") as f:
        json.dump(workers, f, indent=2)
    click.echo("✓ Created .hive/workers.json")

    # Create plan.md (empty template)
    plan_path = hive_dir / "plan.md"
    plan_template = """# Hive Plan

> **Status:** Draft

## Goal

[Describe the high-level goal of this plan]

## Tasks

[Tasks will be managed in Beads - see `bd list`]

## Notes

[Any important context, decisions, or constraints]
"""

    with open(plan_path, "w") as f:
        f.write(plan_template)
    click.echo("✓ Created .hive/plan.md")

    # Create worktrees/ directory
    worktrees_dir.mkdir(exist_ok=True)
    click.echo("✓ Created worktrees/")

    # Add .gitignore for worktrees
    gitignore_path = worktrees_dir / ".gitignore"
    with open(gitignore_path, "w") as f:
        f.write("# Ignore all worktrees (they're git worktrees, not regular files)\n")
        f.write("*\n")
        f.write("!.gitignore\n")
    click.echo("✓ Created worktrees/.gitignore")

    click.echo("")
    click.echo("✓ Beads already initialized (.beads/)")
    click.echo("✓ Ready to plan")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  hive plan \"<goal description>\"  # Start planning")
    click.echo("  bd ready                         # Check available tasks")
