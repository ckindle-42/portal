.PHONY: install test lint typecheck ci clean help

# Default Python — override with: make install PYTHON=python3.12
PYTHON ?= python3

## install: Install Portal with all extras + dev tools
install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

## test: Run full test suite (install first if needed)
test:
	@$(PYTHON) -c "import portal" 2>/dev/null || (echo "Portal not installed. Run 'make install' first." && exit 1)
	$(PYTHON) -m pytest tests/ -v --tb=short

## test-unit: Run unit tests only (fast)
test-unit:
	@$(PYTHON) -c "import portal" 2>/dev/null || (echo "Portal not installed. Run 'make install' first." && exit 1)
	$(PYTHON) -m pytest tests/unit/ -v --tb=short

## test-cov: Run tests with coverage report
test-cov:
	@$(PYTHON) -c "import portal" 2>/dev/null || (echo "Portal not installed. Run 'make install' first." && exit 1)
	$(PYTHON) -m pytest tests/ --cov=src/portal --cov-report=term-missing --tb=short

## lint: Run ruff linter
lint:
	$(PYTHON) -m ruff check src/ tests/

## typecheck: Run mypy type checker
typecheck:
	$(PYTHON) -m mypy src/portal

## ci: Full CI pipeline (install + lint + typecheck + test with coverage)
ci: install lint typecheck test-cov

## clean: Remove build artifacts
clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

## help: Show this help
help:
	@grep -E '^## ' Makefile | sed 's/## //' | column -t -s ':'
