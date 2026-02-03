"""Tests for hive config module."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from hive.config import HiveConfig, get_default_branch, load_config

try:
    import tomli_w
except ImportError:
    import tomllib as tomli_w


def test_hive_config_defaults():
    """Test HiveConfig has correct default values."""
    config = HiveConfig()

    # Hive metadata
    assert config.version == "0.1.0"

    # Worker settings
    assert config.spawn_grace_period_seconds == 30
    assert config.max_parallel_workers == 1
    assert config.poll_interval == 5
    assert config.task_timeout == 3600

    # Worktree settings
    assert config.worktrees_base_dir == "worktrees"

    # Agent settings
    assert config.agent_command == "claude-code"
    assert config.agent_shell == "bash"

    # Branch settings
    assert config.default_branch == "main"


def test_load_config_missing_file(tmp_path):
    """Test load_config returns defaults when file doesn't exist."""
    config_path = tmp_path / "nonexistent.toml"
    config = load_config(config_path)

    assert isinstance(config, HiveConfig)
    assert config.version == "0.1.0"
    assert config.default_branch == "main"


def test_load_config_from_file(tmp_path):
    """Test load_config reads values from config.toml."""
    config_path = tmp_path / "config.toml"
    config_data = {
        "hive": {"version": "1.0.0"},
        "workers": {
            "spawn_grace_period_seconds": 60,
            "max_parallel_workers": 4,
            "poll_interval": 10,
            "task_timeout": 7200,
        },
        "worktrees": {"base_dir": "custom_worktrees"},
        "agent": {"command": "custom-agent", "shell": "zsh"},
        "branch": {"default_branch": "develop"},
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    config = load_config(config_path)

    assert config.version == "1.0.0"
    assert config.spawn_grace_period_seconds == 60
    assert config.max_parallel_workers == 4
    assert config.poll_interval == 10
    assert config.task_timeout == 7200
    assert config.worktrees_base_dir == "custom_worktrees"
    assert config.agent_command == "custom-agent"
    assert config.agent_shell == "zsh"
    assert config.default_branch == "develop"


def test_load_config_partial_file(tmp_path):
    """Test load_config uses defaults for missing sections."""
    config_path = tmp_path / "config.toml"
    config_data = {
        "workers": {"max_parallel_workers": 8},
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    config = load_config(config_path)

    # Specified value
    assert config.max_parallel_workers == 8

    # Default values
    assert config.version == "0.1.0"
    assert config.spawn_grace_period_seconds == 30
    assert config.default_branch == "main"


def test_load_config_empty_sections(tmp_path):
    """Test load_config handles empty sections gracefully."""
    config_path = tmp_path / "config.toml"
    config_data = {
        "hive": {},
        "workers": {},
        "worktrees": {},
        "agent": {},
        "branch": {},
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    config = load_config(config_path)

    # All should be defaults
    assert config.version == "0.1.0"
    assert config.spawn_grace_period_seconds == 30
    assert config.default_branch == "main"


def test_get_default_branch_from_config(tmp_path):
    """Test get_default_branch reads from config.toml."""
    hive_dir = tmp_path / ".hive"
    hive_dir.mkdir()
    config_path = hive_dir / "config.toml"

    config_data = {"branch": {"default_branch": "master"}}

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    branch = get_default_branch(config_path)
    assert branch == "master"


def test_get_default_branch_from_git(tmp_path):
    """Test get_default_branch detects from git remote HEAD."""
    # Create a config with empty default_branch to trigger git detection
    hive_dir = tmp_path / ".hive"
    hive_dir.mkdir()
    config_path = hive_dir / "config.toml"

    config_data = {"branch": {"default_branch": ""}}

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    # Mock git command to return a branch
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "refs/remotes/origin/develop\n"
        mock_run.return_value.returncode = 0

        branch = get_default_branch(config_path)
        assert branch == "develop"

        # Verify git command was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["git", "symbolic-ref", "refs/remotes/origin/HEAD"]


def test_get_default_branch_fallback_to_main(tmp_path):
    """Test get_default_branch falls back to 'main' when git fails."""
    hive_dir = tmp_path / ".hive"
    hive_dir.mkdir()
    config_path = hive_dir / "config.toml"

    config_data = {"hive": {"version": "0.1.0"}}

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    # Mock git command to fail
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        branch = get_default_branch(config_path)
        assert branch == "main"


def test_get_default_branch_no_config_file():
    """Test get_default_branch works without config file."""
    # Mock git to fail so we get the fallback
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        branch = get_default_branch(Path("/nonexistent/config.toml"))
        assert branch == "main"
