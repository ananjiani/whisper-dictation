# Development commands for whisper_dictation

# Default command - show available commands
default:
    @just --list

# Install dependencies
install:
    uv sync

# Run tests
test *args="":
    pytest {{args}}

# Run tests with coverage
test-cov:
    pytest --cov --cov-report=term-missing --cov-report=html

# Run only fast tests
test-fast:
    pytest -m "not slow"

# Run unit tests only
test-unit:
    pytest -m unit -o addopts=""

# Run integration tests only
test-integration:
    pytest -m integration

# Lint code
lint:
    ruff check whisper_dictation tests --fix
    mypy whisper_dictation

# Format code
format:
    ruff format whisper_dictation tests

# Type check
typecheck:
    mypy whisper_dictation

# Run all checks (lint, typecheck, test)
check: lint typecheck test

# Watch for changes and run tests
watch-test *args="":
    watchexec -e py -- pytest {{args}}

# Watch for changes and run a command
watch +cmd:
    watchexec -e py -- {{cmd}}

# Run the application
run *args="":
    python -m whisper_dictation {{args}}

# Clean build artifacts
clean:
    rm -rf build dist *.egg-info
    rm -rf .coverage htmlcov .pytest_cache .mypy_cache .ruff_cache
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Build package
build:
    uv build

# Generate lock file
lock:
    uv lock

# Update dependencies
update:
    uv lock --upgrade
