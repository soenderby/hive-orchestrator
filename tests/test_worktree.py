"""Tests for git worktree management."""

import subprocess
from pathlib import Path
import pytest
from hive.worktree import WorktreeManager, WorktreeError


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


def test_create_worktree(git_repo):
    """Test creating a new worktree."""
    manager = WorktreeManager(repo_root=git_repo)

    worktree_path = manager.create_worktree("worker-1", "test-123")

    # Check worktree was created
    assert worktree_path.exists()
    assert worktree_path == git_repo / "worktrees" / "worker-1-test-123"

    # Check files are present in worktree
    assert (worktree_path / "README.md").exists()

    # Check branch was created
    result = subprocess.run(
        ["git", "branch", "--list", "task-test-123"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    assert "task-test-123" in result.stdout


def test_create_worktree_custom_base_branch(git_repo):
    """Test creating worktree from a custom base branch."""
    # Create a feature branch
    subprocess.run(
        ["git", "checkout", "-b", "feature"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )
    (git_repo / "feature.txt").write_text("Feature file")
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add feature"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "main"], cwd=git_repo, check=True, capture_output=True
    )

    manager = WorktreeManager(repo_root=git_repo)
    worktree_path = manager.create_worktree("worker-1", "test-123", base_branch="feature")

    # Check feature file is present in worktree
    assert (worktree_path / "feature.txt").exists()


def test_create_worktree_already_exists(git_repo):
    """Test that creating an existing worktree raises an error."""
    manager = WorktreeManager(repo_root=git_repo)

    # Create worktree
    manager.create_worktree("worker-1", "test-123")

    # Try to create again - should fail
    with pytest.raises(WorktreeError, match="Worktree already exists"):
        manager.create_worktree("worker-1", "test-123")


def test_create_worktree_with_force(git_repo):
    """Test that force=True removes existing worktree first."""
    manager = WorktreeManager(repo_root=git_repo)

    # Create worktree
    worktree_path = manager.create_worktree("worker-1", "test-123")

    # Add a file to the worktree
    (worktree_path / "test.txt").write_text("test")

    # Create again with force=True - should succeed
    new_worktree_path = manager.create_worktree("worker-1", "test-123", force=True)

    # Check worktree was recreated (file should be gone)
    assert new_worktree_path.exists()
    assert not (new_worktree_path / "test.txt").exists()


def test_remove_worktree(git_repo):
    """Test removing a worktree."""
    manager = WorktreeManager(repo_root=git_repo)

    # Create and then remove worktree
    worktree_path = manager.create_worktree("worker-1", "test-123")
    assert worktree_path.exists()

    manager.remove_worktree("worker-1", "test-123")

    # Check worktree was removed
    assert not worktree_path.exists()

    # Check branch was deleted
    result = subprocess.run(
        ["git", "branch", "--list", "task-test-123"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    assert "task-test-123" not in result.stdout


def test_remove_nonexistent_worktree(git_repo):
    """Test that removing a non-existent worktree doesn't raise an error."""
    manager = WorktreeManager(repo_root=git_repo)

    # Should not raise an error
    manager.remove_worktree("worker-1", "nonexistent")


def test_remove_worktree_with_uncommitted_changes(git_repo):
    """Test removing worktree with uncommitted changes."""
    manager = WorktreeManager(repo_root=git_repo)

    # Create worktree and add uncommitted changes
    worktree_path = manager.create_worktree("worker-1", "test-123")
    (worktree_path / "test.txt").write_text("uncommitted")

    # Remove without force - should fail
    with pytest.raises(WorktreeError):
        manager.remove_worktree("worker-1", "test-123", force=False)

    # Remove with force - should succeed
    manager.remove_worktree("worker-1", "test-123", force=True)
    assert not worktree_path.exists()


def test_list_worktrees(git_repo):
    """Test listing all worktrees."""
    manager = WorktreeManager(repo_root=git_repo)

    # Create a couple of worktrees
    manager.create_worktree("worker-1", "test-123")
    manager.create_worktree("worker-2", "test-456")

    worktrees = manager.list_worktrees()

    # Should have 3 worktrees: main repo + 2 task worktrees
    assert len(worktrees) >= 3

    # Check main repo is listed
    main_wt = next((w for w in worktrees if Path(w["path"]) == git_repo), None)
    assert main_wt is not None
    assert main_wt["branch"] == "refs/heads/main"

    # Check task worktrees are listed
    task_wts = [w for w in worktrees if "task-" in w.get("branch", "")]
    assert len(task_wts) == 2


def test_worktree_exists(git_repo):
    """Test checking if a worktree exists."""
    manager = WorktreeManager(repo_root=git_repo)

    # Should not exist initially
    assert not manager.worktree_exists("worker-1", "test-123")

    # Create worktree
    manager.create_worktree("worker-1", "test-123")

    # Should exist now
    assert manager.worktree_exists("worker-1", "test-123")

    # Remove worktree
    manager.remove_worktree("worker-1", "test-123")

    # Should not exist after removal
    assert not manager.worktree_exists("worker-1", "test-123")


def test_cleanup_stale_worktrees(git_repo):
    """Test cleaning up stale worktrees."""
    manager = WorktreeManager(repo_root=git_repo)

    # Create a worktree
    worktree_path = manager.create_worktree("worker-1", "test-123")

    # Simulate a crash by manually deleting the directory
    # but not removing it from git's tracking
    import shutil
    shutil.rmtree(worktree_path)

    # Worktree should still be tracked by git
    worktrees = manager.list_worktrees()
    assert any("task-test-123" in w.get("branch", "") for w in worktrees)

    # Cleanup stale worktrees
    cleaned = manager.cleanup_stale_worktrees()

    # Should have cleaned up the stale worktree
    assert len(cleaned) > 0
    assert any("worker-1-test-123" in path for path in cleaned)

    # Worktree should no longer be tracked
    worktrees = manager.list_worktrees()
    assert not any("task-test-123" in w.get("branch", "") for w in worktrees)


def test_custom_worktrees_dir(git_repo):
    """Test using a custom worktrees directory."""
    manager = WorktreeManager(repo_root=git_repo, worktrees_dir="custom_dir")

    worktree_path = manager.create_worktree("worker-1", "test-123")

    # Check worktree was created in custom directory
    assert worktree_path == git_repo / "custom_dir" / "worker-1-test-123"
    assert worktree_path.exists()
