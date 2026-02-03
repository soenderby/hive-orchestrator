"""Merge command for manual conflict resolution."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import click

from hive.worktree import WorktreeManager


def run_command(cmd: list[str], check: bool = True, capture: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
            cwd=cwd,
        )
        return result
    except subprocess.CalledProcessError as e:
        if not check:
            return e
        raise


def find_worktree_by_identifier(identifier: str, manager: WorktreeManager) -> Optional[tuple[Path, str, str]]:
    """Find a worktree by worker ID, task ID, or worktree path.

    Returns: (worktree_path, branch_name, task_id) or None
    """
    # Check if identifier is a full worktree path
    worktree_path = Path(identifier)
    if worktree_path.exists() and worktree_path.is_dir():
        # Extract task ID from path (format: worker-X-task-ID)
        parts = worktree_path.name.split('-', 2)
        if len(parts) >= 3 and parts[2].startswith('hive-'):
            task_id = parts[2]
            branch_name = f"task-{task_id}"
            return (worktree_path, branch_name, task_id)

    # Check if it's a task ID (hive-xxx)
    if identifier.startswith('hive-'):
        # Find any worktree matching this task ID
        worktrees = manager.list_worktrees()
        for wt in worktrees:
            wt_path = Path(wt['path'])
            if wt_path.name.endswith(identifier):
                branch_name = f"task-{identifier}"
                return (wt_path, branch_name, identifier)

    # Check if it's a worker-task combo (worker-1-hive-abc)
    if '-' in identifier:
        potential_path = manager.worktrees_dir / identifier
        if potential_path.exists():
            parts = identifier.split('-', 2)
            if len(parts) >= 3:
                task_id = parts[2]
                branch_name = f"task-{task_id}"
                return (potential_path, branch_name, task_id)

    return None


def check_merge_status(worktree_path: Path) -> dict:
    """Check the status of a worktree and whether it has conflicts.

    Returns:
        dict with keys:
        - has_conflicts: bool
        - conflicted_files: list[str]
        - uncommitted_changes: bool
        - current_branch: str
    """
    result = run_command(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        check=False,
    )

    lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
    conflicted_files = []
    uncommitted_changes = False

    for line in lines:
        if line.startswith('UU ') or line.startswith('AA ') or line.startswith('DD '):
            # Unmerged files
            conflicted_files.append(line[3:])
        elif line.strip():
            uncommitted_changes = True

    # Get current branch
    branch_result = run_command(
        ["git", "branch", "--show-current"],
        cwd=worktree_path,
        check=False,
    )
    current_branch = branch_result.stdout.strip()

    return {
        'has_conflicts': len(conflicted_files) > 0,
        'conflicted_files': conflicted_files,
        'uncommitted_changes': uncommitted_changes or len(conflicted_files) > 0,
        'current_branch': current_branch,
    }


@click.command(name="merge")
@click.argument("identifier", required=True)
@click.option("--cleanup-only", is_flag=True, help="Skip merge, just cleanup worktree (use after manual merge)")
@click.option("--force", is_flag=True, help="Force cleanup even with uncommitted changes")
def merge_cmd(identifier: str, cleanup_only: bool, force: bool):
    """Assist with manual merge resolution for conflicted tasks.

    IDENTIFIER can be:
    - Task ID (e.g., hive-abc)
    - Worker-task combo (e.g., worker-1-hive-abc)
    - Full worktree path (e.g., worktrees/worker-1-hive-abc)

    \b
    Workflow:
    1. Shows conflict status and files
    2. Guides you through resolution
    3. After resolution, merges to main
    4. Cleans up worktree and branch
    5. Closes task in Beads

    \b
    Examples:
      hive merge hive-abc          # Resolve conflicts for task hive-abc
      hive merge worker-1-hive-abc # Resolve conflicts for specific worktree
      hive merge hive-abc --cleanup-only  # Just cleanup after manual merge
    """
    repo_root = Path.cwd()
    manager = WorktreeManager(repo_root=repo_root)

    # Find the worktree
    result = find_worktree_by_identifier(identifier, manager)
    if not result:
        click.echo(f"✗ Could not find worktree for: {identifier}")
        click.echo("\nAvailable worktrees:")
        worktrees = manager.list_worktrees()
        for wt in worktrees:
            wt_path = Path(wt['path'])
            if wt_path != repo_root:
                click.echo(f"  - {wt_path}")
        sys.exit(1)

    worktree_path, branch_name, task_id = result

    click.echo(f"Found worktree: {worktree_path}")
    click.echo(f"Branch: {branch_name}")
    click.echo(f"Task: {task_id}")
    click.echo()

    # Check status
    status = check_merge_status(worktree_path)

    if cleanup_only:
        # Just cleanup, skip merge
        click.echo("Cleanup mode: skipping merge, cleaning up worktree...")

        if status['uncommitted_changes'] and not force:
            click.echo("✗ Worktree has uncommitted changes. Use --force to cleanup anyway.")
            click.echo("\nUncommitted changes in worktree. Please:")
            click.echo(f"  cd {worktree_path}")
            click.echo("  git status")
            click.echo("  # Commit or discard changes")
            sys.exit(1)

        # Cleanup worktree
        click.echo(f"Removing worktree: {worktree_path}")
        try:
            run_command(
                ["git", "worktree", "remove", str(worktree_path)] + (["--force"] if force else []),
                cwd=repo_root,
            )
        except subprocess.CalledProcessError as e:
            click.echo(f"✗ Failed to remove worktree: {e.stderr}")
            sys.exit(1)

        # Delete branch
        click.echo(f"Deleting branch: {branch_name}")
        run_command(
            ["git", "branch", "-D", branch_name],
            cwd=repo_root,
            check=False,
        )

        click.echo("✓ Cleanup complete")
        click.echo(f"\nDon't forget to close the task:")
        click.echo(f"  bd close {task_id}")
        return

    # Check for conflicts
    if status['has_conflicts']:
        click.echo("⚠ Merge conflicts detected:")
        for file in status['conflicted_files']:
            click.echo(f"  - {file}")
        click.echo()
        click.echo("Please resolve conflicts manually:")
        click.echo(f"  cd {worktree_path}")
        click.echo("  # Edit conflicted files")
        click.echo("  git add <resolved-files>")
        click.echo("  git commit")
        click.echo()
        click.echo("Then run this command again:")
        click.echo(f"  hive merge {task_id}")
        sys.exit(0)

    # Check if there are uncommitted changes
    if status['uncommitted_changes']:
        click.echo("⚠ Worktree has uncommitted changes.")
        click.echo("\nPlease commit or discard changes first:")
        click.echo(f"  cd {worktree_path}")
        click.echo("  git status")
        click.echo("  git add <files>")
        click.echo("  git commit -m 'Resolve conflicts'")
        click.echo()
        click.echo("Then run this command again:")
        click.echo(f"  hive merge {task_id}")
        sys.exit(0)

    # All clean, ready to merge
    click.echo("✓ No conflicts detected, ready to merge")
    click.echo()

    # Checkout main
    click.echo("Switching to main branch...")
    try:
        run_command(["git", "checkout", "main"], cwd=repo_root)
    except subprocess.CalledProcessError as e:
        click.echo(f"✗ Failed to checkout main: {e.stderr}")
        sys.exit(1)

    # Pull latest main
    click.echo("Pulling latest main...")
    run_command(["git", "pull"], cwd=repo_root, check=False)

    # Merge the task branch
    click.echo(f"Merging {branch_name} into main...")
    try:
        merge_result = run_command(
            ["git", "merge", branch_name, "--no-edit"],
            cwd=repo_root,
            check=False,
        )

        if merge_result.returncode != 0:
            click.echo("✗ Merge failed. Conflicts detected.")
            click.echo("\nResolve conflicts in the main repository:")
            click.echo("  git status")
            click.echo("  # Edit conflicted files")
            click.echo("  git add <resolved-files>")
            click.echo("  git commit")
            click.echo()
            click.echo("Then cleanup the worktree:")
            click.echo(f"  hive merge {task_id} --cleanup-only")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        click.echo(f"✗ Merge failed: {e.stderr}")
        click.echo("\nAbort the merge:")
        click.echo("  git merge --abort")
        sys.exit(1)

    click.echo("✓ Merge successful")

    # Delete the branch
    click.echo(f"Deleting branch: {branch_name}")
    run_command(
        ["git", "branch", "-d", branch_name],
        cwd=repo_root,
        check=False,
    )

    # Remove worktree
    click.echo(f"Removing worktree: {worktree_path}")
    try:
        run_command(
            ["git", "worktree", "remove", str(worktree_path), "--force"],
            cwd=repo_root,
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"⚠ Warning: Failed to remove worktree: {e.stderr}")
        click.echo("You may need to remove it manually:")
        click.echo(f"  git worktree remove --force {worktree_path}")

    click.echo("✓ Cleanup complete")
    click.echo()
    click.echo("Close the task in Beads:")
    click.echo(f"  bd close {task_id}")


@click.command(name="sync")
@click.option("--push", is_flag=True, help="Push all branches to remote")
@click.option("--pull", is_flag=True, help="Pull all branches from remote")
@click.option("--dry-run", is_flag=True, help="Show what would be done without doing it")
def sync_cmd(push: bool, pull: bool, dry_run: bool):
    """Synchronize all worker branches with remote.

    By default, both pushes and pulls all task branches.
    Use --push or --pull to do only one operation.

    \b
    Examples:
      hive sync              # Push and pull all branches
      hive sync --push       # Push only
      hive sync --pull       # Pull only
      hive sync --dry-run    # Show what would happen
    """
    repo_root = Path.cwd()
    manager = WorktreeManager(repo_root=repo_root)

    # If neither push nor pull specified, do both
    if not push and not pull:
        push = pull = True

    # Get all worktrees
    worktrees = manager.list_worktrees()
    task_branches = []

    for wt in worktrees:
        wt_path = Path(wt['path'])
        # Skip main worktree
        if wt_path == repo_root:
            continue

        branch = wt.get('branch', '')
        if branch and branch.startswith('refs/heads/'):
            branch_name = branch.replace('refs/heads/', '')
            # Only include task branches (task-*)
            if branch_name.startswith('task-'):
                task_branches.append(branch_name)

    if not task_branches:
        click.echo("No task branches found")
        return

    click.echo(f"Found {len(task_branches)} task branch(es):")
    for branch in task_branches:
        click.echo(f"  - {branch}")
    click.echo()

    if dry_run:
        click.echo("Dry run mode - showing what would be done:")
        if push:
            for branch in task_branches:
                click.echo(f"  Would push: {branch}")
        if pull:
            for branch in task_branches:
                click.echo(f"  Would pull: {branch}")
        return

    # Push branches
    if push:
        click.echo("Pushing branches to remote...")
        for branch in task_branches:
            click.echo(f"  Pushing {branch}...")
            result = run_command(
                ["git", "push", "origin", branch],
                cwd=repo_root,
                check=False,
            )
            if result.returncode == 0:
                click.echo(f"    ✓ Pushed {branch}")
            else:
                click.echo(f"    ✗ Failed to push {branch}: {result.stderr}")
        click.echo()

    # Pull branches
    if pull:
        click.echo("Pulling branches from remote...")
        for branch in task_branches:
            click.echo(f"  Pulling {branch}...")

            # Fetch first
            run_command(
                ["git", "fetch", "origin", branch],
                cwd=repo_root,
                check=False,
            )

            # Try to merge
            result = run_command(
                ["git", "merge", f"origin/{branch}", "--ff-only"],
                cwd=repo_root,
                check=False,
            )

            if result.returncode == 0:
                click.echo(f"    ✓ Pulled {branch}")
            else:
                click.echo(f"    ⚠ Could not fast-forward {branch} (may need manual merge)")
        click.echo()

    click.echo("✓ Sync complete")
