.PHONY: . help sync install-hooks registry bindings sync-bindings lint types build check validate clean clean-deps clean-all test sdk adapters heavy test-cov test-api artifact artifacts-clean artifacts-list artifacts-summary

.DEFAULT_GOAL := .

PYTHON_BOOT ?= $(shell command -v python3.13 2>/dev/null || command -v python3)
PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest

ARTIFACTS_DIR ?= artifacts
TIMESTAMP := $(shell date -u +%Y-%m-%dT%H-%M-%SZ)
RUN_ID := $(TIMESTAMP)_local

help:
	@echo "Porto SDK Python — Make targets"
	@echo "  make sync install-hooks registry bindings sync-bindings lint types test check validate build artifact"
	@echo "  make sdk adapters heavy test-cov test-api"
	@echo "  make artifacts-clean artifacts-list artifacts-summary clean clean-deps clean-all"

.:
	@if [ ! -x .venv/bin/python ]; then \
		echo "Creating .venv with $(PYTHON_BOOT) ..."; \
		$(PYTHON_BOOT) -m venv .venv; \
	fi
	@.venv/bin/pip install -q -U pip
	@.venv/bin/pip install -e ".[dev]"
	@$(MAKE) install-hooks
	@echo "Python SDK ready (.venv)"

install-hooks:
	@if [ ! -x .venv/bin/pre-commit ]; then \
		echo "pre-commit missing in .venv — run: make"; \
		exit 1; \
	fi
	@.venv/bin/pre-commit install
	@echo "Pre-commit hooks installed (.pre-commit-config.yaml → make check leaf jobs)"

sync: .

registry:
	@$(PYTHON_BOOT) scripts/check_registry.py --root "$(CURDIR)"

sync-bindings: .
	@$(PYTHON) scripts/build/build_error_bindings.py

bindings: .
	@$(PYTHON) scripts/build/build_error_bindings.py --check

lint: .
	@.venv/bin/ruff check porto_sdk scripts tests

types: .
	@.venv/bin/mypy porto_sdk

build: .
	@.venv/bin/python -m build

check: registry bindings lint types test

validate: check sdk adapters

artifact: build
	@.venv/bin/python scripts/release/verify_artifact.py

test: .
	@$(PYTEST) tests/ -m "not api and not sdk_bdd" -v

sdk: .
	@$(PYTHON) scripts/run_bdd_batches.py --group cli
	@$(PYTHON) scripts/run_bdd_batches.py --group core
	@$(PYTHON) scripts/run_bdd_batches.py --group provider

adapters: .
	@$(PYTHON) scripts/run_bdd_batches.py --group adapters

heavy: .
	@$(PYTHON) scripts/test/require_internetmarke_canary_env.py
	@$(PYTHON) scripts/run_bdd_batches.py --batch adapters-internetmarke-marks-canary
	@$(PYTHON) scripts/run_bdd_batches.py --batch adapters-internetmarke-marks-full

test-cov: .
	@$(PYTEST) tests/ -m "not api and not sdk_bdd" \
		--cov=porto_sdk --cov-report=term-missing --cov-report=xml --cov-fail-under=80

test-api: .
	@if [ "$$I_ACCEPT_PAID_API_COST" != "1" ]; then \
		echo "test-api: I_ACCEPT_PAID_API_COST=1 is required"; \
		exit 1; \
	fi
	@mkdir -p $(ARTIFACTS_DIR)/$(RUN_ID)
	@ARTIFACTS_DIR=$(ARTIFACTS_DIR)/$(RUN_ID) $(PYTEST) tests/ -m "api" -v

artifacts-clean:
	@cd $(ARTIFACTS_DIR) && ls -t 2>/dev/null | tail -n +6 | xargs -r rm -rf || true

artifacts-list:
	@ls -lt $(ARTIFACTS_DIR) 2>/dev/null | head -10 || echo "No runs yet"

artifacts-summary:
	@cat artifacts/bdd/latest/summary.json 2>/dev/null | $(PYTHON) -m json.tool || echo "No summary available"

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d \( -name "*.egg-info" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name "htmlcov" -o -name "dist" -o -name "build" \) -exec rm -rf {} + 2>/dev/null || true
	@rm -rf artifact-smoke-py 2>/dev/null || true

clean-deps:
	@rm -rf .venv venv 2>/dev/null || true

clean-all: clean clean-deps
