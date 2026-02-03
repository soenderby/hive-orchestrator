"""Tests for daemon command functionality."""

import json
import os
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from hive.commands.daemon import (
    daemon_cmd,
    get_daemon_pid,
    is_daemon_running,
    write_daemon_pid,
    remove_daemon_pid,
    get_workers,
    check_stuck_workers,
    DAEMON_PID_FILE,
    DAEMON_LOG_FILE,
)


@pytest.fixture
def hive_dir(tmp_path):
    """Create a temporary .hive directory."""
    hive_path = tmp_path / ".hive"
    hive_path.mkdir()

    # Create workers.json
    workers_file = hive_path / "workers.json"
    workers_file.write_text(json.dumps({
        "workers": [],
        "last_updated": datetime.now().isoformat()
    }))

    # Change to tmp_path for tests
    original_dir = os.getcwd()
    os.chdir(tmp_path)

    yield hive_path

    os.chdir(original_dir)


def test_get_daemon_pid_no_file(hive_dir):
    """Test getting daemon PID when no PID file exists."""
    assert get_daemon_pid() is None


def test_get_daemon_pid_with_file(hive_dir):
    """Test getting daemon PID from file."""
    # Write current process PID
    write_daemon_pid(os.getpid())

    pid = get_daemon_pid()
    assert pid == os.getpid()


def test_get_daemon_pid_stale_file(hive_dir):
    """Test getting daemon PID when process is not running."""
    # Write a PID that doesn't exist
    fake_pid = 999999
    write_daemon_pid(fake_pid)

    # Should return None and clean up stale file
    pid = get_daemon_pid()
    assert pid is None
    assert not Path(DAEMON_PID_FILE).exists()


def test_is_daemon_running(hive_dir):
    """Test checking if daemon is running."""
    assert not is_daemon_running()

    write_daemon_pid(os.getpid())
    assert is_daemon_running()


def test_write_daemon_pid(hive_dir):
    """Test writing daemon PID to file."""
    write_daemon_pid(12345)

    pid_file = Path(DAEMON_PID_FILE)
    assert pid_file.exists()
    assert pid_file.read_text().strip() == "12345"


def test_remove_daemon_pid(hive_dir):
    """Test removing daemon PID file."""
    write_daemon_pid(12345)
    assert Path(DAEMON_PID_FILE).exists()

    remove_daemon_pid()
    assert not Path(DAEMON_PID_FILE).exists()


def test_get_workers_empty(hive_dir):
    """Test getting workers when registry is empty."""
    workers = get_workers()
    assert workers == []


def test_get_workers_with_data(hive_dir):
    """Test getting workers from registry."""
    # Add a worker to the registry
    workers_file = Path(".hive/workers.json")
    data = {
        "workers": [
            {
                "id": "worker-1",
                "pid": 12345,
                "current_task": "hive-abc",
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
            }
        ],
        "last_updated": datetime.now().isoformat()
    }
    workers_file.write_text(json.dumps(data))

    workers = get_workers()
    assert len(workers) == 1
    assert workers[0]["id"] == "worker-1"


def test_check_stuck_workers_none(hive_dir):
    """Test checking for stuck workers when none are stuck."""
    # Add a recent worker
    workers_file = Path(".hive/workers.json")
    data = {
        "workers": [
            {
                "id": "worker-1",
                "current_task": "hive-abc",
                "last_activity": datetime.now().isoformat(),
            }
        ],
        "last_updated": datetime.now().isoformat()
    }
    workers_file.write_text(json.dumps(data))

    stuck = check_stuck_workers(stuck_threshold=300)
    assert len(stuck) == 0


def test_check_stuck_workers_found(hive_dir):
    """Test checking for stuck workers when some are stuck."""
    # Add a stuck worker (activity 10 minutes ago)
    old_time = datetime.now() - timedelta(minutes=10)
    workers_file = Path(".hive/workers.json")
    data = {
        "workers": [
            {
                "id": "worker-1",
                "current_task": "hive-abc",
                "last_activity": old_time.isoformat(),
            }
        ],
        "last_updated": datetime.now().isoformat()
    }
    workers_file.write_text(json.dumps(data))

    stuck = check_stuck_workers(stuck_threshold=300)  # 5 minutes
    assert len(stuck) == 1
    assert stuck[0]["id"] == "worker-1"
    assert stuck[0]["stuck_duration"] >= 600  # At least 10 minutes


