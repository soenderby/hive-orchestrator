"""Tests for hive task commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from hive.cli import main


@patch("hive.commands.task.subprocess.run")
def test_task_list_basic(mock_run):
    """Test basic task list command."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "list"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["bd", "list"]


@patch("hive.commands.task.subprocess.run")
def test_task_list_with_status(mock_run):
    """Test task list with status filter."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "list", "--status", "open"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["bd", "list", "--status", "open"]


@patch("hive.commands.task.subprocess.run")
def test_task_list_with_json(mock_run):
    """Test task list with JSON output."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "list", "--json"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["bd", "list", "--json"]


@patch("hive.commands.task.subprocess.run")
def test_task_show_basic(mock_run):
    """Test basic task show command."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "show", "hive-123"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["bd", "show", "hive-123"]


@patch("hive.commands.task.subprocess.run")
def test_task_show_with_json(mock_run):
    """Test task show with JSON output."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "show", "hive-123", "--json"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["bd", "show", "hive-123", "--json"]


@patch("hive.commands.task.subprocess.run")
def test_task_add_basic(mock_run):
    """Test basic task add command."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "add", "Test task"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == [
        "bd",
        "create",
        "--title", "Test task",
        "--type", "task",
        "--priority", "2",
        "--notes", "Created via hive task add (discovered work)",
    ]


@patch("hive.commands.task.subprocess.run")
def test_task_add_with_priority(mock_run):
    """Test task add with custom priority."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "add", "Urgent task", "--priority", "1"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == [
        "bd",
        "create",
        "--title", "Urgent task",
        "--type", "task",
        "--priority", "1",
        "--notes", "Created via hive task add (discovered work)",
    ]


@patch("hive.commands.task.subprocess.run")
def test_task_add_with_type(mock_run):
    """Test task add with custom type."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "add", "Bug fix", "--type", "bug"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == [
        "bd",
        "create",
        "--title", "Bug fix",
        "--type", "bug",
        "--priority", "2",
        "--notes", "Created via hive task add (discovered work)",
    ]


@patch("hive.commands.task.subprocess.run")
def test_task_command_passes_through_exit_code(mock_run):
    """Test that non-zero exit codes are passed through."""
    mock_run.return_value = MagicMock(returncode=1)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "list"])

    assert result.exit_code == 1


def test_task_help():
    """Test that task help is displayed."""
    runner = CliRunner()

    result = runner.invoke(main, ["task", "--help"])

    assert result.exit_code == 0
    assert "Manage tasks" in result.output
    assert "list" in result.output
    assert "show" in result.output
    assert "add" in result.output


@patch("hive.commands.task.subprocess.run")
def test_task_too_big_basic(mock_run):
    """Test basic task too-big command."""
    mock_run.return_value = MagicMock(returncode=0)
    runner = CliRunner()

    result = runner.invoke(main, ["task", "too-big", "hive-123"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["bd", "update", "hive-123", "--status", "too_big"]
