.PHONY: install test test-unit test-integration test-coverage clean lint format run-tests

# Default Python interpreter
PYTHON := python3
PIP := $(PYTHON) -m pip

# Virtual environment
VENV := venv
VENV_ACTIVATE := . $(VENV)/bin/activate

# Install dependencies
install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_ACTIVATE) && $(PIP) install --upgrade pip
	$(VENV_ACTIVATE) && $(PIP) install -r requirements.txt
	$(VENV_ACTIVATE) && $(PIP) install -e .

# Run all tests
test:
	$(VENV_ACTIVATE) && pytest

# Run unit tests only
test-unit:
	$(VENV_ACTIVATE) && pytest tests/unit -v -m unit

# Run integration tests only
test-integration:
	$(VENV_ACTIVATE) && pytest tests/integration -v -m integration

# Run tests with coverage
test-coverage:
	$(VENV_ACTIVATE) && pytest --cov=src --cov-report=html --cov-report=term-missing

# Run specific test file
test-file:
	$(VENV_ACTIVATE) && pytest $(FILE) -v

# Lint code
lint:
	$(VENV_ACTIVATE) && flake8 src tests
	$(VENV_ACTIVATE) && mypy src

# Format code
format:
	$(VENV_ACTIVATE) && black src tests

# Clean up
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '*.egg-info' -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .mypy_cache

# Generate test fixtures
generate-fixtures:
	$(VENV_ACTIVATE) && python -m tests.fixtures.generate_fixtures

# Quick test run (fail fast, no coverage)
quick-test:
	$(VENV_ACTIVATE) && pytest -x --tb=short

# Watch tests (requires pytest-watch)
watch:
	$(VENV_ACTIVATE) && ptw -- -x --tb=short

# Run specific test marker
test-marker:
	$(VENV_ACTIVATE) && pytest -m $(MARKER) -v

# Help
help:
	@echo "Available commands:"
	@echo "  make install          - Set up virtual environment and install dependencies"
	@echo "  make test            - Run all tests"
	@echo "  make test-unit       - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-coverage   - Run tests with coverage report"
	@echo "  make test-file FILE=path/to/test.py - Run specific test file"
	@echo "  make lint            - Run linters (flake8, mypy)"
	@echo "  make format          - Format code with black"
	@echo "  make clean           - Remove temporary files"
	@echo "  make quick-test      - Run tests quickly (fail fast)"
	@echo "  make test-marker MARKER=unit - Run tests with specific marker"