# Development

## Layout

```text
src/cultural_events_rag/
├── assistant.py      the served configuration, put together
├── settings.py       the settings, from the environment
├── constants.py      what is tied to the city
├── models.py         Agenda, Event
├── mistral.py        the Mistral models, the pacer
├── elastic.py        the Elasticsearch client
├── retry.py          the retry policy
├── collection/       sources, fetch, parsing, cleaning, process
├── indexing/         formatting, documents, chunking, store, build
├── retrieval/        query analysis, filters, search, rerank
├── generation/       prompt, answer
├── evaluation/       dataset, benchmark, retrieval, generation, judge, reports
├── api/              schemas, service, app
├── ui/               client, text, app
└── cli/              one module per command
tests/
├── unit/             only the repository
├── integration/      a real Elasticsearch, started by testcontainers
└── smoke/            the services of docker compose, from outside
```

## Conventions

- **Languages.** The code, its comments, the logs, the documentation and the commits are in English; the data, the prompts and the answers in French, the language of the events and of the users.
- **Comments and docstrings** say what the code does, simply; the reasons behind the choices are in this documentation. A function docstring starts with a verb ("Return ...", "Build ..."), a module or class docstring with a noun.
- **Settings** have no default in the code (see [Configuration](operations/configuration.md)).
- **Steps** depend only on the steps before them (see [Architecture](guide/architecture.md)).
- **Commands.** Each `cultural-events-rag` command has a make target of the same name; `ARGS` passes its options, `Q` the question.
- **Commits.** The history is built step by step, one step of the pipeline per commit, each commit leaving the repository green: a later step does not change an earlier one.

## Quality

| | |
|---|---|
| `make lint` | ruff check and ruff format, default rules |
| `make format` | fix what ruff can |
| `make typecheck` | mypy strict on `src/` and `tests/`, with the pydantic plugin |
| `make pre-commit` | every git hook on every file: ruff, end of files, whitespace, YAML, large files, private keys, secrets (gitleaks) |
| `make ci` | lint, types, hooks, coverage and the documentation, as the CI runs them |

The hooks run on each commit; the unit tests run before each push.

## Tests

| | Needs | |
|---|---|---|
| `make test-unit` | the repository | every module, its services replaced by fakes |
| `make test-integration` | Docker | the index, the search, the commands, the API and the evaluation against a real Elasticsearch |
| `make test-smoke` | `make docker-up` | the services as a user reaches them |
| `make coverage` | Docker | unit and integration tests, failing under 95% of the lines |

No test calls Mistral nor Open Agenda: the embedding model, the chat model, the reranker and the HTTP sources are replaced by fakes. No test reads the environment of the machine: each one sets the settings it needs.

The integration tests start an Elasticsearch of `ELASTIC_VERSION` with testcontainers, once per session, on a free port, with security on; each test has an alias of its own. The container is removed at the end, even when the tests are killed. Without Docker the integration tests are skipped, under CI they fail.

## Documentation

```bash
make docs-serve
make docs-build
```

The site is built by [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) from `docs/`, the code reference by [mkdocstrings](https://mkdocstrings.github.io) from the docstrings. `make docs-serve` serves it on http://127.0.0.1:8008, reloaded on save; `make docs-build` builds it into `site/`, every warning an error. The CI publishes it on GitHub Pages from `main`.
