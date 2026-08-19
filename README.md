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

That creates a virtual environment in `.venv` and installs everything from `uv.lock`.

Run the API locally:

```bash
make run
```

It serves on http://127.0.0.1:8000, with interactive docs at http://127.0.0.1:8000/docs.

## Before you push

GitHub runs the same checks on every pull request. If they fail, the PR fails.
Do this on your machine first:

```bash
make format
make check
```

Then push.

### `make format` — the linter, and it fixes things for you

Run this whenever you're about to commit (or whenever the linter is yelling).
It reformats the code and auto-fixes what it can: indentation, quotes, import
order, unused imports, and similar style issues. It does not change how your
code behaves.

If you only want to *see* lint errors without touching files, use `make lint`.
CI uses that check-only version. You usually want `make format` instead, so
the problems get fixed rather than just listed.

### `make check` — the thing that must pass before you push

This is lint + type checking + tests, in that order. Same set of checks GitHub
will run (minus a couple of CI-only jobs like the dependency audit).

- **Lint:** fails if `make format` still has work to do. Run `make format` and
  try again.
- **Types (`mypy`):** every function needs type annotations, and they have to
  be consistent. Fix whatever it names.
- **Tests (`pytest`):** runs files in `tests/` named `test_*.py` (underscore,
  not a hyphen). `test-api.py` is ignored; `test_api.py` is not. Also fails if
  too little of `app/` is covered by those tests (see below).

If `make check` is green, you can push.

### Commands

| Command | When to use it |
| --- | --- |
| `make run` | Start the API locally (http://127.0.0.1:8000, docs at `/docs`) |
| `make format` | Auto-fix formatting and most lint errors |
| `make lint` | Report formatting/lint errors without changing files |
| `make test` | Run tests only |
| `make check` | Lint + types + tests. Run this before you push |

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

Put new tests in `tests/`. The file must be named `test_something.py` and each
test function must be named `test_something`. Pytest will not collect
`test-api.py` or a function called `stub_endpoints`. If CI says
`collected 0 items` / exit code 5, the filename is usually the problem.

Runs `pytest` and enforces two separate coverage rules:

- **Project coverage must stay at or above 50%.** Measured across `app/`.
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
tests/          test suite (files must be named test_*.py)
  conftest.py   shared fixtures, e.g. the API test client
  test_api.py   example: tests for the API stubs
scripts/        CI tooling
  coverage_comment.py   builds and enforces the coverage report CI posts
.github/
  workflows/ci.yml      the pipeline described above
  CODEOWNERS            who must approve changes to the pipeline
```

test