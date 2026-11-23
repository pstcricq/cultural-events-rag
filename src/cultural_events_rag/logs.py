"""The logs of the libraries, kept quiet for the commands: no line per request
nor traceback per failed request, the caller reporting the failure itself."""

import logging


def quiet_libraries() -> None:
    """The libraries log their warnings only, or nothing."""
    # httpx2: used by huggingface_hub; sentence_transformers: a line per model
    # loaded.
    for name in ("httpx", "httpx2", "sentence_transformers"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # They log a whole traceback on each failed request (elastic_transport: a
    # line per request too).
    for name in ("langchain_mistralai.embeddings", "elastic_transport"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    # PyTorch warns at its import on macOS that a feature it does not use there
    # is missing; Hugging Face, offline, that it reads the files it has.
    for name in ("torch.distributed.elastic", "huggingface_hub"):
        logging.getLogger(name).setLevel(logging.ERROR)
