"""The files the package reads are found from the root of the repository."""

from cultural_events_rag import paths
from tests import ROOT


def test_the_root_is_the_root_of_the_repository() -> None:
    assert paths.ROOT == ROOT
    assert (paths.ROOT / "pyproject.toml").is_file()


def test_the_env_file_is_at_the_root() -> None:
    assert paths.ENV_FILE == ROOT / ".env"
