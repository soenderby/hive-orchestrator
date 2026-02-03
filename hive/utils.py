"""Utility functions for Hive orchestrator.

Provides file locking and atomic write operations for shared resources.
"""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict

# Try to import fcntl for Unix-like systems
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


@contextmanager
def locked_json_file(path: Path, mode: str = "r", default: Any = None):
    """Context manager for reading/writing JSON files with file locking.

    Provides atomic writes and file locking to prevent race conditions when
    multiple processes access the same JSON file.

    Args:
        path: Path to the JSON file
        mode: File mode - "r" for read, "w" for write, "r+" for read-write
        default: Default value to return if file doesn't exist (read mode only)

    Yields:
        For read mode: The parsed JSON data
        For write mode: A dict to populate with data to write

    Example:
        # Read JSON file
        with locked_json_file(path, "r", default={}) as data:
            workers = data.get("workers", [])

        # Write JSON file
        with locked_json_file(path, "w") as data:
            data["workers"] = workers
            data["last_updated"] = timestamp

        # Read and modify
        with locked_json_file(path, "r+", default={}) as data:
            data["counter"] = data.get("counter", 0) + 1
    """
    path = Path(path)
    write_mode = "w" in mode or "+" in mode

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # For read-only mode with non-existent file, return default
    if mode == "r" and not path.exists():
        if default is not None:
            yield default
            return
        else:
            raise FileNotFoundError(f"File not found: {path}")

    # Open file and acquire lock
    file_mode = "r+" if "+" in mode else ("w+" if write_mode else "r")

    # Create file if it doesn't exist (for write modes)
    if write_mode and not path.exists():
        path.write_text("{}")

    with open(path, file_mode) as f:
        # Acquire exclusive lock for write, shared lock for read
        if HAS_FCNTL:
            lock_type = fcntl.LOCK_EX if write_mode else fcntl.LOCK_SH
            fcntl.flock(f.fileno(), lock_type)

        try:
            # Read existing data
            f.seek(0)
            content = f.read()
            if content.strip():
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = default if default is not None else {}
            else:
                data = default if default is not None else {}

            # For read-only mode, yield data and we're done
            if not write_mode:
                yield data
                return

            # For write modes, yield mutable dict
            if not isinstance(data, dict):
                data = {}

            yield data

            # Write data back atomically
            if write_mode:
                # Use atomic write pattern: write to temp file, then rename
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
                )

                try:
                    with os.fdopen(temp_fd, "w") as temp_f:
                        json.dump(data, temp_f, indent=2)
                        temp_f.write("\n")  # Add trailing newline
                        temp_f.flush()
                        os.fsync(temp_f.fileno())  # Ensure written to disk

                    # Atomic rename
                    os.replace(temp_path, path)
                except Exception:
                    # Clean up temp file on error
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                    raise

        finally:
            # Release lock
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_json_file(path: Path, default: Any = None) -> Any:
    """Read a JSON file with locking.

    Args:
        path: Path to JSON file
        default: Default value if file doesn't exist

    Returns:
        Parsed JSON data or default value
    """
    with locked_json_file(path, "r", default=default) as data:
        return data


def write_json_file(path: Path, data: Dict[str, Any]) -> None:
    """Write a JSON file atomically with locking.

    Args:
        path: Path to JSON file
        data: Data to write
    """
    with locked_json_file(path, "w") as file_data:
        file_data.clear()
        file_data.update(data)
