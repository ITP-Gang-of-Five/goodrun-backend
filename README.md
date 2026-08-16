# goodrun-backend

Backend for Good Run — a FastAPI service.

## Getting started

This project uses [uv](https://docs.astral.sh/uv/) to manage Python and dependencies.
Install it once:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then set up the repo:

```bash
make install
```

That creates a virtual environment in `.venv`, installs everything from `uv.lock`,
and installs the git pre-commit hooks.

Run the API locally:

```bash
make run
```

It serves on http://127.0.0.1:8000, with interactive docs at http://127.0.0.1:8000/docs.

## Before you push

```bash
make check
```

This runs the exact same checks as CI. If it passes locally, the pull request will
pass. If the formatter complains, `make format` fixes it for you automatically.

The pre-commit hooks installed by `make install` also run the formatter and linter
on every `git commit`, so most problems get caught before they ever reach a PR.

## Adding dependencies

```bash
uv add fastapi-users          # runtime dependency
uv add --group dev pytest-mock # development-only dependency
```

Both commands update `pyproject.toml` and `uv.lock`. **Commit `uv.lock`** — CI
installs from it with `--locked` and will fail if it is out of date.

## What CI checks

Every pull request into `main` runs six checks, each a separately named job so a
red mark in the PR tells you what broke without having to open the logs.

| Check | Command | What it catches | How to fix |
| --- | --- | --- | --- |
| Formatting (ruff format) | `ruff format --check` | Inconsistent formatting. The `black` equivalent. | `make format` |
| Linting (ruff check) | `ruff check` | Unused imports and variables, unsorted imports, likely bugs, outdated syntax. Covers what `flake8` and `isort` did. | `make format` fixes most; the rest are listed as annotations on the PR diff |
| Type checking (mypy) | `mypy` | Type errors, and functions missing type annotations. | Add the annotations it names |
| Tests & coverage (pytest) | `pytest` | Failing tests, and untested code. See below. | Write tests |
| Dependency audit (pip-audit) | `pip-audit` | Known CVEs in your dependencies. | Usually a Dependabot PR |
| Workflow lint (actionlint) | `actionlint` | Mistakes in `.github/workflows/*.yml` itself. | Fix what it names |

### Tests & coverage

Runs `pytest` and enforces two separate coverage rules:

- **Project coverage must stay at or above 50%.** Measured across `app/` and
  `scripts/`.
- **Patch coverage must be at or above 50%.** At least half of the lines *your PR
  changes* must be executed by a test. This is the rule that stops someone merging
  a large untested feature by hiding behind the rest of the codebase.

The job posts a comment on the pull request showing both numbers against the
threshold, plus the exact lines you changed that no test reaches.

Both thresholds come from `fail_under` under `[tool.coverage.report]` in
`pyproject.toml`. Change that one number to move both gates.

## Project layout

```
app/            application code (coverage is measured here)
  main.py       FastAPI app and routes
tests/          test suite
  conftest.py   shared fixtures, e.g. the API test client
scripts/        CI tooling (coverage is measured here too)
  coverage_comment.py   builds and enforces the coverage report CI posts
.github/
  workflows/ci.yml      the pipeline described above
  CODEOWNERS            who must approve changes to the pipeline
```
