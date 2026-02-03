"""Configuration loading for Hive orchestrator.

Provides typed configuration dataclass and loading from .hive/config.toml.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python


@dataclass
class HiveConfig:
    """Hive configuration settings.

    All fields have sensible defaults. Values are loaded from .hive/config.toml
    if present, falling back to defaults if the file doesn't exist or fields
    are missing.
    """

    # Hive metadata
    version: str = "0.1.0"

    # Worker settings
    spawn_grace_period_seconds: int = 30
    max_parallel_workers: int = 1
    poll_interval: int = 5
    task_timeout: int = 3600

    # Worktree settings
    worktrees_base_dir: str = "worktrees"

    # Agent settings
    agent_command: str = "claude-code"
    agent_shell: str = "bash"

    # Branch settings
    default_branch: str = "main"


def load_config(config_path: Optional[Path] = None) -> HiveConfig:
    """Load Hive configuration from .hive/config.toml.

    Args:
        config_path: Path to config.toml. If None, uses .hive/config.toml in current directory.

    Returns:
        HiveConfig instance with values loaded from file, or defaults if file doesn't exist.

    Example:
        config = load_config()
        timeout = config.task_timeout
        agent = config.agent_command
    """
    if config_path is None:
        config_path = Path.cwd() / ".hive" / "config.toml"

    # If config doesn't exist, return defaults
    if not config_path.exists():
        return HiveConfig()

    # Load TOML file
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # Extract values from TOML sections with defaults
    hive_section = data.get("hive", {})
    workers_section = data.get("workers", {})
    worktrees_section = data.get("worktrees", {})
    agent_section = data.get("agent", {})
    branch_section = data.get("branch", {})

    return HiveConfig(
        # Hive metadata
        version=hive_section.get("version", "0.1.0"),
        # Worker settings
        spawn_grace_period_seconds=workers_section.get(
            "spawn_grace_period_seconds", 30
        ),
        max_parallel_workers=workers_section.get("max_parallel_workers", 1),
        poll_interval=workers_section.get("poll_interval", 5),
        task_timeout=workers_section.get("task_timeout", 3600),
        # Worktree settings
        worktrees_base_dir=worktrees_section.get("base_dir", "worktrees"),
        # Agent settings
        agent_command=agent_section.get("command", "claude-code"),
        agent_shell=agent_section.get("shell", "bash"),
        # Branch settings
        default_branch=branch_section.get("default_branch", "main"),
    )
