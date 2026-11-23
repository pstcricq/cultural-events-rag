.DEFAULT_GOAL := help
.PHONY: help install models config docker-up docker-down docker-ps docker-logs docker-reset fetch process documents index status rebuild analyze search ask benchmark eval-retrieval eval-generation api test-all test-unit test-integration coverage lint format typecheck pre-commit ci clean
.SILENT:

# Blank line once at the top of the output, then one after each command.
$(info )

# Run a command followed by a blank line and keep its exit code.
# Its argument holds no comma: $(call) splits its arguments on commas.
run = $(1); status=$$?; echo; exit $$status

# A section per group of the cultural-events-rag command, named after it:
# `uv run cultural-events-rag --help` lists the commands.

UV  := uv
RUN := $(UV) run

# Hugging Face offline for every command: `make models` alone downloads the
# models run on this machine; a command missing one says so.
export HF_HUB_OFFLINE := 1

# docker compose reads compose.yaml and .env on its own.
COMPOSE := docker compose

# The targets of a command take its options in ARGS: ARGS=--help lists them.
help: ## Show this help
	awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m [Q=...] [ARGS=...]\n"; \
		printf "ARGS=--help after a target lists every option of its command\n\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	echo

##@ Environment

install: ## Install the locked environment, the reranker, the judge and the git hooks
	$(call run,$(UV) sync --extra rerank --extra eval)
	$(call run,$(RUN) pre-commit install)

models: ## Download the models run on this machine (Mistral tokenizer, reranker)
	$(call run,HF_HUB_OFFLINE=0 $(RUN) cultural-events-rag models)

##@ Config (cultural-events-rag config)

config: ## Show the active settings, secrets masked
	$(call run,$(RUN) cultural-events-rag config show)

##@ Docker (compose.yaml, its values from .env)

docker-up: ## Start every service (S=<service>: those only), wait until healthy
	$(call run,$(COMPOSE) up -d --wait $(S))

docker-down: ## Stop the services, keep their data
	$(call run,$(COMPOSE) down)

docker-ps: ## Show the containers and their health
	$(call run,$(COMPOSE) ps -a)

docker-logs: ## Follow the logs (S=<service>), or print the last N=<lines>
	$(COMPOSE) logs $(if $(N),--no-color --tail $(N),-f) $(S)

docker-reset: ## Stop the services and delete their volumes (the index)
	printf 'Delete the volumes of the services, the index of the events? [y/N] ' && read ans && [ "$$ans" = y ]
	$(call run,$(COMPOSE) down -v)

##@ Events (cultural-events-rag fetch, process)

fetch: ## Download the raw events, MAX_EVENTS of them (ARGS="--max-events 200")
	$(call run,$(RUN) cultural-events-rag fetch $(ARGS))

process: ## Turn the raw events into the events of the common format
	$(call run,$(RUN) cultural-events-rag process)

##@ Index (cultural-events-rag documents, index, status)

documents: ## Show the documents of the index (ARGS="--uid 123")
	$(call run,$(RUN) cultural-events-rag documents $(ARGS))

index: ## Embed the documents and write their index into Elasticsearch
	$(call run,$(RUN) cultural-events-rag index)

status: ## Show the index served, and whether the code still builds it the same way
	$(call run,$(RUN) cultural-events-rag status)

rebuild: fetch process index ## Download, process and index the events again, as POST /rebuild (ARGS go to fetch)

##@ Retrieval (cultural-events-rag analyze, search)

analyze: ## Show the filters of a question (Q="concert gratuit ce week-end", ARGS="--today 2026-10-15")
	$(call run,$(RUN) cultural-events-rag analyze $(ARGS) "$(Q)")

search: ## Search the events of a question (Q="...", ARGS="--mode hybrid --rerank")
	$(call run,$(RUN) cultural-events-rag search $(ARGS) "$(Q)")

##@ Generation (cultural-events-rag ask)

ask: ## Answer a question from the events found (Q="...", ARGS="--no-rerank")
	$(call run,$(RUN) cultural-events-rag ask $(ARGS) "$(Q)")

##@ Evaluation (cultural-events-rag benchmark, evaluate)

benchmark: ## Check the benchmark and build its index when missing or outdated
	$(call run,$(RUN) cultural-events-rag benchmark)

eval-retrieval: ## Compare the configurations of the search on the benchmark (ARGS="--no-rerank --yes")
	$(call run,$(RUN) cultural-events-rag evaluate retrieval $(ARGS))

eval-generation: ## Answer the benchmark questions and judge them (ARGS="--no-judge")
	$(call run,$(RUN) cultural-events-rag evaluate generation $(ARGS))

##@ API (FastAPI)

api: ## Serve the API on http://127.0.0.1:8000, its documentation at /docs
	$(call run,$(RUN) uvicorn cultural_events_rag.api.app:create_app --factory --host 127.0.0.1 --port 8000)

##@ Tests

test-all: test-unit test-integration ## Run the unit, then integration tests

test-unit: ## Run the tests that need only the repository
	$(call run,$(RUN) pytest tests/unit -q)

test-integration: ## Run the tests that need an Elasticsearch (docker)
	$(call run,$(RUN) pytest tests/integration -q)

coverage: ## Run the unit and integration tests, list the lines left uncovered, fail under 95%
	$(call run,$(RUN) pytest tests/unit tests/integration -q --cov $(ARGS))

##@ Quality

lint: ## Lint the Python (ruff check + format --check)
	$(call run,$(RUN) ruff check .)
	$(call run,$(RUN) ruff format --check .)

format: ## Format and auto-fix the Python
	$(call run,$(RUN) ruff check --fix .)
	$(call run,$(RUN) ruff format .)

typecheck: ## Check the types (mypy strict)
	$(call run,$(RUN) mypy)

pre-commit: ## Run every pre-commit hook on every file
	$(call run,$(RUN) pre-commit run --all-files --show-diff-on-failure)

##@ CI

ci: lint typecheck pre-commit coverage ## Everything the CI checks, in this order

##@ Cleanup

clean: ## Remove the Python caches (__pycache__) and the HTML report of the coverage (htmlcov/)
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
	rm -rf htmlcov
	$(call run,echo "Cleaning done.")
