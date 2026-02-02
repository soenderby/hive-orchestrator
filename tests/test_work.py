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
    """Test getting next task from Beads."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([{"id": "hive-123", "title": "Test task"}]),
    )

    task = get_next_task()
    assert task is not None
    assert task["id"] == "hive-123"
    assert task["title"] == "Test task"


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
    assert any("agent_spawn_failed" in str(call) for call in failed_update_calls), "Should include agent_spawn_failed reason"


# Note: More complex integration tests for ralph_loop_iteration are omitted
# to avoid test hangs. The unit tests above cover the core functionality.
# Integration testing should be done manually or with a real test environment.
