"""Main CLI entry point for Hive."""

import click
from hive.commands import init


@click.group()
@click.version_option()
def main():
    """Hive: A lightweight orchestrator for coordinating LLM coding agents."""
    pass


main.add_command(init.init_cmd)


if __name__ == "__main__":
    main()
