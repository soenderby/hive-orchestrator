"""Tests for merge command functionality."""

import subprocess
from pathlib import Path
import pytest
from click.testing import CliRunner

from hive.commands.merge import merge_cmd, sync_cmd, find_worktree_by_identifier, check_merge_status
from hive.worktree import WorktreeManager


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit on main branch
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Ensure we're on main branch
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    return repo_path


def test_find_worktree_by_task_id(git_repo):
    """Test finding worktree by task ID."""
    manager = WorktreeManager(repo_root=git_repo)
    worktree_path = manager.create_worktree("worker-1", "hive-abc")

    result = find_worktree_by_identifier("hive-abc", manager)

    assert result is not None
    path, branch, task_id = result
    assert path == worktree_path
    assert branch == "task-hive-abc"
    assert task_id == "hive-abc"


def test_find_worktree_by_worker_task_combo(git_repo):
    """Test finding worktree by worker-task combo."""
    manager = WorktreeManager(repo_root=git_repo)
    worktree_path = manager.create_worktree("worker-1", "hive-abc")

    result = find_worktree_by_identifier("worker-1-hive-abc", manager)

    assert result is not None
    path, branch, task_id = result
    assert path == worktree_path
    assert branch == "task-hive-abc"
    assert task_id == "hive-abc"


def test_find_worktree_by_path(git_repo):
    """Test finding worktree by full path."""
    manager = WorktreeManager(repo_root=git_repo)
    worktree_path = manager.create_worktree("worker-1", "hive-abc")

    result = find_worktree_by_identifier(str(worktree_path), manager)

    assert result is not None
    path, branch, task_id = result
    assert path == worktree_path
    assert branch == "task-hive-abc"
    assert task_id == "hive-abc"


def test_find_worktree_nonexistent(git_repo):
    """Test finding a non-existent worktree."""
    manager = WorktreeManager(repo_root=git_repo)

    result = find_worktree_by_identifier("hive-nonexistent", manager)

    assert result is None


def test_check_merge_status_clean(git_repo):
    """Test checking merge status of a clean worktree."""
    manager = WorktreeManager(repo_root=git_repo)
    worktree_path = manager.create_worktree("worker-1", "hive-abc")

    status = check_merge_status(worktree_path)

    assert status['has_conflicts'] is False
    assert status['conflicted_files'] == []
    assert status['uncommitted_changes'] is False
    assert status['current_branch'] == "task-hive-abc"


def test_check_merge_status_with_uncommitted_changes(git_repo):
    """Test checking merge status with uncommitted changes."""
    manager = WorktreeManager(repo_root=git_repo)
    worktree_path = manager.create_worktree("worker-1", "hive-abc")

    # Add uncommitted changes
    (worktree_path / "test.txt").write_text("test content")

    status = check_merge_status(worktree_path)

    assert status['has_conflicts'] is False
    assert status['uncommitted_changes'] is True


def test_merge_cmd_cleanup_only(git_repo):
    """Test merge command with cleanup-only flag."""
    runner = CliRunner()
    manager = WorktreeManager(repo_root=git_repo)

    # Create worktree and commit some work
    worktree_path = manager.create_worktree("worker-1", "hive-abc")
    (worktree_path / "feature.txt").write_text("new feature")
    subprocess.run(["git", "add", "."], cwd=worktree_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add feature"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
    )

    # Run merge command with cleanup-only
    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(merge_cmd, ["hive-abc", "--cleanup-only"])

    assert result.exit_code == 0
    assert "Cleanup complete" in result.output
    assert not worktree_path.exists()


def test_merge_cmd_with_uncommitted_changes(git_repo):
    """Test merge command detects uncommitted changes."""
    runner = CliRunner()
    manager = WorktreeManager(repo_root=git_repo)

    # Create worktree with uncommitted changes
    worktree_path = manager.create_worktree("worker-1", "hive-abc")
    (worktree_path / "test.txt").write_text("uncommitted")

    # Run merge command
    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(merge_cmd, ["hive-abc"])

    assert result.exit_code == 0
    assert "uncommitted changes" in result.output.lower()
    assert worktree_path.exists()  # Should preserve worktree


def test_merge_cmd_successful_merge(git_repo):
    """Test successful merge workflow."""
    runner = CliRunner()
    manager = WorktreeManager(repo_root=git_repo)

    # Create worktree and commit some work
    worktree_path = manager.create_worktree("worker-1", "hive-abc")
    (worktree_path / "feature.txt").write_text("new feature")
    subprocess.run(["git", "add", "."], cwd=worktree_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add feature"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
    )

    # Run merge command
    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(merge_cmd, ["hive-abc"])

    assert result.exit_code == 0
    assert "Merge successful" in result.output
    assert "Cleanup complete" in result.output
    assert not worktree_path.exists()

    # Verify merge happened
    assert (git_repo / "feature.txt").exists()
    assert (git_repo / "feature.txt").read_text() == "new feature"


def test_merge_cmd_not_found(git_repo):
    """Test merge command with non-existent worktree."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(merge_cmd, ["hive-nonexistent"])

    assert result.exit_code == 1
    assert "Could not find worktree" in result.output


def test_sync_cmd_no_branches(git_repo):
    """Test sync command with no task branches."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(sync_cmd, [])

    assert result.exit_code == 0
    assert "No task branches found" in result.output


def test_sync_cmd_dry_run(git_repo):
    """Test sync command in dry-run mode."""
    runner = CliRunner()
    manager = WorktreeManager(repo_root=git_repo)

    # Create worktree
    manager.create_worktree("worker-1", "hive-abc")

    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(sync_cmd, ["--dry-run"])

    assert result.exit_code == 0
    assert "Dry run mode" in result.output
    assert "task-hive-abc" in result.output


def test_sync_cmd_push_only(git_repo, tmp_path):
    """Test sync command with push only."""
    # This test would need a remote repo setup
    # For now, just test that the command accepts the flag
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(sync_cmd, ["--push"])

    # Should succeed even with no branches
    assert result.exit_code == 0


def test_sync_cmd_pull_only(git_repo):
    """Test sync command with pull only."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(sync_cmd, ["--pull"])

    # Should succeed even with no branches
    assert result.exit_code == 0


def test_merge_cmd_force_cleanup(git_repo):
    """Test merge command with force cleanup of uncommitted changes."""
    runner = CliRunner()
    manager = WorktreeManager(repo_root=git_repo)

    # Create worktree with uncommitted changes
    worktree_path = manager.create_worktree("worker-1", "hive-abc")
    (worktree_path / "test.txt").write_text("uncommitted")

    # Run merge command with force cleanup
    with runner.isolated_filesystem(temp_dir=git_repo):
        result = runner.invoke(merge_cmd, ["hive-abc", "--cleanup-only", "--force"])

    assert result.exit_code == 0
    assert "Cleanup complete" in result.output
    assert not worktree_path.exists()
