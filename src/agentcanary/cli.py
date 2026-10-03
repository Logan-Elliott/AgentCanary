"""Command line entry point."""

import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic canaries and local evidence")
    parser.add_argument("--version", action="version", version=f"agentcanary {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
