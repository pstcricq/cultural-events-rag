# cultural-events-rag

[![CI](https://github.com/pstcricq/cultural-events-rag/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pstcricq/cultural-events-rag/actions/workflows/ci.yml) [![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org) [![uv](https://img.shields.io/badge/uv-0.12.5-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![License MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

RAG assistant recommending cultural events from [Open Agenda](https://openagenda.com).

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/) 0.12.5
- make

## Quick start

```bash
make install
make models
```

`make install` sets up the locked environment in `.venv`, the `cultural-events-rag` command and the git hooks. `make models` (`cultural-events-rag models`) downloads once, into the cache of Hugging Face, the models run on this machine: the Mistral tokenizer (about 2 MB), that counts the tokens of each embedding request. Every other target runs Hugging Face offline (`HF_HUB_OFFLINE=1`): a model missing is reported, never downloaded on the way. `make help` lists every target, `uv run cultural-events-rag --help` every command.

## Configuration

```bash
cp .env.example .env
make config
```

The settings are what an environment sets: its secrets, where its services are, what its machine and its plans allow. They come from the environment, then from `.env`; none has a default in the code: `.env.example` lists them all, with their values. `.env` holds the API keys and is never committed. `make config` (`cultural-events-rag config show`) prints the active settings, a key only shown as set or not.

## Search engine

```bash
make docker-up
```

The index of the events lives in [Elasticsearch](https://www.elastic.co/elasticsearch), run by docker compose: one node, with the `elastic` user and `ELASTIC_PASSWORD` from `.env`, over plain HTTP. `compose.yaml` holds the services as they run in every environment, and writes none of the values an environment sets: it takes them from the environment, then from `.env`, and refuses to start without any of them, naming the one missing: the passwords and the version of every Elastic image `ELASTIC_VERSION`, all listed in `.env.example`. The ports are published on 127.0.0.1, this machine only. `make docker-up` starts the services and waits until they are healthy (`S=elasticsearch`: Elasticsearch alone); `make docker-down` stops them and keeps their data, `make docker-ps` shows their health, `make docker-logs` their logs, `make docker-reset` deletes their data: the only way to change `ELASTIC_PASSWORD`, read at the first start alone.

`make docker-up` also starts [Kibana](https://www.elastic.co/kibana), the web interface of Elasticsearch, on http://127.0.0.1:5601: sign in as `elastic` with `ELASTIC_PASSWORD`, then browse the index in Discover, or try queries in Dev Tools. Kibana reaches Elasticsearch as its built-in user `kibana_system`, with `KIBANA_PASSWORD` from `.env`; the application never goes through it.

## Events

```bash
make fetch
make process
```

`make fetch` (`cultural-events-rag fetch`) downloads the events of the cultural agendas of Toulouse, the upcoming ones first, then those of the last 365 days, into `data/raw/<source>.json`, as the API returns them. The source is the official [Open Agenda API](https://developers.openagenda.com/) with `OPENAGENDA_API_KEY`, the [OpenDataSoft dataset](https://public.opendatasoft.com/explore/dataset/evenements-publics-openagenda/) of the public agendas without. `MAX_EVENTS` in `.env` says how many: a number, a sample split between the agendas (200 is enough while developing), or `all`; it is required, a forgotten cap is not a choice. `ARGS="--max-events 200"` overrides it for one run.

`make process` (`cultural-events-rag process`) turns the raw events of that source into the events of the common format, in `data/processed/events.jsonl`: the fields kept, the HTML turned into text, whether the event is free read from its conditions, then the invalid events, those outside the city or finished before the period, and the duplicates dropped. The sessions of one activity, published as separate events, become one event. It calls no API: it can be run again on the same raw events.

## Index

```bash
make documents
make index
make status
```

`make documents` (`cultural-events-rag documents`) shows the documents the events of `data/processed/events.jsonl` make, as the index will store them: a summary of them all, or with `ARGS="--uid 123"` every document of one event. Each event gives one document per chunk of its description, up to `CHUNK_SIZE` characters (1000), the last `CHUNK_OVERLAP` (150) repeated at the start of the next. Every chunk starts with the header of the event, its title, dates in Paris time, place, price, audience, so that each one stays tied to its event. The metadata (dates in UTC, district, age, price) will filter the search.

`make index` (`cultural-events-rag index`) sends these documents to `mistral-embed` (`MISTRAL_API_KEY`) in batches of about 15k tokens, a batch retried on a rate limit or a server error, and writes them into Elasticsearch: each one with its text, analyzed in French for the lexical search (BM25), its vector, for the vector search (kNN, exact: the question is compared with every vector by cosine), and its metadata, as fields to filter on. Each build writes a new index, then moves the alias `events` (`ELASTICSEARCH_INDEX`) onto it once every event is in it, and deletes the one it served: a failed build leaves the served index as it was. The index records what it was built with, the embedding model, the chunking, the document format and the vector index type: `make status` (`cultural-events-rag status`) shows the index served, its documents, when it was built, and whether the code still builds it the same way.

## Retrieval

```bash
make analyze Q="Un concert gratuit ce week-end à Saint-Cyprien ?"
```

`make analyze` (`cultural-events-rag analyze`) shows the filters the search will apply to a question, read by rules, without any model: the period ("ce week-end", "en décembre", "du 20 au 25 octobre", "Noël", "les vacances de la Toussaint", taken at their widest whatever the year), free entry ("gratuit", "entrée libre": the free events and those whose price the agenda does not give, many free ones not saying so; the answer tells which price is unknown), the district or the venue, among those of the index served. A question without a period, or with one under way, looks for events from today; past events only for a question about the past ("le mois dernier"). `ARGS="--today 2026-10-15"` asks it on another day.

## CI

GitHub Actions runs one job per make target of the same name: `lint`, `typecheck`, `pre-commit`, `test-unit` and `coverage`, the coverage of each file written in the summary of the run. `make ci` runs every check of the CI on this machine. The CI needs no secret: the tests fake Mistral and Open Agenda, and start their own Elasticsearch. The packages of uv and the hooks of pre-commit are cached between runs; a new push stops the run still going on the same branch.

## Test

```bash
make test-unit
make test-integration
make coverage
```

`make test-unit` runs the tests that need only the repository, also before each `git push`. `make test-integration` runs those that need an Elasticsearch: [testcontainers](https://testcontainers.com) starts their own container of the image of `compose.yaml` on a free port, with its security on, and removes it at the end, even when the tests are killed. `make test-all` runs the unit and integration tests. `make coverage` runs them and measures the lines of the package they run: it lists those left out, and fails below 95%. `make lint` checks the Python, `make format` fixes what it can, `make typecheck` checks the types, `make pre-commit` runs every hook on every file.

## Licence

The code, under MIT: see [LICENSE](LICENSE).
