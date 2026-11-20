"""The ``cultural-events-rag config`` commands: ``show``."""

import argparse

from pydantic import SecretStr

from cultural_events_rag.settings import Settings, get_settings


def _shown(value: object) -> str:
    """A value as ``config show`` prints it: a secret only says whether it is
    set."""
    if isinstance(value, SecretStr):
        return "set" if value.get_secret_value() else "not set"
    return "not set" if value is None else str(value)


def lines(settings: Settings) -> list[str]:
    """One line per setting: the variable that sets it, then its value."""
    names = [name.upper() for name in type(settings).model_fields]
    width = max(len(name) for name in names)
    return [
        f"{name:<{width}}  {_shown(getattr(settings, name.lower()))}" for name in names
    ]


def _show(args: argparse.Namespace) -> int:
    for line in lines(get_settings()):
        print(line)
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag config`` to the cultural-events-rag command."""
    config = commands.add_parser("config", help="the settings of the application")
    steps = config.add_subparsers(dest="step", required=True)
    show = steps.add_parser("show", help="print the active settings, secrets masked")
    show.set_defaults(run=_show)
