"""Task commands for Hive orchestrator.

Thin wrappers around Beads (bd) commands for task management.
"""

import subprocess
import sys

import click


def run_bd_command(args: list[str]):
    """Run a bd command and pass through output."""
    try:
        result = subprocess.run(
            ["bd"] + args,
            check=False,
            text=True,
        )
        sys.exit(result.returncode)
    except FileNotFoundError:
        click.echo("✗ Beads (bd) not found in PATH")
        click.echo("  Install beads first: https://github.com/beadsx/beads")
        sys.exit(1)


@click.group(name="task")
def task_cmd():
    """Manage tasks (thin wrapper around bd commands)."""
    pass


@task_cmd.command(name="list")
@click.option("--status", help="Filter by status (open, in_progress, done, etc.)")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def list_cmd(status, output_json):
    """List tasks (wraps bd list)."""
    args = ["list"]
    if status:
        args.extend(["--status", status])
    if output_json:
        args.append("--json")
    run_bd_command(args)


@task_cmd.command(name="show")
@click.argument("task_id")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def show_cmd(task_id, output_json):
    """Show task details (wraps bd show)."""
    args = ["show", task_id]
    if output_json:
        args.append("--json")
    run_bd_command(args)


@task_cmd.command(name="add")
@click.argument("description")
@click.option("--priority", type=int, default=2, help="Priority (0-4, default: 2)")
@click.option("--type", "task_type", default="task", help="Task type (default: task)")
@click.option("--discovered-from", default=None, help="Parent task ID this discovery is related to")
def add_cmd(description, priority, task_type, discovered_from):
    """Add a new task for discovered work (wraps bd create)."""
    args = [
        "create",
        "--title", description,
        "--type", task_type,
        "--priority", str(priority),
        "--notes", "Created via hive task add (discovered work)",
    ]
    if discovered_from:
        args.extend(["--deps", f"discovered-from:{discovered_from}"])
    run_bd_command(args)


@task_cmd.command(name="too-big")
@click.argument("task_id")
def too_big_cmd(task_id):
    """Mark a task as too big for decomposition (wraps bd update --status too_big)."""
    args = ["update", task_id, "--status", "too_big"]
    run_bd_command(args)
