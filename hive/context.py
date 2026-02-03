"""CLAUDE.md context generation for agent tasks."""

import subprocess
from pathlib import Path
from typing import Optional


def generate_claude_context(
    task_id: str,
    task_title: str,
    task_description: str,
    task_type: str = "task",
    acceptance_criteria: Optional[str] = None,
    plan_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> str:
    """Generate CLAUDE.md context for an agent working on a task.

    Args:
        task_id: The Beads task ID (e.g., "hive-abc")
        task_title: Short title of the task
        task_description: Detailed description of what needs to be done
        task_type: Type of task (task, bug, feature, etc.)
        acceptance_criteria: Criteria for task completion
        plan_path: Path to .hive/plan.md (optional, will be read if exists)
        output_path: Where to write CLAUDE.md (optional, will return string if None)

    Returns:
        The generated CLAUDE.md content as a string
    """
    # Read plan context if available
    plan_context = ""
    if plan_path and plan_path.exists():
        with open(plan_path) as f:
            plan_context = f.read()

    # Generate acceptance criteria if not provided
    if not acceptance_criteria:
        acceptance_criteria = f"Complete the implementation for: {task_title}"

    # Generate the CLAUDE.md content
    content = f"""# Task Context

This file provides context for working on a specific task in the Hive orchestrator.

## Task Information

- **Task ID**: {task_id}
- **Type**: {task_type}
- **Title**: {task_title}

## Description

{task_description}

## Acceptance Criteria

{acceptance_criteria}

## Worker Instructions

### When Task is Complete

When you have successfully completed this task:

1. Ensure all tests pass
2. Commit your changes with a clear message
3. Update the task status:
   ```bash
   bd close {task_id}
   ```
4. Push your changes

### If Task is Too Big

If you discover this task is too large for a single session:

1. Document what you've learned in the task notes:
   ```bash
   bd update {task_id} --notes="This needs to be broken down because..."
   ```
2. Update the task status:
   ```bash
   bd update {task_id} --status=too_big
   ```
3. Create subtasks for the remaining work
4. Notify the orchestrator that decomposition is needed

### If Task is Blocked

If you encounter a blocker (missing dependency, need human input, etc.):

1. Document the blocker:
   ```bash
   bd update {task_id} --notes="Blocked by: <reason>"
   ```
2. Update the task status:
   ```bash
   bd update {task_id} --status=blocked
   ```
3. Create a task for the blocker if appropriate

### If Task Fails

If you encounter an error you cannot resolve:

1. Document the failure:
   ```bash
   bd update {task_id} --notes="Failed: <reason>"
   ```
2. Update the task status:
   ```bash
   bd update {task_id} --status=failed
   ```
3. The failure will be reviewed by a human

## Project Context

"""

    # Add plan context if available
    if plan_context:
        content += plan_context
    else:
        content += "(No plan available - run `hive plan --show` for project context)\n"

    content += """

## Working in a Worktree

You are working in a git worktree, which is an isolated copy of the repository.

- Your changes are isolated from other workers
- You have your own branch for this task
- When done, your work will be merged back to the main branch

### Important Notes

- Stay focused on THIS task only
- Do not make unrelated changes
- Keep the scope small and testable
- When in doubt, mark the task as too_big rather than expanding scope

## Questions?

If you have questions or need clarification:

1. Check the task description and acceptance criteria above
2. Review the project context below
3. If still unclear, mark the task as blocked and request human input

---

**Good luck!** Remember: small, focused changes are better than large, risky ones.
"""

    # Write to file if output_path is provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)

    return content


def get_task_from_beads(task_id: str) -> dict:
    """Fetch task details from Beads.

    Args:
        task_id: The Beads task ID

    Returns:
        Dictionary with task details (title, description, type, etc.)

    Raises:
        RuntimeError: If bd command fails or task not found
    """
    try:
        result = subprocess.run(
            ["bd", "show", task_id, "--json"],
            capture_output=True,
            text=True,
            check=True,
        )

        import json
        task_data = json.loads(result.stdout)
        return task_data

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to fetch task {task_id} from Beads: {e.stderr}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Beads output: {e}")


def generate_claude_context_from_beads(
    task_id: str,
    output_path: Optional[Path] = None,
    plan_path: Optional[Path] = None,
) -> str:
    """Generate CLAUDE.md by fetching task details from Beads.

    Args:
        task_id: The Beads task ID
        output_path: Where to write CLAUDE.md (optional)
        plan_path: Path to .hive/plan.md (optional)

    Returns:
        The generated CLAUDE.md content as a string
    """
    # Fetch task from Beads
    task = get_task_from_beads(task_id)

    # Extract task details
    title = task.get("title", "No title")
    description = task.get("description", "No description provided")
    task_type = task.get("type", "task")

    # Generate and return context
    return generate_claude_context(
        task_id=task_id,
        task_title=title,
        task_description=description,
        task_type=task_type,
        plan_path=plan_path,
        output_path=output_path,
    )
