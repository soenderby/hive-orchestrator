"""Tests for hive init command."""

import json
import os
from pathlib import Path
from click.testing import CliRunner
from hive.cli import main

try:
    import tomli
except ImportError:
    import tomllib as tomli


def test_init_creates_structure(tmp_path):
    """Test that hive init creates the required directory structure."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create .beads directory (prerequisite)
        beads_dir = Path(".beads")
        beads_dir.mkdir()

        # Run hive init
        result = runner.invoke(main, ["init"])

        # Check command succeeded
        assert result.exit_code == 0
        assert "✓ Created .hive/" in result.output
        assert "✓ Created .hive/config.toml" in result.output
        assert "✓ Created .hive/workers.json" in result.output
        assert "✓ Created .hive/plan.md" in result.output
        assert "✓ Created worktrees/" in result.output
        assert "✓ Beads already initialized" in result.output

        # Verify directories exist
        assert Path(".hive").is_dir()
        assert Path("worktrees").is_dir()

        # Verify files exist
        assert Path(".hive/config.toml").is_file()
        assert Path(".hive/workers.json").is_file()
        assert Path(".hive/plan.md").is_file()
        assert Path("worktrees/.gitignore").is_file()

        # Verify config.toml content
        with open(".hive/config.toml", "rb") as f:
            config = tomli.load(f)
            assert "hive" in config
            assert "workers" in config
            assert "worktrees" in config
            assert "agent" in config
            assert config["workers"]["spawn_grace_period_seconds"] == 30
            assert config["workers"]["max_parallel_workers"] == 1

        # Verify workers.json content
        with open(".hive/workers.json") as f:
            workers = json.load(f)
            assert "workers" in workers
            assert workers["workers"] == []
            assert "last_updated" in workers

        # Verify plan.md has content
        plan_content = Path(".hive/plan.md").read_text()
        assert "# Hive Plan" in plan_content
        assert "## Goal" in plan_content


def test_init_requires_beads(tmp_path):
    """Test that hive init fails if beads is not initialized."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Run hive init without .beads directory
        result = runner.invoke(main, ["init"])

        # Check command failed
        assert result.exit_code == 1
        assert "Beads not initialized" in result.output
        assert "Please run 'bd init' first" in result.output


def test_init_warns_if_already_initialized(tmp_path):
    """Test that hive init warns if already initialized."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create .beads directory
        beads_dir = Path(".beads")
        beads_dir.mkdir()

        # Run hive init first time
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0

        # Run hive init second time, abort
        result = runner.invoke(main, ["init"], input="n\n")
        assert "⚠ Hive already initialized" in result.output
        assert "Aborted" in result.output

        # Run hive init second time, confirm
        result = runner.invoke(main, ["init"], input="y\n")
        assert "⚠ Hive already initialized" in result.output
        assert result.exit_code == 0
