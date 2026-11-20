"""The ``cultural-events-rag`` command, a command or a group of commands per
area. The exit code is 0 when the command succeeded, 1 otherwise.
"""

import argparse

from cultural_events_rag.cli import config, documents, fetch, process

GROUPS = (config, fetch, process, documents)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cultural-events-rag",
        description="RAG assistant recommending cultural events.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for group in GROUPS:
        group.add_commands(commands)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    code: int = args.run(args)
    return code
