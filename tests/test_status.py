"""Tests for the status command."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from hive.commands.status import status_cmd


@pytest.fixture
def temp_hive_dir(tmp_path):
    """Create a temporary .hive directory."""
    hive_dir = tmp_path / ".hive"
    hive_dir.mkdir()
    return hive_dir


@pytest.fixture
def mock_workers_file(temp_hive_dir):
    """Create a mock workers.json file."""
    workers_path = temp_hive_dir / "workers.json"
    workers_data = {
        "workers": [
            {
                "id": "worker-1",
                "pid": 12345,
                "tmux_session": "hive-worker-1-task-abc",
                "worktree": "worktrees/worker-1-task-abc",
                "current_task": "task-abc",
                "started_at": "2026-01-27T10:00:00Z",
                "last_activity": "2026-01-27T10:15:00Z",
            }
        ],
        "last_updated": "2026-01-27T10:15:00Z",
    }
    with open(workers_path, "w") as f:
        json.dump(workers_data, f)
    return workers_path


def test_status_shows_no_workers(tmp_path):
    """Test status command with no active workers."""
    runner = CliRunner()
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        (tmp_path / ".hive").mkdir(exist_ok=True)
        (tmp_path / ".hive" / "workers.json").write_text(
            json.dumps({"workers": [], "last_updated": None})
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps([]), returncode=0
            )

            result = runner.invoke(status_cmd)

            assert result.exit_code == 0
            assert "Active Workers: 0" in result.output
            assert "No active workers" in result.output
    finally:
        os.chdir(original_dir)


def test_status_shows_active_workers(tmp_path):
    """Test status command with active workers."""
    runner = CliRunner()
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        (tmp_path / ".hive").mkdir(exist_ok=True)
        workers_data = {
            "workers": [
                {
                    "id": "worker-1",
                    "pid": 12345,
                    "tmux_session": "hive-worker-1-task-abc",
                    "worktree": "worktrees/worker-1-task-abc",
                    "current_task": "task-abc",
                    "started_at": "2026-01-27T10:00:00Z",
                    "last_activity": "2026-01-27T10:15:00Z",
                }
            ],
            "last_updated": "2026-01-27T10:15:00Z",
        }
        (tmp_path / ".hive" / "workers.json").write_text(json.dumps(workers_data))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps([]), returncode=0
            )

            result = runner.invoke(status_cmd)

            assert result.exit_code == 0
            assert "Active Workers: 1" in result.output
            assert "worker-1" in result.output
            assert "task-abc" in result.output
    finally:
        os.chdir(original_dir)


def test_status_shows_task_statistics(tmp_path):
    """Test status command shows task statistics."""
    runner = CliRunner()
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        (tmp_path / ".hive").mkdir(exist_ok=True)
        (tmp_path / ".hive" / "workers.json").write_text(
            json.dumps({"workers": [], "last_updated": None})
        )

        # Mock bd list output
        mock_tasks = [
            {"id": "task-1", "status": "open", "title": "Task 1"},
            {"id": "task-2", "status": "in_progress", "title": "Task 2"},
            {"id": "task-3", "status": "done", "title": "Task 3"},
            {"id": "task-4", "status": "done", "title": "Task 4"},
            {"id": "task-5", "status": "blocked", "title": "Task 5"},
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps(mock_tasks), returncode=0
            )

            result = runner.invoke(status_cmd)

            assert result.exit_code == 0
            assert "Total: 5" in result.output
            assert "Open: 1" in result.output
            assert "In Progress: 1" in result.output
            assert "Done: 2" in result.output
            assert "Blocked: 1" in result.output
            assert "Overall Progress: 2/5 (40.0%)" in result.output
    finally:
        os.chdir(original_dir)


def test_status_json_output(tmp_path):
    """Test status command with JSON output."""
    runner = CliRunner()
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        (tmp_path / ".hive").mkdir(exist_ok=True)
        workers_data = {
            "workers": [
                {
                    "id": "worker-1",
                    "pid": 12345,
                    "tmux_session": "hive-worker-1-task-abc",
                    "worktree": "worktrees/worker-1-task-abc",
                    "current_task": "task-abc",
                    "started_at": "2026-01-27T10:00:00Z",
                    "last_activity": "2026-01-27T10:15:00Z",
                }
            ],
            "last_updated": "2026-01-27T10:15:00Z",
        }
        (tmp_path / ".hive" / "workers.json").write_text(json.dumps(workers_data))

        mock_tasks = [
            {"id": "task-1", "status": "open", "title": "Task 1"},
            {"id": "task-2", "status": "done", "title": "Task 2"},
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps(mock_tasks), returncode=0
            )

            result = runner.invoke(status_cmd, ["--json"])

            assert result.exit_code == 0

            # Parse JSON output
            output_data = json.loads(result.output)
            assert len(output_data["workers"]) == 1
            assert output_data["workers"][0]["id"] == "worker-1"
            assert output_data["total_tasks"] == 2
            assert output_data["task_counts"]["open"] == 1
            assert output_data["task_counts"]["done"] == 1
    finally:
        os.chdir(original_dir)


def test_status_without_hive_init(tmp_path):
    """Test status command when hive is not initialized."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(status_cmd)

        assert result.exit_code == 0
        assert "✗ Hive not initialized" in result.output
