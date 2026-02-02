"""Tests for CLAUDE.md context generation."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from hive.context import generate_claude_context, generate_claude_context_from_beads


def test_generate_claude_context_basic():
    """Test basic CLAUDE.md generation."""
    content = generate_claude_context(
        task_id="test-123",
        task_title="Implement feature X",
        task_description="This is a test task",
        task_type="feature",
    )

    # Check required sections
    assert "# Task Context" in content
    assert "test-123" in content
    assert "Implement feature X" in content
    assert "This is a test task" in content
    assert "feature" in content

    # Check worker instructions
    assert "When Task is Complete" in content
    assert "If Task is Too Big" in content
    assert "If Task is Blocked" in content
    assert "bd close test-123" in content


def test_generate_claude_context_with_acceptance_criteria():
    """Test CLAUDE.md generation with custom acceptance criteria."""
    content = generate_claude_context(
        task_id="test-123",
        task_title="Test task",
        task_description="Description",
        acceptance_criteria="- All tests pass\n- Code is documented",
    )

    assert "- All tests pass" in content
    assert "- Code is documented" in content


def test_generate_claude_context_with_plan(tmp_path):
    """Test CLAUDE.md generation with plan context."""
    # Create a plan file
    plan_path = tmp_path / "plan.md"
    plan_content = """# Project Plan

Goal: Build awesome feature

Tasks:
- Task 1
- Task 2
"""
    plan_path.write_text(plan_content)

    content = generate_claude_context(
        task_id="test-123",
        task_title="Test task",
        task_description="Description",
        plan_path=plan_path,
    )

    assert "Build awesome feature" in content
    assert "Task 1" in content


def test_generate_claude_context_without_plan():
    """Test CLAUDE.md generation without plan."""
    content = generate_claude_context(
        task_id="test-123",
        task_title="Test task",
        task_description="Description",
    )

    assert "(No plan available" in content


def test_generate_claude_context_writes_file(tmp_path):
    """Test that CLAUDE.md is written to file."""
    output_path = tmp_path / "CLAUDE.md"

    content = generate_claude_context(
        task_id="test-123",
        task_title="Test task",
        task_description="Description",
        output_path=output_path,
    )

    # Check file was created
    assert output_path.exists()

    # Check file content matches returned content
    file_content = output_path.read_text()
    assert file_content == content
    assert "test-123" in file_content


def test_generate_claude_context_creates_directories(tmp_path):
    """Test that parent directories are created if needed."""
    output_path = tmp_path / "subdir" / "nested" / "CLAUDE.md"

    generate_claude_context(
        task_id="test-123",
        task_title="Test task",
        task_description="Description",
        output_path=output_path,
    )

    # Check file and directories were created
    assert output_path.exists()
    assert output_path.parent.exists()


@patch("hive.context.subprocess.run")
def test_generate_claude_context_from_beads(mock_run):
    """Test generating context from Beads task data."""
    # Mock bd show output
    mock_task = {
        "id": "test-123",
        "title": "Implement API endpoint",
        "description": "Add POST /api/users endpoint",
        "type": "task",
        "status": "open",
    }

    mock_run.return_value = MagicMock(
        stdout=json.dumps(mock_task),
        returncode=0,
    )

    content = generate_claude_context_from_beads("test-123")

    # Verify bd was called correctly
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args == ["bd", "show", "test-123", "--json"]

    # Check content includes task data
    assert "test-123" in content
    assert "Implement API endpoint" in content
    assert "Add POST /api/users endpoint" in content


@patch("hive.context.subprocess.run")
def test_generate_claude_context_from_beads_with_plan(mock_run, tmp_path):
    """Test generating context from Beads with plan file."""
    # Mock bd show output
    mock_task = {
        "id": "test-123",
        "title": "Test task",
        "description": "Description",
        "type": "task",
    }

    mock_run.return_value = MagicMock(
        stdout=json.dumps(mock_task),
        returncode=0,
    )

    # Create plan file
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Project Goal\n\nBuild feature X")

    content = generate_claude_context_from_beads(
        "test-123",
        plan_path=plan_path,
    )

    assert "Build feature X" in content


@patch("hive.context.subprocess.run")
def test_generate_claude_context_from_beads_writes_file(mock_run, tmp_path):
    """Test that context from Beads is written to file."""
    # Mock bd show output
    mock_task = {
        "id": "test-123",
        "title": "Test task",
        "description": "Description",
        "type": "task",
    }

    mock_run.return_value = MagicMock(
        stdout=json.dumps(mock_task),
        returncode=0,
    )

    output_path = tmp_path / "CLAUDE.md"

    generate_claude_context_from_beads(
        "test-123",
        output_path=output_path,
    )

    assert output_path.exists()
    content = output_path.read_text()
    assert "test-123" in content
