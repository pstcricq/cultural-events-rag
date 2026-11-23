---
title: Home
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

<span class="kicker">RAG assistant · Toulouse · Open Agenda</span>

# Que faire à Toulouse ?

<span class="ask">:material-account-outline: « Un concert gratuit ce week-end à Saint-Cyprien ? »</span>

An assistant that recommends the cultural events of Toulouse. It reads a question in French for its period, place and price, searches the events of the city's public agendas by their words and their meaning, and lets a Mistral model answer from those events only, every date, place and price taken from the agendas.

[Get started](getting-started.md){ .md-button .md-button--primary } [How it works](guide/architecture.md){ .md-button } [Source code](https://github.com/pstcricq/cultural-events-rag){ .md-button }

</div>

This site is the technical guide: how each step is built and why, how the assistant is measured, how to run and deploy it. To install and run the project quickly, the [README](https://github.com/pstcricq/cultural-events-rag#readme) is the shorter path.

## Tonight's figures

Measured on the benchmark of 50 annotated questions; the numbers change with each evaluation.

<div class="tickets">
  <div class="ticket"><span class="label">Recall@5 of the search</span><span class="figure">0.81 → 0.89</span><span class="note">BM25 alone, then hybrid search reranked: the configuration served.</span></div>
  <div class="ticket"><span class="label">Recommendation precision</span><span class="figure">0.92</span><span class="note">The share of the events an answer recommends that are relevant.</span></div>
  <div class="ticket"><span class="label">Faithfulness</span><span class="figure">0.88</span><span class="note">The claims of an answer supported by the events given, scored by Ragas.</span></div>
  <div class="ticket"><span class="label">Out of scope</span><span class="figure">4 / 5</span><span class="note">Questions outside culture answered without any event.</span></div>
  <div class="ticket"><span class="label">Agendas</span><span class="figure">11</span><span class="note">Libraries, museums, conservatory, theatres, cinemas, heritage days.</span></div>
  <div class="ticket"><span class="label">Tests</span><span class="figure">544</span><span class="note">Unit, integration against a real Elasticsearch, smoke; 99% of the lines.</span></div>
</div>

## The programme

<div class="programme">
<a href="guide/collection/"><strong>Collect</strong><span>11 agendas, one common format, sessions merged</span></a>
<a href="guide/indexing/"><strong>Index</strong><span>French text, vectors and metadata in Elasticsearch</span></a>
<a href="guide/search/"><strong>Search</strong><span>rules for the filters, BM25 and kNN fused, reranked</span></a>
<a href="guide/generation/"><strong>Answer</strong><span>Mistral writes, the index gives the facts</span></a>
<a href="guide/evaluation/"><strong>Measure</strong><span>50 questions, search and answers compared</span></a>
</div>

## On stage

![The web interface: the question, the answer written as it appears, and a card per event recommended](assets/screenshots/ui-answer.png){ .shot-l }

*The web interface, a client of the REST API: the answer, then a card per event with its day, its badges, its slots and its place.*

```mermaid
flowchart LR
    oa(["Open Agenda"]):::source -- fetch, process --> ev["events"]:::store
    ev -- index --> es[("Elasticsearch")]:::store
    q(["question"]):::source --> an["query analysis"]:::process
    an --> s["hybrid search"]:::process
    es --> s
    s --> rr["reranker"]:::model
    rr --> llm["Mistral"]:::model
    llm --> api["REST API"]:::service
    api --> ui["web interface"]:::service
    classDef source fill:#fbf1e8,stroke:#e0a526,color:#3d1530
    classDef process fill:#fde4d8,stroke:#c2410c,color:#6e280c
    classDef store fill:#f1ece6,stroke:#9b8f86,color:#2a1220
    classDef model fill:#f3e3ec,stroke:#6b1f45,color:#3d1530
    classDef service fill:#e4f1e8,stroke:#2f7d4f,color:#1d3b28
```

## Where to go next

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .brick } __Getting started__

    Install, configure, collect and index the events, ask a question.

    [:octicons-arrow-right-24: Install and run](getting-started.md)

-   :material-sitemap-outline:{ .lg .brick } __Architecture__

    The pipeline, its packages, and the principles behind them.

    [:octicons-arrow-right-24: How it is built](guide/architecture.md)

-   :material-chart-bar:{ .lg .brick } __Evaluation__

    The benchmark, the metrics, and what they say.

    [:octicons-arrow-right-24: How it is measured](guide/evaluation.md)

-   :material-api:{ .lg .plum } __API__

    Routes, answers and errors of the REST API.

    [:octicons-arrow-right-24: Ask over HTTP](guide/api.md)

-   :material-docker:{ .lg .plum } __Docker__

    The image, the services, and how a server runs them.

    [:octicons-arrow-right-24: Deploy](operations/docker.md)

-   :material-scale-balance:{ .lg .plum } __Decisions__

    The choices of the project and their reasons.

    [:octicons-arrow-right-24: Why it is so](project/decisions.md)

</div>

The project is a proof of concept for a cultural-events platform, fictional and not affiliated with the organizers nor with Open Agenda. The application speaks French, the language of its events and users; the code and this documentation are in English.
