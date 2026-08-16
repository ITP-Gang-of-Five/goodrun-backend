.PHONY: install format lint typecheck test check run

# One-time setup for a new clone.
install:
	uv sync --all-groups
	uv run pre-commit install

# Rewrites your files to satisfy the formatter and autofixable lint rules.
format:
	uv run ruff format .
	uv run ruff check --fix .

# Read-only: the same checks CI runs.
lint:
	uv run ruff format --check --diff .
	uv run ruff check .

typecheck:
	uv run mypy

test:
	uv run pytest --cov --cov-report=term-missing

# Run this before pushing. If it passes, CI will pass.
check: lint typecheck test

run:
	uv run fastapi dev app/main.py
