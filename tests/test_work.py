"""Tests for hive work command."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from hive.cli import main
from hive.commands.work import (
    check_tmux_activity,
    claim_task,
    get_next_task,
    get_task_status,
    kill_tmux_session,
    log,
    merge_branch,
    ralph_loop_iteration,
    work_cmd,
    tmux_session_exists,
)


def test_log_formats_correctly(capsys):
    """Test that log function formats messages correctly."""
    log("worker-1", "Test message")
    captured = capsys.readouterr()
    assert "[worker-1]" in captured.out
    assert "Test message" in captured.out


@patch("hive.commands.work.run_command")
def test_get_next_task_success(mock_run):
    """Test getting next task from Beads with no dependencies."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([{"id": "hive-123", "title": "Test task", "dependency_count": 0}]),
    )

    task = get_next_task()
    assert task is not None
    assert task["id"] == "hive-123"
    assert task["title"] == "Test task"
    mock_run.assert_called_once_with(["bd", "list", "--ready", "--json"], check=False)


@patch("hive.commands.work.run_command")
def test_get_next_task_no_tasks(mock_run):
    """Test getting next task when queue is empty."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([]),
    )

    task = get_next_task()
    assert task is None


@patch("hive.commands.work.run_command")
def test_get_next_task_error(mock_run):
    """Test getting next task when bd command fails."""
    mock_run.return_value = MagicMock(returncode=1)

    task = get_next_task()
    assert task is None


@patch("hive.commands.work.run_command")
def test_get_next_task_with_closed_dependencies(mock_run):
    """Test getting task where all dependencies are closed."""
    # First call: bd list --ready returns task with dependencies
    # Second call: bd show returns full task with closed dependencies
    mock_run.side_effect = [
        MagicMock(
            returncode=0,
            stdout=json.dumps([{"id": "hive-123", "title": "Test task", "dependency_count": 1}]),
        ),
        MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "hive-123",
                        "title": "Test task",
                        "dependencies": [{"id": "hive-111", "status": "closed"}],
                    }
                ]
            ),
        ),
    ]

    task = get_next_task()
    assert task is not None
    assert task["id"] == "hive-123"
    assert mock_run.call_count == 2
    mock_run.assert_any_call(["bd", "list", "--ready", "--json"], check=False)
    mock_run.assert_any_call(["bd", "show", "hive-123", "--json"], check=False)


@patch("hive.commands.work.run_command")
def test_get_next_task_with_open_dependencies(mock_run):
    """Test that tasks with open dependencies are skipped."""
    # First call: bd list --ready returns two tasks
    # Second call: bd show for first task shows open dependency
    # Third call: bd show for second task shows no dependencies
    mock_run.side_effect = [
        MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {"id": "hive-123", "title": "Blocked task", "dependency_count": 1},
                    {"id": "hive-456", "title": "Ready task", "dependency_count": 0},
                ]
            ),
        ),
        MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "hive-123",
                        "title": "Blocked task",
                        "dependencies": [{"id": "hive-111", "status": "open"}],
                    }
                ]
            ),
        ),
    ]

    task = get_next_task()
    assert task is not None
    assert task["id"] == "hive-456"  # Should return second task, not blocked one
    assert task["title"] == "Ready task"


@patch("hive.commands.work.run_command")
def test_get_next_task_with_in_progress_dependencies(mock_run):
    """Test that tasks with in_progress dependencies are skipped."""
    mock_run.side_effect = [
        MagicMock(
            returncode=0,
            stdout=json.dumps([{"id": "hive-123", "title": "Test task", "dependency_count": 1}]),
        ),
        MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "hive-123",
                        "title": "Test task",
                        "dependencies": [{"id": "hive-111", "status": "in_progress"}],
                    }
                ]
            ),
        ),
    ]

    task = get_next_task()
    assert task is None  # Should return None as only task has in_progress dependency


@patch("hive.commands.work.run_command")
def test_claim_task_success(mock_run):
    """Test successfully claiming a task using atomic --claim flag."""
    mock_run.return_value = MagicMock(returncode=0)

    result = claim_task("hive-123", "worker-1")
    assert result is True
    mock_run.assert_called_once_with(
        ["bd", "update", "hive-123", "--claim"],
        check=False,
    )


@patch("hive.commands.work.run_command")
def test_claim_task_failure(mock_run):
    """Test claiming a task when it fails (already claimed or not planned)."""
    mock_run.return_value = MagicMock(returncode=1)

    result = claim_task("hive-123", "worker-1")
    assert result is False


@patch("hive.commands.work.run_command")
def test_get_task_status(mock_run):
    """Test getting task status."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "hive-123", "status": "done"}),
    )

    status = get_task_status("hive-123")
    assert status == "done"


