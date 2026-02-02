"""Hive plan command - interactive planning sessions."""

import sys
from pathlib import Path
from datetime import datetime
import click


@click.command(name="plan")
@click.argument("goal", required=False)
@click.option("--show", is_flag=True, help="Display the current plan")
@click.option("--approve", is_flag=True, help="Approve the current plan for execution")
def plan_cmd(goal, show, approve):
    """Interactive planning session for task breakdown.

    GOAL: Description of what you want to accomplish

    Examples:
        hive plan "Add user authentication with OAuth"
        hive plan --show
        hive plan --approve
    """
    project_root = Path.cwd()
    hive_dir = project_root / ".hive"
    plan_path = hive_dir / "plan.md"

    # Check if hive is initialized
    if not hive_dir.exists():
        click.echo("✗ Hive not initialized (.hive/ not found)")
        click.echo("  Please run 'hive init' first")
        sys.exit(1)

    # Handle --show flag
    if show:
        if not plan_path.exists():
            click.echo("✗ No plan found")
            click.echo("  Create a plan with: hive plan \"<goal>\"")
            sys.exit(1)

        with open(plan_path) as f:
            content = f.read()
        click.echo(content)
        return

    # Handle --approve flag
    if approve:
        if not plan_path.exists():
            click.echo("✗ No plan found")
            click.echo("  Create a plan with: hive plan \"<goal>\"")
            sys.exit(1)

        # Check if plan has Draft status
        with open(plan_path) as f:
            content = f.read()

        if "> **Status:** Approved" in content:
            click.echo("⚠ Plan already approved")
            return

        # Update status to Approved
        updated_content = content.replace(
            "> **Status:** Draft",
            "> **Status:** Approved"
        ).replace(
            "> **Status:** In Progress",
            "> **Status:** Approved"
        )

        with open(plan_path, "w") as f:
            f.write(updated_content)

        click.echo("✓ Plan approved")
        click.echo("")
        click.echo("Next steps:")
        click.echo("  bd ready              # Check ready tasks")
        click.echo("  hive work             # Start serial execution")
        click.echo("  hive work --parallel N # Start parallel execution")
        return

    # Handle goal-based planning
    if not goal:
        click.echo("Error: Missing GOAL argument")
        click.echo("")
        click.echo("Usage:")
        click.echo("  hive plan \"<goal description>\"")
        click.echo("  hive plan --show")
        click.echo("  hive plan --approve")
        sys.exit(1)

    # Start planning session
    click.echo("Starting planning session...")
    click.echo("─────────────────────────────────────────────")
    click.echo("")
    click.echo(f"Goal: {goal}")
    click.echo("")

    # Create/update plan.md with the goal
    plan_template = f"""# Hive Plan

> **Status:** In Progress

## Goal

{goal}

## Tasks

Tasks will be managed in Beads. Use the following workflow:

1. Break down the goal into concrete tasks
2. Create tasks in Beads:
   ```bash
   bd create --title="Task description" --type=task --priority=1
   ```
3. Add dependencies between tasks:
   ```bash
   bd dep add <dependent-task> <dependency>
   ```
4. Review the task graph:
   ```bash
   bd list --status=open
   bd blocked  # Show blocked tasks
   ```
5. When ready, approve the plan:
   ```bash
   hive plan --approve
   ```

## Planning Notes

- Keep tasks small (~30-60 min of work each)
- Define clear acceptance criteria for each task
- Mark dependencies explicitly
- Note which tasks can run in parallel

## Created

{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    with open(plan_path, "w") as f:
        f.write(plan_template)

    click.echo("✓ Plan created and saved to .hive/plan.md")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Break down your goal into tasks using 'bd create'")
    click.echo("  2. Add dependencies with 'bd dep add'")
    click.echo("  3. Review with 'hive plan --show'")
    click.echo("  4. Approve with 'hive plan --approve'")
    click.echo("")
    click.echo("Example:")
    click.echo("  bd create --title=\"Setup database schema\" --type=task --priority=1")
    click.echo("  bd create --title=\"Implement API endpoints\" --type=task --priority=1")
    click.echo("  bd dep add <api-task-id> <schema-task-id>  # API depends on schema")
