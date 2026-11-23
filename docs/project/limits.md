# Limits and next steps

## Known limits

**The quota of the free plan.** Two requests a minute to the chat models: one answer every 30 s, the questions asked at once waiting their turn, and an evaluation with the judge takes about three hours. A paid plan lifts it with one setting, `LLM_REQUESTS_PER_MINUTE`.

**The reranker on a CPU.** In a container, a reranked search takes about 10 s, against about 2 s on the GPU of a Mac. A server without a GPU serves at that speed, or without the reranker (`RERANK_AVAILABLE=false`) and below what was measured.

**Optimistic scores.** The configuration was chosen on the same 50 questions it is measured on: its scores are slightly optimistic, and a gap of a few points between two configurations is not necessarily real. The judge is the model that wrote the answers, and tends to rate them well.

**Out-of-scope questions.** One out-of-scope question in five still gets events recommended (abstention 0.80): the reranker score alone cannot tell them apart, and the model sometimes stretches a weak match.

**The phrasings the rules know.** The query analysis reads the periods, places and prices it has rules for. An unusual phrasing ("la quinzaine de Pâques") gives no filter, and the search falls back to the vectors.

**No conversation.** Each question is answered on its own: "et le dimanche ?" does not refer to the previous question.

**Data freshness.** The index is as fresh as its last rebuild, run by hand (`make rebuild`) or through `POST /rebuild`. Nothing schedules it.

**One node, plain HTTP.** Elasticsearch runs as one node without TLS inside the compose network, with its built-in superuser on a laptop. A production deployment needs TLS, a user limited to the events indices, and a replica.

**One city.** The city, its agendas, its timezone and its calendar are constants; another city is another version of `constants.py` and its own benchmark.

## Next steps

- Run the reranker with ONNX Runtime, a backend of sentence-transformers, and check its scores again with `make eval-retrieval`.
- Schedule the rebuild, nightly, from the API or a cron job, with an alert when it fails.
- Keep the previous turns of a conversation, rewriting a follow-up question into a standalone one before the search.
- Split the benchmark into questions to tune on and questions to measure on, and grow it.
- Detect the out-of-scope questions before the search, with a threshold measured on the benchmark.
- Publish the image to a registry from the CI, and deploy it.
- Monitor the API: latency, errors, the questions that find no event.
