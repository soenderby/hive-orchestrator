"""Tests for hive plan command."""

from pathlib import Path
from click.testing import CliRunner
from hive.cli import main


def test_plan_requires_init(tmp_path):
    """Test that hive plan requires initialization."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["plan", "Test goal"])
        assert result.exit_code == 1
        assert "Hive not initialized" in result.output


def test_plan_creates_plan_file(tmp_path):
    """Test that hive plan creates a plan file."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize first
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])

        # Create a plan
        result = runner.invoke(main, ["plan", "Build a REST API"])
        assert result.exit_code == 0
        assert "✓ Plan created and saved" in result.output
        assert "Goal: Build a REST API" in result.output

        # Verify plan file exists and has content
        plan_path = Path(".hive/plan.md")
        assert plan_path.exists()

        content = plan_path.read_text()
        assert "# Hive Plan" in content
        assert "Build a REST API" in content
        assert "> **Status:** In Progress" in content
        assert "## Tasks" in content


def test_plan_show_displays_plan(tmp_path):
    """Test that hive plan --show displays the current plan."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize and create plan
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])
        runner.invoke(main, ["plan", "Test goal"])

        # Show the plan
        result = runner.invoke(main, ["plan", "--show"])
        assert result.exit_code == 0
        assert "# Hive Plan" in result.output
        assert "Test goal" in result.output


def test_plan_show_without_plan(tmp_path):
    """Test that hive plan --show fails when no plan exists."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize but don't create plan
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])

        # Remove the default plan created by init
        Path(".hive/plan.md").unlink()

        # Try to show non-existent plan
        result = runner.invoke(main, ["plan", "--show"])
        assert result.exit_code == 1
        assert "✗ No plan found" in result.output


def test_plan_approve_updates_status(tmp_path):
    """Test that hive plan --approve updates the plan status."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize and create plan
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])
        runner.invoke(main, ["plan", "Test goal"])

        # Approve the plan
        result = runner.invoke(main, ["plan", "--approve"])
        assert result.exit_code == 0
        assert "✓ Plan approved" in result.output

        # Verify status changed in file
        plan_path = Path(".hive/plan.md")
        content = plan_path.read_text()
        assert "> **Status:** Approved" in content
        assert "> **Status:** In Progress" not in content


def test_plan_approve_idempotent(tmp_path):
    """Test that approving an already approved plan is idempotent."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize and create plan
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])
        runner.invoke(main, ["plan", "Test goal"])

        # Approve twice
        runner.invoke(main, ["plan", "--approve"])
        result = runner.invoke(main, ["plan", "--approve"])
        assert result.exit_code == 0
        assert "⚠ Plan already approved" in result.output


def test_plan_approve_without_plan(tmp_path):
    """Test that hive plan --approve fails when no plan exists."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize but don't create plan
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])

        # Remove the default plan created by init
        Path(".hive/plan.md").unlink()

        # Try to approve non-existent plan
        result = runner.invoke(main, ["plan", "--approve"])
        assert result.exit_code == 1
        assert "✗ No plan found" in result.output


def test_plan_requires_goal_argument(tmp_path):
    """Test that hive plan requires a goal argument."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])

        # Try to create plan without goal
        result = runner.invoke(main, ["plan"])
        assert result.exit_code == 1
        assert "Error: Missing GOAL argument" in result.output


def test_plan_continue_with_too_big_task(tmp_path):
    """Test that hive plan --continue handles too_big tasks."""
    from unittest.mock import patch, MagicMock
    import json

    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])

        # Mock bd list command to return a too_big task
        mock_tasks = [
            {
                "id": "hive-123",
                "title": "Big task that needs decomposition",
                "status": "too_big"
            }
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(mock_tasks)
            )

            # Run plan --continue
            result = runner.invoke(main, ["plan", "--continue"])
            assert result.exit_code == 0
            assert "hive-123" in result.output
            assert "Big task that needs decomposition" in result.output
            assert "Create subtasks" in result.output
            assert "bd close hive-123" in result.output


def test_plan_continue_without_too_big_tasks(tmp_path):
    """Test that hive plan --continue fails when no too_big tasks exist."""
    from unittest.mock import patch, MagicMock
    import json

    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize
        Path(".beads").mkdir()
        runner.invoke(main, ["init"])

        # Mock bd list command to return empty list
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([])
            )

            # Run plan --continue
            result = runner.invoke(main, ["plan", "--continue"])
            assert result.exit_code == 1
            assert "No tasks marked as too_big" in result.output
