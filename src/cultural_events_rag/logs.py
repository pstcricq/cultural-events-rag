"""The logs of the libraries, kept quiet for the commands: no line per request
nor traceback per failed request, the caller reporting the failure itself."""

import logging


def quiet_libraries() -> None:
    """The libraries log their warnings only, or nothing."""
    # httpx2: used by huggingface_hub.
    for name in ("httpx", "httpx2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # They log a whole traceback on each failed request (elastic_transport: a
    # line per request too).
    for name in ("langchain_mistralai.embeddings", "elastic_transport"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    # Hugging Face, offline, warns that it reads the files it has.
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
