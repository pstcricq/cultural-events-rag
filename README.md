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

`make install` sets up the locked environment in `.venv`, with the `rerank` extra (sentence-transformers and PyTorch for the reranker, about 1 GB), the `cultural-events-rag` command and the git hooks. Without the reranker, `uv sync` installs the rest alone. `make models` (`cultural-events-rag models`) downloads once, into the cache of Hugging Face, the models run on this machine: the Mistral tokenizer (about 2 MB), that counts the tokens of each embedding request, and the reranker, `RERANK_MODEL` (about 2.3 GB, unless `RERANK_AVAILABLE=false`). Every other target runs Hugging Face offline (`HF_HUB_OFFLINE=1`): a model missing is reported, never downloaded on the way. `make help` lists every target, `make <target> ARGS=--help` every option of its command, `uv run cultural-events-rag --help` every command.

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

The index of the events lives in [Elasticsearch](https://www.elastic.co/elasticsearch), run by docker compose: one node, with the `elastic` user and `ELASTIC_PASSWORD` from `.env`, over plain HTTP. `compose.yaml` holds the services as they run in every environment, and writes none of the values an environment sets: it takes them from the environment, then from `.env`, and refuses to start without any of them, naming the one missing: the secrets, the settings of the API (`MAX_EVENTS`, `RERANK_AVAILABLE`…), the version of every Elastic image `ELASTIC_VERSION`, the image of the application `APP_IMAGE:APP_TAG`, all listed in `.env.example`. The same file serves every environment: it runs the image `APP_IMAGE:APP_TAG` names. On this machine, the `docker-*` targets of make read `compose.dev.yaml` along with it, which builds that image from this checkout (`cultural-events-rag:local`); a server runs docker compose on `compose.yaml` alone and pulls the image from its registry (`docker compose pull`, then `docker compose up -d`). The ports are published on 127.0.0.1, this machine only. `make docker-up` builds the image again when the code changed, starts the services and waits until they are healthy (`S=elasticsearch`: Elasticsearch alone); `make docker-down` stops them and keeps their data, `make docker-ps` shows their health, `make docker-logs` their logs, `make docker-reset` deletes their data: the only way to change `ELASTIC_PASSWORD`, read at the first start alone.

Elasticsearch and Kibana run under compose with the profile `search`, which make always gives, and the API reaches Elasticsearch by its name, `API_ELASTICSEARCH_URL=http://elasticsearch:9200`. A server with an Elasticsearch run elsewhere starts compose without the profile (`docker compose up -d`) and sets `API_ELASTICSEARCH_URL` to its address: compose then starts neither of them, and the API does not wait for them. The API starts without Elasticsearch all the same: its `/health` answers 503 with the reason, and its logs give the cause (`make docker-logs S=api`), an address that resolves to no host for instance.

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

`make index` (`cultural-events-rag index`) sends these documents to `mistral-embed` (`MISTRAL_API_KEY`) in batches of about 15k tokens, a batch retried on a rate limit or a server error, and writes them into Elasticsearch: each one with its text, analyzed in French for the lexical search (BM25), its vector, for the vector search (kNN, exact: the question is compared with every vector by cosine), and its metadata, as fields to filter on. Each build writes a new index, then moves the alias `events` (`ELASTICSEARCH_INDEX`) onto it once every event is in it, and deletes the one it served: a failed build leaves the served index as it was. The index records what it was built with, the embedding model, the chunking, the document format and the vector index type: `make status` (`cultural-events-rag status`) shows the index served, its documents, when it was built, and whether the code still builds it the same way. `make rebuild` refreshes the events served: `make fetch`, `make process` and `make index` in a row, as `POST /rebuild` does (`ARGS` go to `make fetch`).

## Retrieval

```bash
make analyze Q="Un concert gratuit ce week-end à Saint-Cyprien ?"
make search Q="Un concert gratuit ce week-end à Saint-Cyprien ?" ARGS="--mode hybrid --rerank"
```

`make analyze` (`cultural-events-rag analyze`) shows the filters the search will apply to a question, read by rules, without any model: the period ("ce week-end", "en décembre", "du 20 au 25 octobre", "Noël", "les vacances de la Toussaint", taken at their widest whatever the year), free entry ("gratuit", "entrée libre": the free events and those whose price the agenda does not give, many free ones not saying so; the answer tells which price is unknown), the district or the venue, among those of the index served. A question without a period, or with one under way, looks for events from today; past events only for a question about the past ("le mois dernier"). `ARGS="--today 2026-10-15"` asks it on another day.

`make search` (`cultural-events-rag search`) gives the events of the index closest to the question, among those its filters keep: Elasticsearch applies the filters first, then ranks only the entries left. `make search` is a tool to explore: it has no choice of its own, the mode is always given. `--mode` picks the ranking: `lexical`, the words of the question against the French text of the entries (BM25); `vector`, its vector (`mistral-embed`) against theirs, by cosine; `hybrid`, both, their two rankings fused by Reciprocal Rank Fusion. An event split into several chunks counts once, at the rank of its best chunk; the `SEARCH_K` best events (5) are kept, each with its rank in each ranking, `--k 10` for more. The search refuses an index the code builds otherwise now: `make status` tells what differs.

With `--rerank`, a cross-encoder, `RERANK_MODEL` (`BAAI/bge-reranker-v2-m3`), sorts the first 20 events of the search again: it reads the question and the best chunk of each event together, and scores how well the chunk answers it, more exactly than the comparison of their vectors, too slowly for the whole index. It runs on this machine (the `rerank` extra, the model downloaded by `make models`): about 2.3 GB on disk, 2 to 3 GB of memory, a few seconds to load, under a second per search. Which mode the assistant serves, and whether it reranks, the evaluation of the search decides (see Evaluation).

## Generation

```bash
make ask Q="Un concert de jazz ?"
```

`make ask` (`cultural-events-rag ask`) answers the question from the events the search found: the LLM, `LLM_MODEL` (`ministral-14b-latest`, the most capable model of the free Mistral plan), reads each of them whole, its header and its whole description, not only its best chunk, which can leave out its sessions or its prices. Each event is a few hundred tokens: five make a context of about 2,000. The prompt, in French, holds it to those events: nothing invented, every event that fits recommended, and no event at all when none fits ("Un bon restaurant italien"), since the score of the reranker alone cannot tell such a question apart (`reports/retrieval.md`). The LLM returns its answer and the uids of the events it recommends; only the events it was given are kept, and their details (place, slot, price, link) are shown from the index, never from the generated text. It searches as the assistant does (`assistant.py`); `ARGS="--today 2026-10-15 --no-rerank"` for a day of your choice, or without the reranker.

## API

```bash
make api
```

`make api` serves the assistant as a REST API (FastAPI, uvicorn) on http://127.0.0.1:8000, its interactive documentation at http://127.0.0.1:8000/docs. The assistant is loaded once, at start (Elasticsearch, the embedding model, the reranker, the LLM), then shared by every question:

| Route | What it does |
|---|---|
| `POST /ask` | `{"question": "Un concert de jazz ?", "today": "2026-10-19"}` (`today` optional, today in Toulouse by default): the answer, the filters read in the question, and the events it recommends, each with its title, venue, address, district, ages (`age_min`, `age_max`, when the agenda gives them), dates in French, first slot in the period, price (free, paid, or `null` when unknown), and link, all from the index, never from the generated text. |
| `GET /health` | `ok` when the assistant is loaded and the index served is up to date with the settings; 503 with the reason otherwise. |
| `GET /metadata` | The index served (events, documents, build time), the models and the search, and the state of the last rebuild. |
| `POST /rebuild` | Fetches, processes and indexes the events again, as `make rebuild` (`make fetch process index`), in the background: 202 at once, its progress on `/metadata`, 409 while one runs. It needs the `ADMIN_API_KEY` of `.env` in the `X-API-Key` header, and is turned off without it. The questions keep their answers from the index served until the new one is complete. |

A failure has its code: 422 for an empty or too long question (500 characters), 503 when Elasticsearch or the index is missing, 502 when Mistral fails after its retries. The answers share the quota of the Mistral plan: on the free plan, two questions asked at once wait 30 s more each.

Under docker compose, `make docker-up` builds the image of the application (`Dockerfile`: the locked environment with the reranker, PyTorch for the CPU, without the dev tools nor the `eval` extra, about 2 GB; built again at each `make docker-up`, only what changed since the last time) and starts the API from it on the same port, after two services: Elasticsearch, healthy, and `models`, which downloads once the models of Hugging Face into a volume of their own (about 2 GB, at the first start only), read offline by the API. The API takes its secrets and its settings from `.env` or the environment, each one named in `compose.yaml`, reaches Elasticsearch at `API_ELASTICSEARCH_URL` (see Search engine), and keeps the events `POST /rebuild` writes in a volume. Its `/health` answers 503 until an index is built: `make index` from this machine, or `POST /rebuild`. In a container, the reranker runs on the CPU: Docker Desktop gives no access to the GPU of a Mac, nor would a server without one. Measured on an Apple M4 Pro, a reranked search takes about 10 s per question in the container (6.6 s to read the 20 candidates, whatever the number of threads), against about 2 s with `make api`, which uses the GPU of the Mac; the answer of the LLM comes on top. Kept as it is for this proof of concept: the reranking is what the evaluation measured. Running the same model with ONNX Runtime (a backend of sentence-transformers) would be the first step to make it faster, its scores checked again by `make eval-retrieval`.

## Evaluation

```bash
make benchmark
make eval-retrieval
```

The benchmark (`data/benchmark/`, committed) measures the search on fixed ground: 50 questions in French (`questions.json`), each with the events a human judged relevant and a reference answer, all judged as of a reference date, and the 1,850 events they were judged on (`events.jsonl`), frozen. `make benchmark` (`cultural-events-rag benchmark`) checks that every relevant event is among them, then writes them into Elasticsearch under an alias of their own, `events-benchmark`, beside the index of the application, by the same build: only when that index is missing, built otherwise than the code builds it now, or holds other events.

`make eval-retrieval` (`cultural-events-rag evaluate retrieval`) searches each question in that index, as of its reference date, by each configuration: `lexical`, `vector` and `hybrid`, without then with the reranker (`ARGS="--no-rerank"`, or `RERANK_AVAILABLE=false`: without only). No LLM is involved: the events found are compared with those judged relevant, by Hit@5, Recall@5, Precision@5, MRR and Recall@20, the candidates of the reranker. Recall@k counts the relevant events in the first k out of min(k, relevant events): five relevant events in the first five of "en décembre" is a perfect answer. The report, `reports/retrieval.md`, sets every configuration side by side, the best score of each row in bold: the metrics, how often each one does better than each other question by question (a mean can hide a few large gains or losses), the metrics by category, Recall@5 for each question, and what comes first for the out-of-scope questions, with the first score of the reranker; `reports/retrieval.json` holds every ranking. The configuration it chose is the search the assistant serves, written where the assistant is put together, `assistant.py`: `SEARCH_MODE = "hybrid"` and `RERANK = True`. The search itself makes no choice. An environment that cannot run the reranker says so with `RERANK_AVAILABLE=false`, and serves below what was measured. That configuration was chosen on these same 50 questions: its scores are slightly optimistic, and a gap of a few points between two configurations is not necessarily real.

```bash
make eval-generation
```

`make eval-generation` (`cultural-events-rag evaluate generation`) asks each question of the benchmark to the whole assistant, as of its reference date, with the configuration kept only (`SEARCH_MODE`, `RERANK`, `LLM_MODEL`): the search was measured by `make eval-retrieval`, this measures what the LLM does with the events it is given. First, exactly and without any judge, the events its answer recommends are compared with those judged relevant: the recommendation precision (the share of those recommended that are relevant), the recommendation recall (the share of the relevant events given to the LLM that it recommends) and, for the out-of-scope questions, the abstention (an answer without any event). Then an LLM judge, `JUDGE_MODEL` (the model that wrote the answers, which tends to rate them well: read its scores as a comparison between versions), scores the answers to the questions with relevant events with three metrics of [Ragas](https://docs.ragas.io) (the `eval` extra, installed by `make install`): faithfulness (nothing invented beyond the events given), answer relevancy (the answer addresses the question) and factual correctness (the answer against the reference answer). The context precision and context recall of Ragas are left out on purpose: they judge the events given to the LLM, which `make eval-retrieval` already measures against human judgments. The report, `reports/generation.md`, gives the means, by category and question by question, and the answer to each out-of-scope question; `reports/generation.json` holds every answer, the events it recommends, those given to the LLM and the scores of the judge.

The free Mistral plan allows its chat models 2 requests a minute (`LLM_REQUESTS_PER_MINUTE`): the calls are spaced to keep to it, the LLM and the judge sharing the quota. The answers take about 25 minutes, the judge about 2 h 40 more (7 calls per question: 2 for faithfulness, 1 for answer relevancy, 4 for factual correctness); `ARGS="--no-judge"` keeps the exact checks only. The evaluation is run to compare versions of the assistant, not at each change. Each evaluation first shows its estimated time and asks before running; `ARGS="--yes"` runs it without asking, in the background for instance.

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

The code, under MIT: see [LICENSE](LICENSE). The events of the benchmark keep the licence of their source, the Licence Ouverte 2.0 of Etalab, with the attribution of each event: see [NOTICE](NOTICE).
