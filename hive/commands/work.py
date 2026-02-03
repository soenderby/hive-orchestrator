"""Work command for Hive orchestrator.

Implements the Ralph loop: claim task, create worktree, spawn agent, poll for completion.
"""

import json
import multiprocessing
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from hive.context import generate_claude_context_from_beads
from hive.worktree import WorktreeManager


def run_command(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        if not check:
            return e
        raise


def log(worker_id: str, message: str):
    """Log a message with timestamp and worker ID."""
    timestamp = time.strftime("%H:%M:%S")
    click.echo(f"[{timestamp}] [{worker_id}] {message}")


def get_next_task() -> Optional[dict]:
    """Get the next ready task from Beads.

    Only returns tasks where all dependencies are closed (done AND merged).
    """
    result = run_command(["bd", "list", "--ready", "--json"], check=False)
    if result.returncode != 0:
        return None

    try:
        tasks = json.loads(result.stdout)
        if not tasks:
            return None

        # Filter tasks to only those with all dependencies closed
        for task in tasks:
            # If no dependencies, task is ready
            if task.get("dependency_count", 0) == 0:
                return task

            # Has dependencies - need to check if all are closed
            task_id = task.get("id")
            if not task_id:
                continue

            # Get full task details with dependency status
            show_result = run_command(["bd", "show", task_id, "--json"], check=False)
            if show_result.returncode != 0:
                continue

            try:
                task_details = json.loads(show_result.stdout)
                if not task_details or len(task_details) == 0:
                    continue

                task_detail = task_details[0]
                dependencies = task_detail.get("dependencies", [])

                # Check if all dependencies are closed
                all_closed = all(dep.get("status") == "closed" for dep in dependencies)
                if all_closed:
                    return task
            except (json.JSONDecodeError, KeyError):
                continue

    except (json.JSONDecodeError, KeyError):
        pass

    return None


def claim_task(task_id: str, worker_id: str) -> bool:
    """Atomically claim a task using compare-and-swap semantics.

    Uses bd update --claim which:
    - Atomically sets assignee and status=in_progress
    - Fails if task is already claimed or not in planned state
    - Provides true compare-and-swap guarantees for parallel safety
    """
    result = run_command(
        ["bd", "update", task_id, "--claim"],
        check=False,
    )
    return result.returncode == 0


def get_task_status(task_id: str) -> str:
    """Get the current status of a task."""
    result = run_command(["bd", "show", task_id, "--json"], check=False)
    if result.returncode != 0:
        return "unknown"

    try:
        task = json.loads(result.stdout)
        return task.get("status", "unknown")
    except (json.JSONDecodeError, KeyError):
        return "unknown"


def kill_tmux_session(session_name: str):
    """Kill a tmux session if it exists."""
    run_command(["tmux", "kill-session", "-t", session_name], check=False)


def tmux_session_exists(session_name: str) -> bool:
    """Check if a tmux session exists."""
    result = run_command(["tmux", "has-session", "-t", session_name], check=False)
    return result.returncode == 0


def check_tmux_activity(session_name: str) -> bool:
    """Check if there's any activity in the tmux session."""
    result = run_command(
        ["tmux", "capture-pane", "-t", session_name, "-p"],
        check=False,
    )
    if result.returncode != 0:
        return False

    # Check if there's more than just the initial prompt
    lines = result.stdout.strip().split("\n")
    return len(lines) > 2


def merge_branch(branch: str) -> bool:
    """Merge a branch to main. Returns True if successful, False on conflict."""
    # First checkout main
    result = run_command(["git", "checkout", "main"], check=False)
    if result.returncode != 0:
        return False

    # Try to merge
    result = run_command(["git", "merge", branch, "--no-edit"], check=False)
    if result.returncode != 0:
        # Abort the merge
        run_command(["git", "merge", "--abort"], check=False)
        return False

    return True


def register_worker(worker_id: str, pid: int, task_id: str, tmux_session: str, worktree: str):
    """Register a worker in the worker registry."""
    workers_path = Path(".hive/workers.json")

    # Read current registry
    try:
        with open(workers_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"workers": [], "last_updated": None}

    # Add or update worker
    workers = data.get("workers", [])
    worker_entry = {
        "id": worker_id,
        "pid": pid,
        "tmux_session": tmux_session,
        "worktree": worktree,
        "current_task": task_id,
        "started_at": datetime.now().isoformat(),
        "last_activity": datetime.now().isoformat(),
    }

    # Remove existing entry for this worker if present
    workers = [w for w in workers if w.get("id") != worker_id]
    workers.append(worker_entry)

    data["workers"] = workers
    data["last_updated"] = datetime.now().isoformat()

    # Write back
    with open(workers_path, "w") as f:
        json.dump(data, f, indent=2)


def unregister_worker(worker_id: str):
    """Unregister a worker from the worker registry."""
    workers_path = Path(".hive/workers.json")

    try:
        with open(workers_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    # Remove worker
    workers = data.get("workers", [])
    workers = [w for w in workers if w.get("id") != worker_id]

    data["workers"] = workers
    data["last_updated"] = datetime.now().isoformat()

    # Write back
    with open(workers_path, "w") as f:
        json.dump(data, f, indent=2)


def update_worker_activity(worker_id: str):
    """Update the last activity timestamp for a worker."""
    workers_path = Path(".hive/workers.json")

    try:
        with open(workers_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    # Update worker activity
    workers = data.get("workers", [])
    for worker in workers:
        if worker.get("id") == worker_id:
            worker["last_activity"] = datetime.now().isoformat()
            break

    data["last_updated"] = datetime.now().isoformat()

    # Write back
    with open(workers_path, "w") as f:
        json.dump(data, f, indent=2)


def ralph_loop_iteration(
    worker_id: str,
    manager: WorktreeManager,
    poll_interval: int = 5,
    task_timeout: int = 3600,
    spawn_grace: int = 30,
    agent_command: str = "claude-code",
) -> bool:
    """Run one iteration of the Ralph loop. Returns True if should continue, False if no work."""

    # -------------------------------------------------
    # 1. GET NEXT TASK
    # -------------------------------------------------

    task = get_next_task()
    if not task:
        log(worker_id, "No tasks remaining. Exiting.")
        return False

    task_id = task.get("id", "")
    task_title = task.get("title", "")

    log(worker_id, f"Picked task: {task_id} - {task_title}")

    # -------------------------------------------------
    # 2. ATOMIC CLAIM
    # -------------------------------------------------

    if not claim_task(task_id, worker_id):
        log(worker_id, "Failed to claim task (race condition or invalid state). Retrying...")
        time.sleep(1)
        return True  # Continue loop

    # -------------------------------------------------
    # 3. CREATE UNIQUE WORKTREE
    # -------------------------------------------------

    branch = f"task-{task_id}"
    tmux_session = f"hive-{worker_id}-{task_id}"

    log(worker_id, f"Creating worktree on branch: {branch}")

    try:
        # Remove stale worktree if exists (from prior crash)
        if manager.worktree_exists(worker_id, task_id):
            manager.remove_worktree(worker_id, task_id, force=True)

        worktree_path = manager.create_worktree(worker_id, task_id, base_branch="main")
    except Exception as e:
        log(worker_id, f"ERROR: Failed to create worktree: {e}")
        run_command(
            ["bd", "update", task_id, "--status", "failed", "--notes", f"Worktree creation failed: {e}"],
            check=False,
        )
        return True  # Continue loop

    # -------------------------------------------------
    # 4. GENERATE CONTEXT
    # -------------------------------------------------

    log(worker_id, "Generating CLAUDE.md")

    try:
        plan_path = Path(".hive/plan.md")
        context = generate_claude_context_from_beads(
            task_id,
            output_path=worktree_path / "CLAUDE.md",
            plan_path=plan_path if plan_path.exists() else None,
        )
    except Exception as e:
        log(worker_id, f"ERROR: Failed to generate context: {e}")
        run_command(
            ["bd", "update", task_id, "--status", "failed", "--notes", f"Context generation failed: {e}"],
            check=False,
        )
        manager.remove_worktree(worker_id, task_id, force=True)
        return True  # Continue loop

    # -------------------------------------------------
    # 5. SPAWN AGENT
    # -------------------------------------------------

    log(worker_id, f"Spawning agent in tmux session: {tmux_session}")

    # Clean up any stale session
    kill_tmux_session(tmux_session)

    # Create new tmux session with agent
    run_command(
        ["tmux", "new-session", "-d", "-s", tmux_session, "-c", str(worktree_path)],
        check=False,
    )

    run_command(
        ["tmux", "send-keys", "-t", tmux_session, agent_command, "Enter"],
        check=False,
    )

    # Register worker in registry
    register_worker(
        worker_id=worker_id,
        pid=os.getpid(),
        task_id=task_id,
        tmux_session=tmux_session,
        worktree=str(worktree_path),
    )

    # -------------------------------------------------
    # 6. SPAWN GRACE PERIOD CHECK
    # -------------------------------------------------

    log(worker_id, f"Checking agent spawn (grace period: {spawn_grace}s)...")

    time.sleep(spawn_grace)

    # Check for any sign of life
    current_status = get_task_status(task_id)
    has_activity = False

    if current_status != "in_progress":
        has_activity = True  # Status changed = agent is working
    elif check_tmux_activity(tmux_session):
        has_activity = True  # Tmux has output = agent is working
    elif not tmux_session_exists(tmux_session):
        has_activity = False  # Session died = spawn failed
    else:
        has_activity = True  # Session exists, assume it's working

    if not has_activity:
        log(worker_id, f"SPAWN FAILED: No activity detected within grace period")
        run_command(
            ["bd", "update", task_id, "--status", "failed", "--notes", f"agent_spawn_failed: no activity within {spawn_grace}s"],
            check=False,
        )
        kill_tmux_session(tmux_session)
        manager.remove_worktree(worker_id, task_id, force=True)
        return True  # Continue loop

    # -------------------------------------------------
    # 7. WAIT FOR COMPLETION (poll Beads)
    # -------------------------------------------------

    log(worker_id, f"Waiting for task completion (timeout: {task_timeout}s)...")

    start_time = time.time()
    outcome = None

    while True:
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed >= task_timeout:
            log(worker_id, f"TIMEOUT: Task exceeded {task_timeout}s")
            run_command(
                ["bd", "update", task_id, "--status", "failed", "--notes", f"Timeout after {task_timeout}s"],
                check=False,
            )
            outcome = "timeout"
            break

        # Check if tmux session died unexpectedly
        if not tmux_session_exists(tmux_session):
            log(worker_id, "Session died unexpectedly")
            current_status = get_task_status(task_id)
            if current_status == "in_progress":
                run_command(
                    ["bd", "update", task_id, "--status", "failed", "--notes", "Session crashed"],
                    check=False,
                )
                outcome = "crashed"
            else:
                outcome = current_status
            break

        # Update worker activity
        update_worker_activity(worker_id)

        # Check Beads for status change
        current_status = get_task_status(task_id)

        if current_status == "done":
            log(worker_id, "Task completed successfully")
            outcome = "done"
            break
        elif current_status == "too_big":
            log(worker_id, "Task marked as too big")
            outcome = "too_big"
            break
        elif current_status == "blocked":
            log(worker_id, "Task is blocked")
            outcome = "blocked"
            break
        elif current_status == "failed":
            log(worker_id, "Task failed")
            outcome = "failed"
            break

        time.sleep(poll_interval)

    # -------------------------------------------------
    # 8. CLEANUP AGENT
    # -------------------------------------------------

    kill_tmux_session(tmux_session)

    # -------------------------------------------------
    # 9. HANDLE OUTCOME (including merge)
    # -------------------------------------------------

    if outcome == "done":
        log(worker_id, f"Merging branch {branch} to main")

        if merge_branch(branch):
            log(worker_id, "Merge successful")
            manager.remove_worktree(worker_id, task_id, force=True)
        else:
            log(worker_id, "MERGE CONFLICT - requires human resolution")
            run_command(
                ["bd", "update", task_id, "--status", "blocked", "--notes", f"Merge conflict, needs human resolution. Worktree: {worktree_path}"],
                check=False,
            )
            # Keep worktree for human to resolve

    elif outcome == "too_big":
        log(worker_id, "Task needs decomposition by human")
        manager.remove_worktree(worker_id, task_id, force=True)

    elif outcome == "blocked":
        log(worker_id, "Task blocked, preserving worktree for inspection")
        # Keep worktree, human may want to inspect

    elif outcome in ["failed", "timeout", "crashed"]:
        log(worker_id, f"Task failed: {outcome}")
        manager.remove_worktree(worker_id, task_id, force=True)

    else:
        log(worker_id, f"Unexpected outcome: {outcome}")
        manager.remove_worktree(worker_id, task_id, force=True)

    # Unregister worker after task completion
    unregister_worker(worker_id)

    log(worker_id, "--- Iteration complete ---")
    click.echo("")

    return True  # Continue loop


def run_worker(
    worker_num: int,
    poll_interval: int,
    task_timeout: int,
    spawn_grace: int,
    agent_command: str,
):
    """Run a single worker in a separate process."""
    worker_id = f"worker-{worker_num}"
    repo_root = Path.cwd()
    manager = WorktreeManager(repo_root=repo_root)

    log(worker_id, "Starting ralph loop")

    while True:
        should_continue = ralph_loop_iteration(
            worker_id=worker_id,
            manager=manager,
            poll_interval=poll_interval,
            task_timeout=task_timeout,
            spawn_grace=spawn_grace,
            agent_command=agent_command,
        )

        if not should_continue:
            break

    log(worker_id, "Ralph loop completed")


@click.command(name="work")
@click.option("--worker-id", default=None, help="Worker ID (default: worker-<pid>)")
@click.option("--poll-interval", default=5, help="Poll interval in seconds (default: 5)")
@click.option("--task-timeout", default=3600, help="Task timeout in seconds (default: 3600)")
@click.option("--spawn-grace", default=30, help="Spawn grace period in seconds (default: 30)")
@click.option("--agent-command", default="claude-code", help="Agent command to run (default: claude-code)")
@click.option("--parallel", default=1, type=int, help="Number of parallel workers (default: 1)")
@click.option("--task", default=None, help="Run specific task only (not implemented yet)")
@click.option("--dry-run", is_flag=True, help="Show what would execute (not implemented yet)")
def work_cmd(worker_id, poll_interval, task_timeout, spawn_grace, agent_command, parallel, task, dry_run):
    """Execute tasks using Ralph loop orchestration.

    The Ralph loop runs continuously, claiming tasks from Beads one at a time,
    spawning an agent in a fresh worktree, and polling for completion.

    With --parallel N, spawns N independent workers that coordinate via atomic claims.
    """
    # Check prerequisites
    repo_root = Path.cwd()
    beads_dir = repo_root / ".beads"
    hive_dir = repo_root / ".hive"

    if not beads_dir.exists():
        click.echo("✗ Beads not initialized (.beads/ not found)")
        click.echo("  Run 'bd init' first")
        sys.exit(1)

    if not hive_dir.exists():
        click.echo("✗ Hive not initialized (.hive/ not found)")
        click.echo("  Run 'hive init' first")
        sys.exit(1)

    # Validate parallel count
    if parallel < 1:
        click.echo("✗ --parallel must be >= 1")
        sys.exit(1)

    # If parallel execution requested, spawn worker processes
    if parallel > 1:
        click.echo(f"Starting {parallel} parallel workers...")

        processes = []
        for i in range(1, parallel + 1):
            p = multiprocessing.Process(
                target=run_worker,
                args=(i, poll_interval, task_timeout, spawn_grace, agent_command),
            )
            p.start()
            processes.append(p)
            click.echo(f"[main] Started worker-{i} (PID: {p.pid})")

        # Wait for all workers to complete
        for p in processes:
            p.join()

        click.echo("[main] All workers completed")
    else:
        # Serial execution (single worker)
        if not worker_id:
            worker_id = f"worker-{os.getpid()}"

        # Initialize worktree manager
        manager = WorktreeManager(repo_root=repo_root)

        # Start the Ralph loop
        log(worker_id, "Starting ralph loop")

        while True:
            should_continue = ralph_loop_iteration(
                worker_id=worker_id,
                manager=manager,
                poll_interval=poll_interval,
                task_timeout=task_timeout,
                spawn_grace=spawn_grace,
                agent_command=agent_command,
            )

            if not should_continue:
                break

        log(worker_id, "Ralph loop completed")
