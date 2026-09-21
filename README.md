# goodrun-backend
Backend for Good Run Project (updated for sprint 2)



# Notes

This requires [uv](https://docs.astral.sh/uv/) and Python 3.14, we should all use the same version of these for consistency. 

Run the following

```sh
make install
```
to install everything


then use
```sh 
make run
```
To actually run fast api, which should spawn the backend on `localhost:8000`
## Getting started

Requires 

```sh
make install
make run
```

The API serves on `http://localhost:8000`, with interactive docs at `/docs`.

## Commands

| Command          | What it does                                   |
| ---------------- | ---------------------------------------------- |
| `make install`   | Install dependencies                           |
| `make run`       | Start the API in dev mode                      |
| `make format`    | Format and autofix lint issues                 |
| `make lint`      | Check formatting and lint (what CI runs)       |
| `make typecheck` | Run mypy                                       |
| `make test`      | Run the tests with coverage                    |
| `make check`     | Lint, typecheck and test. Run before pushing   |

## Layout

```
app/
  main.py        FastAPI app
  api/           mounts every domain router under /api/v0
  auth/          each domain has its own package with a router
  orders/
  runs/
  volunteers/
  organisations/
  locations/
tests/
scripts/         CI helpers
```
