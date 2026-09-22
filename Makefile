.PHONY: install format lint typecheck test check run
#NB: used AI to help with this makefile, it will install everything we setup in the CI pipeline

#must run this as a one time thing to setup
install:
	uv sync --all-groups

#actually writes formatting changes
format:
	uv run ruff format .
	uv run ruff check --fix .

# read only lint checks
lint:
	uv run ruff format --check --diff .
	uv run ruff check .

typecheck:
	uv run mypy

test:
	uv run pytest --cov --cov-report=term-missing

check: lint typecheck test

run:
	uv run fastapi dev app/main.py
