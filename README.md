# cultural-events-rag

[![CI](https://github.com/pstcricq/cultural-events-rag/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pstcricq/cultural-events-rag/actions/workflows/ci.yml) [![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org) [![uv](https://img.shields.io/badge/uv-0.12.5-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![License MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

RAG assistant recommending cultural events from [Open Agenda](https://openagenda.com).

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/) 0.12.5
- make

## Quick start

```bash
make install
```

`make install` sets up the locked environment in `.venv`, the `cultural-events-rag` command and the git hooks. `make help` lists every target, `uv run cultural-events-rag --help` every command.

## Configuration

```bash
cp .env.example .env
make config
```

The settings are what an environment sets: its secrets, where its services are, what its machine and its plans allow. They come from the environment, then from `.env`, then from their defaults; `.env.example` lists them all. `.env` holds the API keys and is never committed. `make config` (`cultural-events-rag config show`) prints the active settings, a key only shown as set or not.

## CI

GitHub Actions runs one job per make target of the same name: `lint`, `typecheck`, `pre-commit`, `test-unit` and `coverage`, the coverage of each file written in the summary of the run. `make ci` runs every check of the CI on this machine. The CI needs no secret: each test sets its own settings. The packages of uv and the hooks of pre-commit are cached between runs; a new push stops the run still going on the same branch.

## Test

```bash
make test-unit
make coverage
```

`make test-unit` runs the tests that need only the repository, also before each `git push`. `make coverage` runs them and measures the lines of the package they run: it lists those left out, and fails below 95%. `make lint` checks the Python, `make format` fixes what it can, `make typecheck` checks the types, `make pre-commit` runs every hook on every file.

## Licence

The code, under MIT: see [LICENSE](LICENSE).
