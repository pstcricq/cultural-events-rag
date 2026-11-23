"""The log levels of the third-party libraries used by the commands."""

import logging


def quiet_libraries() -> None:
    """Set the third-party libraries to log warnings only, or nothing."""
    # httpx2 (used by huggingface_hub) and sentence_transformers log a line per
    # request or model loaded.
    for name in ("httpx", "httpx2", "sentence_transformers"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # These log a traceback for each failed request.
    for name in ("langchain_mistralai.embeddings", "elastic_transport"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    # Warnings of PyTorch on macOS and of Hugging Face offline, at import.
    for name in ("torch.distributed.elastic", "huggingface_hub"):
        logging.getLogger(name).setLevel(logging.ERROR)
