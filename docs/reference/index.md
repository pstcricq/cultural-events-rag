# Code reference

The reference of the package `cultural_events_rag`, generated from its docstrings. The package is organized by step of the pipeline, each depending only on the steps before it:

| Package | Step |
|---|---|
| [`collection`](collection.md) | download and process the events |
| [`indexing`](indexing.md) | turn them into documents and index them |
| [`retrieval`](retrieval.md) | analyze a question and search the index |
| [`generation`](generation.md) | write the answer |
| [`evaluation`](evaluation.md) | measure the search and the answers on the benchmark |
| [`api`](api.md) | serve the assistant over HTTP |
| [`ui`](ui.md) | the web interface, a client of the API |
| [`cli`](cli.md) | the `cultural-events-rag` command |

The modules at the root of the package, the [assistant and the settings](core.md), are shared by all of them.
