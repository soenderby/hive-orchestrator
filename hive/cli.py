"""Main CLI entry point for Hive."""

import click
from hive.commands import daemon, init, merge, plan, status, task, work


@click.group()
@click.version_option()
def main():
    """Hive: A lightweight orchestrator for coordinating LLM coding agents."""
    pass


main.add_command(daemon.daemon_cmd)
main.add_command(init.init_cmd)
main.add_command(merge.merge_cmd)
main.add_command(merge.sync_cmd)
main.add_command(plan.plan_cmd)
main.add_command(status.status_cmd)
main.add_command(task.task_cmd)
main.add_command(work.work_cmd)


if __name__ == "__main__":
    main()
