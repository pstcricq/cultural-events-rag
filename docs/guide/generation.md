# Generation

```bash
make ask Q="Un concert de jazz ?"
```

## The prompt

The chat model, `ministral-14b-latest` (the most capable model of the free Mistral plan), receives a French system prompt and the question. The prompt gives:

- the day of the question, to place the events in time without limiting the search to it;
- the events found, each whole (its header and its whole description) between `<event uid="...">` tags, so that the model can name the ones it recommends;
- its rules.

| Rule | Why |
|---|---|
| Use only the facts of the events given | no invented date, time, place, price or audience |
| Name no place, event or source absent from the events | no redirection to other agendas or ticket offices |
| Recommend every event that fits, even partly, saying what differs | a screening in a library for a question about cinema is still an answer |
| When none fits, say so and recommend none | the reranker score alone cannot tell an out-of-scope question apart |
| "Entrée libre" means free; "Tarif : non précisé" is never free | consistent with the free-entry filter |
| Mention a special status (cancelled, full, postponed) | the index keeps them |
| Plain text, no links, no Markdown | the details and links are shown beside the answer |

Five events of a few hundred tokens each make a context of about 2,000 tokens.

## Structured output

The model returns a structured output, constrained by a JSON schema: its answer, and the uids of the events it recommends, the most relevant first. The descriptions of the fields are instructions to the model, in French.

Then:

- **Only the uids of the events given are kept.** A uid the model made up, or one of an event it was not given, is dropped.
- **The details come from the index.** The dates, place, price and link of each event recommended are those of the index, never those of the generated text.
- **A missing structured output is asked again**, up to 3 attempts in all.
- **An answer cut in the middle of a sentence is detected** (a straight double quote in a description can close the JSON output early). The straight double quotes of the events are replaced with French quotes before the model reads them, since it copies them.
- **Markdown emphasis is removed** from the answer: the model does not always keep to plain text.

## Determinism and quota

The model runs at temperature 0 with a fixed seed. The free plan allows 2 requests a minute to the chat models (`LLM_REQUESTS_PER_MINUTE`): a pacer spaces the calls, 30 s apart, the first at once, rather than letting Mistral refuse them and retry after longer and longer waits. The pacer is shared when two models share the quota, as the assistant and the judge do in the evaluation. Each call is one attempt: the caller retries, visibly.
