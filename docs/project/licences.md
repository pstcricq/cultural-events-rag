# Licences

## Code and documentation

The code of the repository, this documentation, and the questions and reference answers of the benchmark (`data/benchmark/questions.json`) are under the MIT licence, see [LICENSE](https://github.com/pstcricq/cultural-events-rag/blob/main/LICENSE).

## Event data

The events are not under MIT: they keep the licence of their source, see [NOTICE](https://github.com/pstcricq/cultural-events-rag/blob/main/NOTICE).

`data/benchmark/events.jsonl` holds public events of Toulouse published on [Open Agenda](https://openagenda.com), fetched through the Open Agenda API and through its mirror on OpenDataSoft, the dataset "Public events - OpenAgenda". `make fetch` and `make process` fetch and write the same kind of data into `data/raw/` and `data/processed/`, which are not versioned.

These events are published under the [Licence Ouverte / Open Licence 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence/) of Etalab. The licensor of an event is the organization of the agenda it was created in, not Open Agenda, which hosts and distributes the agendas. Each event keeps its attribution:

| Field | |
|---|---|
| `agenda_title` | the agenda, its licensor |
| `url` | its canonical link on Open Agenda |
| `updated_at` | the date of its last update at its source |

The events were modified: read into a common format, their HTML turned into text, those outside the city or of another period left out, each event kept once, and the sessions of one activity merged. The personal data of the contributors and the images of the events are not kept.

## Models and libraries

| | Licence |
|---|---|
| `BAAI/bge-reranker-v2-m3` | Apache 2.0 |
| `mistral-embed`, `ministral-14b-latest` | called through the Mistral API, under its terms |
| Elasticsearch, Kibana | Elastic License 2.0, AGPL v3 or SSPL, run unmodified |
| The Python dependencies | their own licences, listed in `uv.lock` |