@patch("hive.commands.work.run_command")
def test_get_task_status_error(mock_run):
    """Test getting task status when bd command fails."""
    mock_run.return_value = MagicMock(returncode=1)

    status = get_task_status("hive-123")
    assert status == "unknown"


@patch("hive.commands.work.run_command")
def test_kill_tmux_session(mock_run):
    """Test killing a tmux session."""
    kill_tmux_session("test-session")
    mock_run.assert_called_once_with(
        ["tmux", "kill-session", "-t", "test-session"],
        check=False,
    )


@patch("hive.commands.work.run_command")
def test_tmux_session_exists(mock_run):
    """Test checking if tmux session exists."""
    mock_run.return_value = MagicMock(returncode=0)

    result = tmux_session_exists("test-session")
    assert result is True


@patch("hive.commands.work.run_command")
def test_tmux_session_not_exists(mock_run):
    """Test checking if tmux session doesn't exist."""
    mock_run.return_value = MagicMock(returncode=1)

    result = tmux_session_exists("test-session")
    assert result is False


@patch("hive.commands.work.run_command")
def test_check_tmux_activity_with_output(mock_run):
    """Test checking tmux activity when there is output."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="line1\nline2\nline3\nline4\n",
    )

    result = check_tmux_activity("test-session")
    assert result is True


@patch("hive.commands.work.run_command")
def test_check_tmux_activity_no_output(mock_run):
    """Test checking tmux activity when there is minimal output."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="line1\nline2\n",
    )

    result = check_tmux_activity("test-session")
    assert result is False


@patch("hive.commands.work.run_command")
def test_merge_branch_success(mock_run):
    """Test successfully merging a branch."""
    mock_run.return_value = MagicMock(returncode=0)

    result = merge_branch("task-hive-123")
    assert result is True

    # Should call checkout main then merge
    assert mock_run.call_count == 2
    mock_run.assert_any_call(["git", "checkout", "main"], check=False)
    mock_run.assert_any_call(["git", "merge", "task-hive-123", "--no-edit"], check=False)


@patch("hive.commands.work.run_command")
def test_merge_branch_conflict(mock_run):
    """Test merging a branch with conflict."""
    # First call (checkout) succeeds, second (merge) fails
    mock_run.side_effect = [
        MagicMock(returncode=0),  # checkout
        MagicMock(returncode=1),  # merge fails
        MagicMock(returncode=0),  # merge --abort
    ]

    result = merge_branch("task-hive-123")
    assert result is False

    # Should call checkout, merge, then abort
    assert mock_run.call_count == 3
    mock_run.assert_any_call(["git", "merge", "--abort"], check=False)


def test_work_cmd_requires_beads(tmp_path):
    """Test that work command requires Beads to be initialized."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["work"])

        assert result.exit_code == 1
        assert "Beads not initialized" in result.output


def test_work_cmd_requires_hive(tmp_path):
    """Test that work command requires Hive to be initialized."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create .beads but not .hive
        beads_dir = Path(".beads")
        beads_dir.mkdir()

        result = runner.invoke(main, ["work"])

        assert result.exit_code == 1
        assert "Hive not initialized" in result.output


