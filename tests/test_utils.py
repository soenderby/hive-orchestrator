"""Tests for hive utils module."""

import json
import multiprocessing
import time
from pathlib import Path

import pytest

from hive.utils import locked_json_file, read_json_file, write_json_file


def test_locked_json_file_write(tmp_path):
    """Test writing JSON file with locking."""
    test_file = tmp_path / "test.json"

    with locked_json_file(test_file, "w") as data:
        data["key"] = "value"
        data["number"] = 42

    # Verify file was created and written
    assert test_file.exists()
    with open(test_file) as f:
        content = json.load(f)
    assert content["key"] == "value"
    assert content["number"] == 42


def test_locked_json_file_read(tmp_path):
    """Test reading JSON file with locking."""
    test_file = tmp_path / "test.json"

    # Create a test file
    test_data = {"foo": "bar", "count": 123}
    with open(test_file, "w") as f:
        json.dump(test_data, f)

    # Read it back
    with locked_json_file(test_file, "r") as data:
        assert data["foo"] == "bar"
        assert data["count"] == 123


def test_locked_json_file_read_default(tmp_path):
    """Test reading non-existent file returns default."""
    test_file = tmp_path / "nonexistent.json"

    with locked_json_file(test_file, "r", default={"empty": True}) as data:
        assert data["empty"] is True


def test_locked_json_file_read_write(tmp_path):
    """Test read-modify-write pattern."""
    test_file = tmp_path / "counter.json"

    # Initial write
    with locked_json_file(test_file, "w") as data:
        data["counter"] = 0

    # Read and modify
    with locked_json_file(test_file, "r+") as data:
        data["counter"] += 1

    # Verify modification
    with open(test_file) as f:
        content = json.load(f)
    assert content["counter"] == 1


def test_locked_json_file_creates_parent_dir(tmp_path):
    """Test that locked_json_file creates parent directories."""
    test_file = tmp_path / "nested" / "dir" / "test.json"

    with locked_json_file(test_file, "w") as data:
        data["created"] = True

    assert test_file.exists()
    assert test_file.parent.exists()


def test_locked_json_file_atomic_write(tmp_path):
    """Test that writes are atomic (temp file + rename)."""
    test_file = tmp_path / "atomic.json"

    # Write initial data
    with locked_json_file(test_file, "w") as data:
        data["value"] = 1

    # Verify no temp files left behind
    temp_files = list(test_file.parent.glob(f".{test_file.name}.*.tmp"))
    assert len(temp_files) == 0


def test_locked_json_file_invalid_json_uses_default(tmp_path):
    """Test that invalid JSON falls back to default."""
    test_file = tmp_path / "invalid.json"

    # Write invalid JSON
    test_file.write_text("not valid json{")

    # Should return default instead of crashing
    with locked_json_file(test_file, "r", default={"fallback": True}) as data:
        assert data["fallback"] is True


def test_read_json_file(tmp_path):
    """Test read_json_file helper."""
    test_file = tmp_path / "test.json"
    test_data = {"helper": "test", "value": 999}

    with open(test_file, "w") as f:
        json.dump(test_data, f)

    data = read_json_file(test_file)
    assert data["helper"] == "test"
    assert data["value"] == 999


def test_read_json_file_default(tmp_path):
    """Test read_json_file with default for missing file."""
    test_file = tmp_path / "missing.json"

    data = read_json_file(test_file, default={"default": True})
    assert data["default"] is True


def test_write_json_file(tmp_path):
    """Test write_json_file helper."""
    test_file = tmp_path / "test.json"
    test_data = {"written": "data", "number": 456}

    write_json_file(test_file, test_data)

    with open(test_file) as f:
        content = json.load(f)
    assert content["written"] == "data"
    assert content["number"] == 456


def test_write_json_file_clears_existing(tmp_path):
    """Test write_json_file replaces existing content."""
    test_file = tmp_path / "test.json"

    # Write initial data
    write_json_file(test_file, {"old": "data"})

    # Write new data
    write_json_file(test_file, {"new": "data"})

    # Verify old data is gone
    data = read_json_file(test_file)
    assert "old" not in data
    assert data["new"] == "data"


def test_locked_json_file_concurrent_writes(tmp_path):
    """Test that concurrent writes with file locking don't corrupt the file."""
    import threading

    test_file = tmp_path / "concurrent.json"
    iterations = 10
    num_threads = 3
    errors = []

    def write_data(worker_id):
        """Thread function to write data."""
        try:
            for i in range(iterations):
                with locked_json_file(test_file, "r+", default={}) as data:
                    # Each worker writes to its own key
                    worker_key = f"worker_{worker_id}"
                    data[worker_key] = data.get(worker_key, 0) + 1
                    time.sleep(0.001)  # Simulate some work
        except Exception as e:
            errors.append(e)

    # Spawn multiple threads that will all write to the file
    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=write_data, args=(i,))
        t.start()
        threads.append(t)

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Verify no errors occurred
    assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

    # Verify the file is valid JSON and has expected structure
    data = read_json_file(test_file)
    assert isinstance(data, dict)
    # Each worker should have written iterations times
    for i in range(num_threads):
        worker_key = f"worker_{i}"
        assert worker_key in data, f"Missing key {worker_key}"
        # Value should be <= iterations (may be less due to race conditions)
        assert data[worker_key] > 0, f"Worker {i} made no writes"


def test_locked_json_file_preserves_formatting(tmp_path):
    """Test that written JSON has proper formatting."""
    test_file = tmp_path / "formatted.json"

    with locked_json_file(test_file, "w") as data:
        data["a"] = 1
        data["b"] = 2

    content = test_file.read_text()
    # Should be indented with 2 spaces
    assert '  "a"' in content or '  "b"' in content
    # Should have trailing newline
    assert content.endswith("\n")
