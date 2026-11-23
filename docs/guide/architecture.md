# Architecture

## The pipeline

**Offline**, on demand (`make rebuild`, or `POST /rebuild`): the agendas become an index.

```mermaid
flowchart LR
    oa(["Open Agenda API<br/>or OpenDataSoft"]):::source -- "fetch" --> raw["raw events<br/><i>data/raw/</i>"]:::store
    raw -- "process" --> ev["events<br/><i>data/processed/</i>"]:::store
    ev -- "index<br/>mistral-embed" --> idx[("Elasticsearch<br/>alias <i>events</i>")]:::store
    classDef source fill:#fbf1e8,stroke:#e0a526,color:#3d1530
    classDef process fill:#fde4d8,stroke:#c2410c,color:#6e280c
    classDef store fill:#f1ece6,stroke:#9b8f86,color:#2a1220
    classDef model fill:#f3e3ec,stroke:#6b1f45,color:#3d1530
    classDef service fill:#e4f1e8,stroke:#2f7d4f,color:#1d3b28
```

**Online**, for each question: four steps, each a package of its own.

```mermaid
flowchart LR
    q(["question"]):::source --> an["query analysis<br/>rules"]:::process
    an -- "filters" --> s["search<br/>BM25 + kNN, RRF"]:::process
    idx[("Elasticsearch")]:::store --> s
    s -- "20 candidates" --> rr["reranker<br/>bge-reranker-v2-m3"]:::model
    rr -- "5 events" --> llm["ministral-14b<br/>structured output"]:::model
    llm --> a(["answer + events"]):::service
    classDef source fill:#fbf1e8,stroke:#e0a526,color:#3d1530
    classDef process fill:#fde4d8,stroke:#c2410c,color:#6e280c
    classDef store fill:#f1ece6,stroke:#9b8f86,color:#2a1220
    classDef model fill:#f3e3ec,stroke:#6b1f45,color:#3d1530
    classDef service fill:#e4f1e8,stroke:#2f7d4f,color:#1d3b28
```

## The packages

The package `cultural_events_rag` has one subpackage per step. Each depends only on the steps before it and on the modules at the root, never on a later one:

| Package | Step | Depends on |
|---|---|---|
| `collection` | download the raw events, process them into the common format | root |
| `indexing` | turn the events into documents, embed them, write the index | root |
| `retrieval` | analyze a question, search the index, rerank | `indexing` |
| `generation` | write the answer from the events found | `retrieval` |
| `evaluation` | measure the search and the answers on the benchmark | every step |
| `api` | serve the assistant and the rebuild over HTTP | every step |
| `ui` | the web interface, a client of the API | `api` schemas only |
| `cli` | the `cultural-events-rag` command, one module per command | every step |

At the root: `assistant.py` puts the steps together, `settings.py` reads the environment, `constants.py` holds what is tied to the city, `models.py` the data models, `mistral.py` and `elastic.py` the clients, `retry.py` the retry policy.

```mermaid
flowchart LR
    cli["cli"] --> assistant
    api["api"] --> assistant
    evaluation["evaluation"] --> assistant
    ui["ui"] -. "HTTP" .-> api
    assistant["assistant"] --> generation
    generation --> retrieval
    retrieval --> indexing
    cli --> collection
    api --> collection
    collection & indexing & retrieval & generation --> root[("root modules<br/>settings, constants, models,<br/>clients, retry")]:::store
    class cli,api,ui service
    class assistant,generation model
    class retrieval,indexing,collection,evaluation process
    classDef source fill:#fbf1e8,stroke:#e0a526,color:#3d1530
    classDef process fill:#fde4d8,stroke:#c2410c,color:#6e280c
    classDef store fill:#f1ece6,stroke:#9b8f86,color:#2a1220
    classDef model fill:#f3e3ec,stroke:#6b1f45,color:#3d1530
    classDef service fill:#e4f1e8,stroke:#2f7d4f,color:#1d3b28
```

## The assistant

`assistant.py` is the one place where the served configuration is written: the search mode (`SEARCH_MODE = "hybrid"`) and whether to rerank (`RERANK = True`), the choices the [evaluation of the search](evaluation.md) made. The search itself offers every mode and leaves the choice to its caller. The commands that answer a question (`ask`, the API, the evaluation of the answers) all load the assistant the same way, so they serve the same thing.

## Principles

**Settings are not choices.** A setting is what an environment decides: its keys, where its services are, what its machine and its Mistral plan allow. The choices of the design (chunk size, models, search mode) are constants next to the code that uses them, the same everywhere, changed by a commit that the evaluation measures. See [Configuration](../operations/configuration.md).

**No default for a setting.** Every setting is unset until the environment sets it, and the code that needs one refuses to run without it, naming it. A forgotten value is an error, not a silent default.

**The index records how it was built.** Each index stores a signature: the embedding model, the chunking, the format of the documents, the mappings. The search refuses an index the code would now build otherwise, and `status` says what differs.

**Facts come from the index.** The chat model writes the text of the answer and names the events it recommends; their dates, place, price and link come from the index, never from the generated text.

**Rules before models.** The constraints of a question are read by tested rules, not by a model: the same question always gives the same filters, and each phrasing has its test.

**One build, one swap.** A build writes a new index and moves the alias onto it only once complete. The questions are answered from the previous index meanwhile, and a failed build leaves it untouched.
