# Configuration

```bash
cp .env.example .env
make config
```

## Settings and constants

The project separates two kinds of values.

**Settings** are what an environment decides: its secrets, where its services are, what its machine and its Mistral plan allow. They come from the environment, then from `.env`, a variable of the environment winning over the same line of `.env`. None has a default in the code: an unset setting is `None`, and the code that needs it raises an error that names it. [`.env.example`](https://github.com/pstcricq/cultural-events-rag/blob/main/.env.example) gives each one its value.

**Constants** are the choices of the design: the city and its agendas, the chunk size, the models, the search mode. They are the same in every environment, written next to the code that uses them, and changed by a commit that the evaluation measures.

## Settings

| Variable | Read by | |
|---|---|---|
| `MISTRAL_API_KEY` | index, search, ask, API, evaluation | the Mistral API key |
| `OPENAGENDA_API_KEY` | fetch, rebuild | the Open Agenda API key; unset, the OpenDataSoft mirror |
| `ADMIN_API_KEY` | API | the key of `POST /rebuild`; unset, the rebuild is turned off |
| `ELASTICSEARCH_URL` | every command | the URL of Elasticsearch, `http://127.0.0.1:9200` from this machine |
| `ELASTIC_USER`, `ELASTIC_PASSWORD` | every command | the user the application signs in as, and its password |
| `ELASTICSEARCH_INDEX` | every command | the alias of the index served, `events` |
| `MAX_EVENTS` | fetch, rebuild | the number of events to collect, or `all`; required |
| `RERANK_AVAILABLE` | models, search, ask, API, evaluation | whether this machine can run the reranker |
| `LLM_REQUESTS_PER_MINUTE` | ask, API, evaluation | the requests per minute the Mistral plan allows its chat models, 2 on the free plan |
| `API_URL` | web interface | the URL of the API |

Docker Compose reads a few more, never read by the application:

| Variable | |
|---|---|
| `KIBANA_PASSWORD` | the password of `kibana_system`, the user Kibana signs in as |
| `API_ELASTICSEARCH_URL` | where the API container reaches Elasticsearch: `http://elasticsearch:9200` in compose, another address without the profile `search` |
| `ELASTIC_VERSION` | the version of every Elastic image |
| `APP_IMAGE`, `APP_TAG` | the image of the application |

`make config` (`cultural-events-rag config show`) prints the active settings, the secrets only shown as set or not.

## Constants

| Constant | Value | Where |
|---|---|---|
| `CITY` | Toulouse | `constants.py` |
| `CULTURAL_AGENDAS` | 11 agendas | `constants.py` |
| `LOOKBACK_DAYS` | 365 | `collection/fetch.py` |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | 1,000 and 150 characters | `indexing/chunking.py` |
| `EMBEDDING_MODEL` | `mistral-embed` | `mistral.py` |
| `LLM_MODEL`, `JUDGE_MODEL` | `ministral-14b-latest` | `mistral.py` |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | `retrieval/rerank.py` |
| `CANDIDATES` | 50 entries per search | `retrieval/search.py` |
| `RERANK_CANDIDATES` | 20 events | `retrieval/search.py` |
| `SEARCH_K` | 5 events | `retrieval/search.py` |
| `SEARCH_MODE`, `RERANK` | hybrid, reranked | `assistant.py` |
| `MAX_QUESTION_LENGTH` | 500 characters | `api/schemas.py` |

Another city means another version of `constants.py`: its agendas, its timezone, its calendar.
