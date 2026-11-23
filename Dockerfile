# The image of the application, one for its two services (the command that
# downloads the models, the API): the locked environment without the dev tools
# nor the eval extra (the evaluation runs outside), with the reranker (PyTorch
# for the CPU on Linux).

FROM python:3.12-slim AS builder

# The version of uv pinned by pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# The dependencies first, in a layer of their own: a change of the code does
# not install them again.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra rerank --no-install-project

COPY README.md LICENSE NOTICE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra rerank

FROM python:3.12-slim

# A user of its own, and the folders of its two volumes: the events (data/,
# rewritten by POST /rebuild) and the models of Hugging Face.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data /models \
    && chown app /app/data /models

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src

# The models read from the volume, offline: the models service downloads them.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    HF_HUB_OFFLINE=1

USER app

EXPOSE 8000

CMD ["uvicorn", "cultural_events_rag.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
