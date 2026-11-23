# Decisions

The choices of the project and their reasons. The code says what it does; this page says why it does it that way.

## Data

**Open Agenda, with a fallback.** The official API is the source of record and needs a key; its mirror on OpenDataSoft needs none, so the project runs on a laptop without any account. Both are parsed into the same common format, so the rest of the pipeline does not know which one was used.

**Agendas picked by hand.** The public agendas of Toulouse include employment services and local associations. The 11 agendas kept are cultural, so the assistant does not recommend a job fair for a free evening.

**Upcoming first, then a year back.** The assistant recommends outings: the upcoming events come first. The events of the past year answer the questions about the past ("le mois dernier"). Sorting the upcoming events by update spreads them over the months; sorting by date would keep only the next weeks.

**The sessions of one activity merged.** A guided tour published once per date would otherwise fill the five results with one activity, and repeat the same text in the index.

**No personal data, no images.** The OpenDataSoft records carry the contributors' names and emails: they are not kept. The images of the events are under the Licence Ouverte too, but their credits would have to be carried everywhere they are shown; the cards show the facts instead.

## Index

**Elasticsearch.** One engine does the lexical search (BM25 with a French analyzer), the vector search (kNN), the exact filters on dates, places and prices, and the alias that swaps an index atomically. A vector store alone would need a second engine for the rest.

**Exact vector search.** At a few thousand documents, comparing the question with every vector is instant and finds the true nearest neighbours. An approximate graph (HNSW) only pays off at hundreds of thousands, at the cost of recall.

**The header in every chunk.** A chunk of a long description says little alone; headed by the title, dates, place and price of its event, its vector stays tied to the event. The chat model reads the whole event, not the chunk, since the best chunk can leave out the sessions or the prices.

**An index that records how it was built.** A change of the chunking, the documents or the embedding model makes the vectors of the index incomparable with those of the questions. The signature in `_meta` lets the search refuse such an index instead of returning wrong results.

**Explicit tokenizer, explicit retries.** The Mistral client counts tokens with the Mistral tokenizer when it finds it, and silently counts characters otherwise; it is loaded explicitly, so a missing tokenizer is an error. Its built-in retries wait a fixed 30 s, silently; they are turned off in favour of an exponential backoff that logs each retry.

## Search

**Rules for the constraints.** A vector holds a meaning, not a date: "ce week-end" is closer to any weekend event than to the right ones. The period, the place and the price are read by rules and applied as exact filters. Rules are deterministic and each phrasing is tested; a language model would add a call, a cost and a variance to every question.

**Hybrid search, fused by rank.** BM25 finds the exact words (a name, a title); the vectors find the meanings ("en famille"). They miss different events: fused, they find more relevant events among their candidates than either alone. Reciprocal Rank Fusion needs no calibration of two scores on different scales, and is computed in Python since the RRF of Elasticsearch needs a paid licence.

**A local cross-encoder.** Mistral has no reranking API. `BAAI/bge-reranker-v2-m3` is multilingual, reads French well, and runs locally on the first 20 candidates only: exact enough to reorder them, too slow for the whole index.

**The configuration chosen by measure.** The search offers every mode; the evaluation compared them, and the assistant serves the best one. The choice is written in one place, `assistant.py`.

## Generation

**The facts from the index.** The model names the events it recommends by their uid; their details are taken from the index. A wrong date or price in the text of an answer can still happen, but never in the cards shown beside it.

**Structured output as a constrained JSON.** The answer and the uids come back as one JSON object constrained by its schema. With a tool call instead, the Mistral API failed on long answers.

**A pacer rather than retries.** The free plan allows 2 requests a minute. Spacing the calls keeps to the quota; letting Mistral refuse them would mean retries after longer and longer waits.

**Swappable providers.** The models are used through their LangChain interfaces (`Embeddings`, `BaseChatModel`): another provider can take their place without touching the steps.

## Evaluation

**A frozen benchmark in its own index.** The events change every day; the relevance judgments do not. The benchmark keeps the events it was judged on, and builds its own index from them with the same code, so the evaluation measures the search, not the drift of the data.

**Exact checks first, a judge second.** Whether the recommended events are relevant is known exactly from the judgments; only the quality of the text needs a judge. Ragas context precision and recall are left out: they would judge again, less exactly, what the evaluation of the search measures against human judgments.

## Operations

**No default for a setting.** A default for an API key, a password or a number of events would hide a forgotten value until it causes harm. Every setting is required where it is used, and named when missing.

**One compose file, one image.** The same `compose.yaml` serves every environment, its values from the environment; this machine only adds the build of the image. The three services of the application share one image, and PyTorch with it.

**The interface as a client of the API.** The web interface goes through the API like any front end, with the schemas of the API as the contract. The API can serve another front end; the interface needs no secret.
