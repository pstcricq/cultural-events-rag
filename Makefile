.DEFAULT_GOAL := help
.PHONY: help install config fetch process test-unit coverage lint format typecheck pre-commit ci clean
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

help: ## Show this help
	awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	echo

##@ Environment

install: ## Install the locked environment and the git hooks
	$(call run,$(UV) sync)
	$(call run,$(RUN) pre-commit install)

##@ Config (cultural-events-rag config)

config: ## Show the active settings, secrets masked
	$(call run,$(RUN) cultural-events-rag config show)

##@ Events (cultural-events-rag fetch, process)

fetch: ## Download the raw events, MAX_EVENTS of them (ARGS="--max-events 200")
	$(call run,$(RUN) cultural-events-rag fetch $(ARGS))

process: ## Turn the raw events into the events of the common format
	$(call run,$(RUN) cultural-events-rag process)

##@ Tests

test-unit: ## Run the tests that need only the repository
	$(call run,$(RUN) pytest tests/unit -q)

coverage: ## Run the unit tests, list the lines left uncovered, fail under 95%
	$(call run,$(RUN) pytest tests/unit -q --cov $(ARGS))

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
