# The image of the application, for its three services (models, API, web
# interface): the locked environment with the reranker (PyTorch for the CPU)
# and Streamlit, without the dev tools nor the eval extra.

FROM python:3.12-slim AS builder

# The version of uv pinned by pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# The dependencies first, in their own layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra rerank --extra ui --no-install-project

COPY README.md LICENSE NOTICE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra rerank --extra ui

FROM python:3.12-slim

# A user of its own, and the folders of the two volumes: the events and the
# Hugging Face models.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data /models \
    && chown app /app/data /models

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src
# The settings of Streamlit, read from the working directory.
COPY .streamlit ./.streamlit

# The models are read offline from their volume.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    HF_HUB_OFFLINE=1

USER app

EXPOSE 8000 8501

CMD ["uvicorn", "cultural_events_rag.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
