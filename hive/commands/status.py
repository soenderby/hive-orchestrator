"""Status command for Hive orchestrator.

Shows the current state of workers, tasks, and overall progress.
"""

import json
import subprocess
from pathlib import Path

import click


@click.command(name="status")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def status_cmd(output_json):
    """Show current workers, tasks, and progress.

    Displays:
    - Active workers and their current tasks
    - Task statistics (open, in_progress, done, blocked)
    - Overall progress
    """
    repo_root = Path.cwd()
    workers_path = repo_root / ".hive/workers.json"

    # Check prerequisites
    if not workers_path.exists():
        click.echo("✗ Hive not initialized (.hive/workers.json not found)")
        click.echo("  Run 'hive init' first")
        return

    # Read worker registry
    try:
        with open(workers_path) as f:
            worker_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        worker_data = {"workers": [], "last_updated": None}

    workers = worker_data.get("workers", [])

    # Get task statistics from beads
    try:
        result = subprocess.run(
            ["bd", "list", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        all_tasks = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        all_tasks = []

    # Count tasks by status
    task_counts = {
        "open": 0,
        "in_progress": 0,
        "closed": 0,
        "blocked": 0,
        "too_big": 0,
        "failed": 0,
    }

    for task in all_tasks:
        status = task.get("status", "open")
        if status in task_counts:
            task_counts[status] += 1
        else:
            task_counts["open"] += 1  # Default to open for unknown statuses

    # Output in JSON format if requested
    if output_json:
        output = {
            "workers": workers,
            "task_counts": task_counts,
            "total_tasks": len(all_tasks),
        }
        click.echo(json.dumps(output, indent=2))
        return

    # Display human-readable status
    click.echo("=" * 60)
    click.echo("HIVE STATUS")
    click.echo("=" * 60)
    click.echo()

    # Workers section
    if workers:
        click.echo(f"Active Workers: {len(workers)}")
        click.echo("-" * 60)
        for worker in workers:
            worker_id = worker.get("id", "unknown")
            current_task = worker.get("current_task", "none")
            tmux_session = worker.get("tmux_session", "unknown")
            started_at = worker.get("started_at", "unknown")
            last_activity = worker.get("last_activity", "unknown")

            click.echo(f"  {worker_id}")
            click.echo(f"    Task: {current_task}")
            click.echo(f"    Session: {tmux_session}")
            click.echo(f"    Started: {started_at}")
            click.echo(f"    Last activity: {last_activity}")
            click.echo()
    else:
        click.echo("Active Workers: 0")
        click.echo("-" * 60)
        click.echo("  No active workers")
        click.echo()

    # Task statistics
    click.echo("Task Statistics:")
    click.echo("-" * 60)
    click.echo(f"  Total: {len(all_tasks)}")
    click.echo(f"  Open: {task_counts['open']}")
    click.echo(f"  In Progress: {task_counts['in_progress']}")
    click.echo(f"  Closed: {task_counts['closed']}")
    click.echo(f"  Blocked: {task_counts['blocked']}")
    click.echo(f"  Too Big: {task_counts['too_big']}")
    click.echo(f"  Failed: {task_counts['failed']}")
    click.echo()

    # Progress summary
    total = len(all_tasks)
    if total > 0:
        done_count = task_counts["closed"]
        progress = (done_count / total) * 100
        click.echo(f"Overall Progress: {done_count}/{total} ({progress:.1f}%)")
    else:
        click.echo("Overall Progress: No tasks")

    click.echo("=" * 60)