@patch("hive.commands.work.ralph_loop_iteration")
def test_work_cmd_runs_loop(mock_iteration, tmp_path):
    """Test that work command runs the Ralph loop."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create prerequisites
        beads_dir = Path(".beads")
        beads_dir.mkdir()
        hive_dir = Path(".hive")
        hive_dir.mkdir()

        # Make iteration return False immediately (no work)
        mock_iteration.return_value = False

        result = runner.invoke(main, ["work"])

        # Should exit cleanly
        assert result.exit_code == 0
        assert "Starting ralph loop" in result.output
        assert mock_iteration.called


@patch("hive.commands.work.get_next_task")
@patch("hive.commands.work.WorktreeManager")
def test_ralph_loop_no_tasks(mock_manager, mock_get_task, tmp_path):
    """Test Ralph loop exits when no tasks available."""
    mock_get_task.return_value = None

    result = ralph_loop_iteration("worker-1", mock_manager)

    assert result is False


@patch("hive.commands.work.get_next_task")
@patch("hive.commands.work.claim_task")
@patch("hive.commands.work.time.sleep")
@patch("hive.commands.work.WorktreeManager")
def test_ralph_loop_claim_race_condition(mock_manager, mock_sleep, mock_claim, mock_get_task):
    """Test Ralph loop handles race condition on claim."""
    mock_get_task.return_value = {"id": "hive-123", "title": "Test"}
    mock_claim.return_value = False  # Claim failed

    result = ralph_loop_iteration("worker-1", mock_manager)

    assert result is True  # Should continue looping
    mock_sleep.assert_called_once_with(1)


@patch("hive.commands.work.get_next_task")
@patch("hive.commands.work.claim_task")
@patch("hive.commands.work.get_task_status")
@patch("hive.commands.work.check_tmux_activity")
@patch("hive.commands.work.tmux_session_exists")
@patch("hive.commands.work.kill_tmux_session")
@patch("hive.commands.work.run_command")
@patch("hive.commands.work.time.sleep")
@patch("hive.commands.work.generate_claude_context_from_beads")
@patch("hive.commands.work.WorktreeManager")
def test_ralph_loop_spawn_failure_detection(
    mock_manager,
    mock_context,
    mock_sleep,
    mock_run,
    mock_kill,
    mock_exists,
    mock_activity,
    mock_status,
    mock_claim,
    mock_get_task,
    tmp_path,
):
    """Test that spawn failure detection marks task as failed when no activity detected."""
    # Setup task
    mock_get_task.return_value = {"id": "hive-123", "title": "Test task"}
    mock_claim.return_value = True

    # Setup worktree manager
    mock_manager.worktree_exists.return_value = False
    mock_manager.create_worktree.return_value = tmp_path / "worktree"

    # Setup context generation
    mock_context.return_value = "context"

    # Setup run_command to return success for tmux commands
    def mock_run_side_effect(cmd, check=True, capture=True):
        result = MagicMock()
        if "tmux" in cmd:
            result.returncode = 0  # tmux commands succeed
            result.stdout = ""
            result.stderr = ""
        else:
            result.returncode = 0  # bd commands also succeed
            result.stdout = ""
            result.stderr = ""
        return result

    mock_run.side_effect = mock_run_side_effect

    # Spawn grace period check - no activity detected
    mock_status.return_value = "in_progress"  # Status unchanged
    mock_activity.return_value = False  # No tmux activity
    mock_exists.return_value = False  # Session died

    result = ralph_loop_iteration("worker-1", mock_manager, spawn_grace=1)

    # Should continue looping after spawn failure
    assert result is True

    # Should have marked task as failed with spawn failure reason
    spawn_failed_calls = [
        call for call in mock_run.call_args_list
        if len(call[0]) > 0 and call[0][0] == ["bd", "update", "hive-123", "--status", "failed", "--notes"]
    ]

    # Find the bd update call with failed status
    failed_update_calls = [
        call for call in mock_run.call_args_list
        if len(call[0]) > 0 and "bd" in call[0][0] and "update" in call[0][0] and "hive-123" in call[0][0]
    ]

    # Verify that the task was marked as failed
    assert any("failed" in str(call) for call in failed_update_calls), "Task should be marked as failed"
    # Check for the new failure type format (agent_spawn_failure)
    assert any("agent_spawn" in str(call) for call in failed_update_calls), "Should include agent spawn failure reason"


# Note: More complex integration tests for ralph_loop_iteration are omitted
# to avoid test hangs. The unit tests above cover the core functionality.
# Integration testing should be done manually or with a real test environment.


def test_register_worker(tmp_path):
    """Test registering a worker in the registry."""
    from hive.commands.work import register_worker

    # Create .hive directory
    hive_dir = tmp_path / ".hive"
    hive_dir.mkdir()

    # Change to temp directory
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Register a worker
        register_worker(
            worker_id="worker-1",
            pid=12345,
            task_id="task-abc",
            tmux_session="hive-worker-1-task-abc",
            worktree="worktrees/worker-1-task-abc"
        )

        # Check that workers.json was created
        workers_path = hive_dir / "workers.json"
        assert workers_path.exists()

        # Read and verify contents
        import json
        with open(workers_path) as f:
            data = json.load(f)

        assert len(data["workers"]) == 1
        worker = data["workers"][0]
        assert worker["id"] == "worker-1"
        assert worker["pid"] == 12345
        assert worker["current_task"] == "task-abc"
        assert worker["tmux_session"] == "hive-worker-1-task-abc"
        assert worker["worktree"] == "worktrees/worker-1-task-abc"
        assert "started_at" in worker
        assert "last_activity" in worker
    finally:
        os.chdir(original_dir)


def test_unregister_worker(tmp_path):
    """Test unregistering a worker from the registry."""
    from hive.commands.work import register_worker, unregister_worker

    # Create .hive directory
    hive_dir = tmp_path / ".hive"
    hive_dir.mkdir()

    # Change to temp directory
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Register two workers
        register_worker("worker-1", 12345, "task-abc", "session-1", "worktree-1")
        register_worker("worker-2", 12346, "task-def", "session-2", "worktree-2")

        # Unregister worker-1
        unregister_worker("worker-1")

        # Check that only worker-2 remains
        import json
        workers_path = hive_dir / "workers.json"
        with open(workers_path) as f:
            data = json.load(f)

        assert len(data["workers"]) == 1
        assert data["workers"][0]["id"] == "worker-2"
    finally:
        os.chdir(original_dir)


def test_update_worker_activity(tmp_path):
    """Test updating worker activity timestamp."""
    from hive.commands.work import register_worker, update_worker_activity
    import time

    # Create .hive directory
    hive_dir = tmp_path / ".hive"
    hive_dir.mkdir()

    # Change to temp directory
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Register a worker
        register_worker("worker-1", 12345, "task-abc", "session-1", "worktree-1")

        # Get initial activity time
        import json
        workers_path = hive_dir / "workers.json"
        with open(workers_path) as f:
            data = json.load(f)
        initial_activity = data["workers"][0]["last_activity"]

        # Wait a bit and update activity
        time.sleep(0.1)
        update_worker_activity("worker-1")

        # Check that activity time was updated
        with open(workers_path) as f:
            data = json.load(f)
        new_activity = data["workers"][0]["last_activity"]

        assert new_activity != initial_activity
    finally:
        os.chdir(original_dir)


def test_work_cmd_with_parallel(tmp_path):
    """Test work command with --parallel option."""
    runner = CliRunner()
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Create .beads and .hive directories
        (tmp_path / ".beads").mkdir()
        (tmp_path / ".hive").mkdir()

        # Mock the multiprocessing to avoid actually spawning processes
        with patch("hive.commands.work.multiprocessing.Process") as mock_process:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_process.return_value = mock_proc

            result = runner.invoke(work_cmd, ["--parallel", "2"])

            # Should start 2 processes
            assert mock_process.call_count == 2
            assert "Starting 2 parallel workers" in result.output
    finally:
        os.chdir(original_dir)


def test_work_cmd_parallel_validation(tmp_path):
    """Test work command validates parallel count."""
    runner = CliRunner()
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Create .beads and .hive directories
        (tmp_path / ".beads").mkdir()
        (tmp_path / ".hive").mkdir()

        result = runner.invoke(work_cmd, ["--parallel", "0"])

        assert result.exit_code == 1
        assert "--parallel must be >= 1" in result.output
    finally:
        os.chdir(original_dir)
