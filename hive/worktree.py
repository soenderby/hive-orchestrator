"""Git worktree management for Hive workers."""

import subprocess
from pathlib import Path
from typing import Optional, List
import shutil


class WorktreeError(Exception):
    """Base exception for worktree operations."""
    pass


class WorktreeManager:
    """Manages git worktrees for isolated task execution."""

    def __init__(self, repo_root: Optional[Path] = None, worktrees_dir: str = "worktrees"):
        """Initialize the worktree manager.

        Args:
            repo_root: Root of the git repository (defaults to current directory)
            worktrees_dir: Directory where worktrees are created (relative to repo_root)
        """
        self.repo_root = repo_root or Path.cwd()
        self.worktrees_dir = self.repo_root / worktrees_dir

    def create_worktree(
        self,
        worker_id: str,
        task_id: str,
        base_branch: str = "main",
        force: bool = False,
    ) -> Path:
        """Create a new worktree for a task.

        Args:
            worker_id: Unique worker identifier (e.g., "worker-1")
            task_id: Task identifier from Beads (e.g., "hive-abc")
            base_branch: Branch to create the worktree from (default: "main")
            force: If True, remove existing worktree first

        Returns:
            Path to the created worktree

        Raises:
            WorktreeError: If worktree creation fails
        """
        worktree_name = f"{worker_id}-{task_id}"
        worktree_path = self.worktrees_dir / worktree_name
        branch_name = f"task-{task_id}"

        # Check if worktree already exists
        if worktree_path.exists():
            if force:
                self.remove_worktree(worker_id, task_id, force=True)
            else:
                raise WorktreeError(
                    f"Worktree already exists: {worktree_path}\n"
                    f"Use force=True to remove it first"
                )

        # Ensure worktrees directory exists
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

        # Create the worktree with a new branch
        try:
            subprocess.run(
                [
                    "git",
                    "worktree",
                    "add",
                    str(worktree_path),
                    "-b",
                    branch_name,
                    base_branch,
                ],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise WorktreeError(
                f"Failed to create worktree: {e.stderr}"
            ) from e

        return worktree_path

    def remove_worktree(
        self,
        worker_id: str,
        task_id: str,
        force: bool = False,
    ) -> None:
        """Remove a worktree and its associated branch.

        Args:
            worker_id: Unique worker identifier
            task_id: Task identifier from Beads
            force: If True, force removal even if worktree has uncommitted changes

        Raises:
            WorktreeError: If worktree removal fails
        """
        worktree_name = f"{worker_id}-{task_id}"
        worktree_path = self.worktrees_dir / worktree_name
        branch_name = f"task-{task_id}"

        # Check if worktree exists
        if not worktree_path.exists():
            # Worktree might be registered in git but directory deleted
            # Try to remove from git's tracking anyway
            try:
                subprocess.run(
                    ["git", "worktree", "remove", str(worktree_path), "--force"],
                    cwd=self.repo_root,
                    check=False,  # Don't fail if it doesn't exist
                    capture_output=True,
                    text=True,
                )
            except Exception:
                pass  # Ignore errors
            return

        # Remove the worktree
        try:
            cmd = ["git", "worktree", "remove", str(worktree_path)]
            if force:
                cmd.append("--force")

            subprocess.run(
                cmd,
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            # If git worktree remove fails, try manual cleanup
            if force:
                try:
                    # Remove directory manually
                    shutil.rmtree(worktree_path)
                    # Prune git's worktree list
                    subprocess.run(
                        ["git", "worktree", "prune"],
                        cwd=self.repo_root,
                        check=False,
                        capture_output=True,
                    )
                except Exception as cleanup_error:
                    raise WorktreeError(
                        f"Failed to remove worktree and cleanup failed: {cleanup_error}"
                    ) from e
            else:
                raise WorktreeError(
                    f"Failed to remove worktree: {e.stderr}\n"
                    f"Try with force=True to force removal"
                ) from e

        # Delete the branch if it exists
        try:
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            # Branch might not exist or already deleted, ignore
            pass

    def list_worktrees(self) -> List[dict]:
        """List all git worktrees.

        Returns:
            List of dictionaries with worktree info (path, branch, etc.)
        """
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )

            worktrees = []
            current_worktree = {}

            for line in result.stdout.strip().split("\n"):
                if not line:
                    if current_worktree:
                        worktrees.append(current_worktree)
                        current_worktree = {}
                    continue

                if line.startswith("worktree "):
                    current_worktree["path"] = line.split(" ", 1)[1]
                elif line.startswith("branch "):
                    current_worktree["branch"] = line.split(" ", 1)[1]
                elif line.startswith("HEAD "):
                    current_worktree["head"] = line.split(" ", 1)[1]
                elif line == "bare":
                    current_worktree["bare"] = True
                elif line == "detached":
                    current_worktree["detached"] = True

            # Add last worktree if exists
            if current_worktree:
                worktrees.append(current_worktree)

            return worktrees

        except subprocess.CalledProcessError as e:
            raise WorktreeError(f"Failed to list worktrees: {e.stderr}") from e

    def cleanup_stale_worktrees(self, force: bool = True) -> List[str]:
        """Clean up stale worktrees (from crashes, etc.).

        A worktree is considered stale if:
        - The directory doesn't exist but git still tracks it
        - It's in the worktrees/ directory but not the main worktree

        Args:
            force: If True, force removal of worktrees with uncommitted changes

        Returns:
            List of cleaned up worktree paths
        """
        cleaned = []

        try:
            # Get all worktrees tracked by git
            worktrees = self.list_worktrees()

            for wt in worktrees:
                wt_path = Path(wt["path"])

                # Skip the main worktree (repo root)
                if wt_path == self.repo_root:
                    continue

                # Check if this is in our worktrees directory
                try:
                    wt_path.relative_to(self.worktrees_dir)
                except ValueError:
                    # Not in our worktrees directory, skip
                    continue

                # Check if directory exists
                if not wt_path.exists():
                    # Stale worktree - remove it
                    try:
                        subprocess.run(
                            ["git", "worktree", "remove", str(wt_path), "--force"],
                            cwd=self.repo_root,
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        cleaned.append(str(wt_path))
                    except subprocess.CalledProcessError:
                        # Try pruning
                        subprocess.run(
                            ["git", "worktree", "prune"],
                            cwd=self.repo_root,
                            check=False,
                            capture_output=True,
                        )
                        cleaned.append(str(wt_path))

            # Also prune to clean up git's internal state
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.repo_root,
                check=False,
                capture_output=True,
            )

        except Exception as e:
            # Don't fail cleanup - just log and continue
            pass

        return cleaned

    def worktree_exists(self, worker_id: str, task_id: str) -> bool:
        """Check if a worktree exists.

        Args:
            worker_id: Unique worker identifier
            task_id: Task identifier from Beads

        Returns:
            True if worktree exists, False otherwise
        """
        worktree_name = f"{worker_id}-{task_id}"
        worktree_path = self.worktrees_dir / worktree_name
        return worktree_path.exists()
