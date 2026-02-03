"""Daemon command for monitoring Hive workers."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import click

from hive.utils import locked_json_file


DAEMON_PID_FILE = ".hive/daemon.pid"
DAEMON_LOG_FILE = ".hive/daemon.log"
DEFAULT_CHECK_INTERVAL = 60  # Check every 60 seconds
DEFAULT_STUCK_THRESHOLD = 300  # 5 minutes of no activity


def get_daemon_pid() -> Optional[int]:
    """Get the PID of the running daemon, if any."""
    pid_file = Path(DAEMON_PID_FILE)
    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        # Check if process is actually running
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return pid
        except OSError:
            # Process not running, clean up stale PID file
            pid_file.unlink()
            return None
    except (ValueError, FileNotFoundError):
        return None


def is_daemon_running() -> bool:
    """Check if the daemon is currently running."""
    return get_daemon_pid() is not None


def write_daemon_pid(pid: int):
    """Write the daemon PID to the PID file."""
    pid_file = Path(DAEMON_PID_FILE)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))


def remove_daemon_pid():
    """Remove the daemon PID file."""
    pid_file = Path(DAEMON_PID_FILE)
    if pid_file.exists():
        pid_file.unlink()


def log_message(message: str):
    """Log a message to the daemon log file."""
    log_file = Path(DAEMON_LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat()
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def get_workers() -> list[dict]:
    """Get the list of registered workers."""
    workers_path = Path(".hive/workers.json")
    if not workers_path.exists():
        return []

    with locked_json_file(workers_path, "r", default={"workers": []}) as data:
        return data.get("workers", [])


def check_stuck_workers(stuck_threshold: int) -> list[dict]:
    """Check for stuck workers (no activity for stuck_threshold seconds).

    Returns:
        List of stuck worker entries with additional 'stuck_duration' field
    """
    workers = get_workers()
    stuck_workers = []
    now = datetime.now()

    for worker in workers:
        last_activity_str = worker.get("last_activity")
        if not last_activity_str:
            continue

        try:
            last_activity = datetime.fromisoformat(last_activity_str)
            duration = (now - last_activity).total_seconds()

            if duration >= stuck_threshold:
                worker_copy = worker.copy()
                worker_copy["stuck_duration"] = int(duration)
                stuck_workers.append(worker_copy)
        except ValueError:
            # Invalid datetime format, skip
            continue

    return stuck_workers


def send_notification(title: str, message: str):
    """Send a desktop notification (best-effort, fails silently)."""
    try:
        # Try notify-send (Linux)
        subprocess.run(
            ["notify-send", title, message],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # notify-send not available or timed out, that's okay
        pass


def daemon_loop(check_interval: int, stuck_threshold: int, notify: bool):
    """Main daemon loop that monitors workers."""
    log_message(f"Daemon started (check_interval={check_interval}s, stuck_threshold={stuck_threshold}s, notify={notify})")

    while True:
        try:
            stuck_workers = check_stuck_workers(stuck_threshold)

            if stuck_workers:
                for worker in stuck_workers:
                    worker_id = worker.get("id", "unknown")
                    task_id = worker.get("current_task", "unknown")
                    duration = worker.get("stuck_duration", 0)

                    log_message(
                        f"Worker {worker_id} stuck on task {task_id} for {duration}s "
                        f"(threshold: {stuck_threshold}s)"
                    )

                    if notify:
                        send_notification(
                            "Hive Worker Stuck",
                            f"Worker {worker_id} stuck on {task_id} for {duration // 60} minutes"
                        )

            time.sleep(check_interval)

        except KeyboardInterrupt:
            log_message("Daemon stopped by interrupt")
            break
        except Exception as e:
            log_message(f"Error in daemon loop: {e}")
            time.sleep(check_interval)


@click.group(name="daemon")
def daemon_cmd():
    """Monitor and manage the Hive daemon."""
    pass


@daemon_cmd.command(name="start")
@click.option("--check-interval", default=DEFAULT_CHECK_INTERVAL, help="Check interval in seconds (default: 60)")
@click.option("--stuck-threshold", default=DEFAULT_STUCK_THRESHOLD, help="Stuck threshold in seconds (default: 300)")
@click.option("--notify", is_flag=True, help="Enable desktop notifications for stuck workers")
@click.option("--foreground", is_flag=True, help="Run in foreground (don't daemonize)")
def start_cmd(check_interval: int, stuck_threshold: int, notify: bool, foreground: bool):
    """Start the Hive daemon."""
    # Check if .hive directory exists
    hive_dir = Path(".hive")
    if not hive_dir.exists():
        click.echo("✗ Hive not initialized (.hive/ not found)")
        click.echo("  Run 'hive init' first")
        sys.exit(1)

    # Check if daemon is already running
    if is_daemon_running():
        pid = get_daemon_pid()
        click.echo(f"✗ Daemon already running (PID: {pid})")
        sys.exit(1)

    if foreground:
        # Run in foreground
        click.echo("Starting daemon in foreground (Ctrl+C to stop)...")
        write_daemon_pid(os.getpid())
        try:
            daemon_loop(check_interval, stuck_threshold, notify)
        finally:
            remove_daemon_pid()
    else:
        # Daemonize
        pid = os.fork()
        if pid > 0:
            # Parent process
            click.echo(f"✓ Daemon started (PID: {pid})")
            click.echo(f"  Check interval: {check_interval}s")
            click.echo(f"  Stuck threshold: {stuck_threshold}s")
            click.echo(f"  Notifications: {'enabled' if notify else 'disabled'}")
            sys.exit(0)

        # Child process
        # Detach from parent
        os.setsid()

        # Second fork to prevent zombie
        pid = os.fork()
        if pid > 0:
            sys.exit(0)

        # Write PID file
        write_daemon_pid(os.getpid())

        # Redirect stdout/stderr to log file
        log_file = Path(DAEMON_LOG_FILE)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        sys.stdout.flush()
        sys.stderr.flush()

        with open(log_file, "a") as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())

        # Close stdin
        with open(os.devnull, "r") as f:
            os.dup2(f.fileno(), sys.stdin.fileno())

        # Run daemon loop
        try:
            daemon_loop(check_interval, stuck_threshold, notify)
        finally:
            remove_daemon_pid()


@daemon_cmd.command(name="stop")
def stop_cmd():
    """Stop the Hive daemon."""
    pid = get_daemon_pid()
    if not pid:
        click.echo("✗ Daemon not running")
        sys.exit(1)

    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"✓ Daemon stopped (PID: {pid})")
        remove_daemon_pid()
    except OSError as e:
        click.echo(f"✗ Failed to stop daemon: {e}")
        sys.exit(1)


@daemon_cmd.command(name="status")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def status_cmd(output_json: bool):
    """Show daemon status."""
    pid = get_daemon_pid()
    is_running = pid is not None

    if output_json:
        status = {
            "running": is_running,
            "pid": pid,
        }

        if is_running:
            # Include stuck workers in status
            stuck_workers = check_stuck_workers(DEFAULT_STUCK_THRESHOLD)
            status["stuck_workers"] = stuck_workers

        click.echo(json.dumps(status, indent=2))
    else:
        if is_running:
            click.echo(f"✓ Daemon running (PID: {pid})")

            # Check for stuck workers
            stuck_workers = check_stuck_workers(DEFAULT_STUCK_THRESHOLD)
            if stuck_workers:
                click.echo(f"\n⚠ {len(stuck_workers)} stuck worker(s):")
                for worker in stuck_workers:
                    worker_id = worker.get("id", "unknown")
                    task_id = worker.get("current_task", "unknown")
                    duration = worker.get("stuck_duration", 0)
                    minutes = duration // 60
                    click.echo(f"  - {worker_id}: {task_id} ({minutes} minutes)")
            else:
                click.echo("  No stuck workers")
        else:
            click.echo("✗ Daemon not running")


@daemon_cmd.command(name="logs")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", default=20, help="Number of lines to show (default: 20)")
def logs_cmd(follow: bool, lines: int):
    """Show daemon logs."""
    log_file = Path(DAEMON_LOG_FILE)

    if not log_file.exists():
        click.echo("No daemon logs found")
        return

    if follow:
        # Use tail -f to follow logs
        try:
            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            pass
    else:
        # Show last N lines
        try:
            result = subprocess.run(
                ["tail", f"-n{lines}", str(log_file)],
                capture_output=True,
                text=True,
            )
            click.echo(result.stdout)
        except FileNotFoundError:
            # tail not available, read file manually
            with open(log_file) as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    click.echo(line.rstrip())