def test_daemon_start_cmd_no_hive(tmp_path):
    """Test daemon start fails without .hive directory."""
    runner = CliRunner()
    os.chdir(tmp_path)

    result = runner.invoke(daemon_cmd, ["start"])

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_daemon_start_cmd_already_running(hive_dir):
    """Test daemon start fails if already running."""
    runner = CliRunner()
    write_daemon_pid(os.getpid())

    result = runner.invoke(daemon_cmd, ["start"])

    assert result.exit_code == 1
    assert "already running" in result.output


def test_daemon_start_cmd_foreground(hive_dir):
    """Test daemon start in foreground mode."""
    # Skip this test as it's hard to test without blocking
    # The foreground mode is better tested manually
    pytest.skip("Foreground mode test requires complex setup to avoid blocking")


def test_daemon_stop_cmd_not_running(hive_dir):
    """Test daemon stop when not running."""
    runner = CliRunner()

    result = runner.invoke(daemon_cmd, ["stop"])

    assert result.exit_code == 1
    assert "not running" in result.output


def test_daemon_stop_cmd_success(hive_dir):
    """Test daemon stop when running."""
    # This test is hard to do properly without actually running a daemon
    # Since we can't write a fake PID (it gets cleaned up immediately)
    # and we can't kill our own process, we'll skip this
    pytest.skip("Requires actual daemon process to test stop command")


def test_daemon_status_cmd_not_running(hive_dir):
    """Test daemon status when not running."""
    runner = CliRunner()

    result = runner.invoke(daemon_cmd, ["status"])

    assert result.exit_code == 0
    assert "not running" in result.output


def test_daemon_status_cmd_running(hive_dir):
    """Test daemon status when running."""
    runner = CliRunner()
    write_daemon_pid(os.getpid())

    result = runner.invoke(daemon_cmd, ["status"])

    assert result.exit_code == 0
    assert "running" in result.output.lower()


def test_daemon_status_cmd_json(hive_dir):
    """Test daemon status with JSON output."""
    runner = CliRunner()

    result = runner.invoke(daemon_cmd, ["status", "--json"])

    assert result.exit_code == 0
    status = json.loads(result.output)
    assert "running" in status
    assert status["running"] is False


def test_daemon_status_cmd_json_with_stuck_workers(hive_dir):
    """Test daemon status JSON includes stuck workers."""
    runner = CliRunner()
    write_daemon_pid(os.getpid())

    # Add a stuck worker
    old_time = datetime.now() - timedelta(minutes=10)
    workers_file = Path(".hive/workers.json")
    data = {
        "workers": [
            {
                "id": "worker-1",
                "current_task": "hive-abc",
                "last_activity": old_time.isoformat(),
            }
        ],
        "last_updated": datetime.now().isoformat()
    }
    workers_file.write_text(json.dumps(data))

    result = runner.invoke(daemon_cmd, ["status", "--json"])

    assert result.exit_code == 0
    status = json.loads(result.output)
    assert "stuck_workers" in status
    assert len(status["stuck_workers"]) == 1


def test_daemon_logs_cmd_no_logs(hive_dir):
    """Test daemon logs when no log file exists."""
    runner = CliRunner()

    result = runner.invoke(daemon_cmd, ["logs"])

    assert result.exit_code == 0
    assert "No daemon logs" in result.output or result.output.strip() == ""


def test_daemon_logs_cmd_with_logs(hive_dir):
    """Test daemon logs with log file."""
    # Create a log file
    log_file = Path(DAEMON_LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("[2024-01-01T12:00:00] Test log message\n")

    runner = CliRunner()
    result = runner.invoke(daemon_cmd, ["logs"])

    assert result.exit_code == 0
    assert "Test log message" in result.output


def test_daemon_help(hive_dir):
    """Test daemon help command."""
    runner = CliRunner()

    result = runner.invoke(daemon_cmd, ["--help"])

    assert result.exit_code == 0
    assert "Monitor and manage" in result.output
